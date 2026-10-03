import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RELAY = os.path.join(HERE, "relay.py")

P = [0, 0, 0, 0, 0, 0]


def link(frm, to, cost=1, bw=100, lat=10, up=True):
    return {"from": frm, "to": to, "cost": cost, "bandwidth": bw,
            "latency": lat, "up": up}


def base_topo():
    # n0 -> n1 -> n3 -> n4 and n0 -> n2 -> n3; both n0->n4 paths cost
    # 3, the n1 path winning the full-node-sequence Unicode tie break.
    return {"nodes": ["n0", "n1", "n2", "n3", "n4"],
            "links": [link("n0", "n1", lat=10),
                      link("n1", "n3", lat=10),
                      link("n0", "n2", lat=50),
                      link("n2", "n3", lat=50),
                      link("n3", "n4", lat=10)]}


def pack(topo=None, v=0, history=None):
    topo = topo or base_topo()
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


SCENARIOS = [["x", ["n1"], []], ["z", [], [["n0", "n1"]]]]


def flow(fid="f1", src="n0", dst="n4", demand=40, mlat=110):
    return [fid, src, dst, demand, mlat]


def moved_topo():
    # Raising n1->n3 cost to 2 pushes the no-failure n0->n4 route to
    # the n2 path; the x/z scenarios were already on n2.
    t = json.loads(json.dumps(base_topo()))
    t["links"][1]["cost"] = 2
    return t


def alt_topo():
    # Only the failure scenarios reroute (no-failure path unchanged).
    t = json.loads(json.dumps(base_topo()))
    t["nodes"].append("n5")
    t["links"][2]["cost"] = 2
    t["links"][3]["cost"] = 2
    t["links"].append(link("n0", "n5"))
    t["links"].append(link("n5", "n3"))
    return t


class Op31(unittest.TestCase):
    def call(self, op_obj, pk=None, expect_rc=0):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            with open(pp, "rb") as fh:
                before = fh.read()
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                json.dumps(op_obj)], capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, expect_rc,
                             "rc=%s err=%s out=%s"
                             % (r.returncode, r.stderr, r.stdout))
            out = json.loads(r.stdout) if r.stdout else None
            with open(pp, "rb") as fh:
                after = fh.read()
            tmps = [n for n in os.listdir(d) if ".tmp." in n]
            return out, before, after, tmps

    def call_raw(self, op_obj, pk=None):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                json.dumps(op_obj)], capture_output=True)
            return r

    # The op 31 scenario row inserts maxWindowMoves after maxMoves, so
    # its flows/links shift from op 30's index 7 to index 8.
    def flows(self, event_row, s_index=0):
        return event_row[4][3][s_index][8]

    def test_preview_pass_renders_window_fields(self):
        t = moved_topo()
        op = [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
              1000000, 1000000, 1000000, 1000000, 1]
        out, before, after, tmps = self.call(op)
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [31, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row keeps op 30's shape plus maxWindowMoves at index 6.
        s0 = scenarios[0]
        self.assertEqual(len(s0), 10)
        self.assertEqual(s0[0:7],
                         [None, "0.400000", 40, 40, "1.000000", 1, 1])
        f0 = s0[8][0]
        # [id,oldCost,newCost,oldLat,newLat,oldPath,newPath,moved,pass,
        # moves,previousMoveClock,gap,intervalPass,
        # windowStart,windowMoves,windowPass]
        self.assertEqual(f0,
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True, 1,
                          None, None, True, -999999, 1, True])
        # x/z did not move: null clocks/gap, interval/window pass,
        # moves and windowMoves both 0; windowStart is fixed at e-W.
        for sx in scenarios[1:]:
            self.assertEqual(sx[5:7], [0, 0])
            self.assertTrue(sx[7])
            fr = sx[8][0]
            self.assertEqual(fr[7], False)
            self.assertEqual(fr[9:16], [0, None, None, True,
                                        -999999, 0, True])

    def test_second_move_inside_window_fails(self):
        t1, t2 = moved_topo(), base_topo()
        # Reroutes at clocks 1 and 4, D unrestricted but W=3 keeps the
        # clock-1 record in the closed [1,4] window: candidate wm 2 > Q1.
        out, before, after, tmps = self.call(
            [31, 0, 0, [[1, t1, P], [4, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 0, 3, 1])
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (4, 2)])
        s0 = out["events"][1][4][3][0]
        # The op 28 gates and the interval pass; only the window fails
        # the scenario (scenario pass folds in windowPass, like op 30's
        # interval folding).
        self.assertFalse(s0[7])
        fr = s0[8][0]
        self.assertEqual(fr[9:16], [2, 1, 3, True, 1, 2, False])

    def test_window_boundary_is_closed(self):
        t1, t2 = moved_topo(), base_topo()
        # W=2: window at clock 4 starts at 2, clock 1 is evicted, wm 1.
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [4, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 0, 2, 1])
        self.assertEqual(out["status"], 0)
        self.assertEqual([r[1] for r in out["events"]], [0, 0])
        self.assertEqual(self.flows(out["events"][1])[0][13:16],
                         [2, 1, True])
        # W=3: the window starts at exactly 1, the record is retained.
        out2, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [4, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 0, 3, 1])
        self.assertEqual(out2["status"], 2)
        self.assertEqual(self.flows(out2["events"][1])[0][13:16],
                         [1, 2, False])

    def test_w_zero_accumulates_same_clock_but_separates_clocks(self):
        t1, t2 = moved_topo(), base_topo()
        # W=0 keeps both reroutes at clock 1 in [1,1]: wm 2 > Q 1.
        out, before, after, _ = self.call(
            [31, 0, 0, [[1, t1, P], [1, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 0, 0, 1])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (1, 2)])
        self.assertEqual(self.flows(out["events"][1])[0][13:16],
                         [1, 2, False])
        # W=0 at distinct clocks 1 and 4: each [e,e] window sees only
        # its own reroute, so both events pass with wm 1.
        out0, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [4, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 0, 0, 1])
        self.assertEqual(out0["status"], 0)
        self.assertEqual(
            [self.flows(out0["events"][i])[0][13:16] for i in (0, 1)],
            [[1, 1, True], [4, 1, True]])

    def test_q_zero_rejects_every_reroute(self):
        t = moved_topo()
        out, before, after, _ = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1000000, 1000000, 1000000, 0])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        fr = s0[8][0]
        # The reroute counts (moves 1, interval fine) but wm 1 > Q 0.
        self.assertEqual(fr[9:13], [1, None, None, True])
        self.assertEqual(fr[13:16], [-999999, 1, False])
        # x/z did not reroute: wm 0 passes even under Q 0.
        for sx in out["events"][0][4][3][1:]:
            self.assertEqual(sx[8][0][13:16], [-999999, 0, True])

    def test_equal_state_event_adds_no_record(self):
        t1, t2 = moved_topo(), base_topo()
        # move@1, equal-state@2 (status 1, empty impact), move-back@5.
        # W=3: the window at clock 5 starts at 2, so the clock-1 record
        # is gone and the second reroute passes with wm 1.
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [2, t1, P], [5, t2, P]],
             [flow()], SCENARIOS, 1000000, 1000000, 1000000, 0, 3, 1])
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (5, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        fr = self.flows(out["events"][2])[0]
        self.assertEqual(fr[9:16], [2, 1, 4, True, 2, 1, True])

    def test_non_movement_does_not_record(self):
        # alt_topo reroutes only x/z at the change event; the no-failure
        # flow never migrates, so its window count stays zero even with a
        # second equal-state event at a fresh clock. Q=1 lets the x/z
        # first reroutes through so the batch is otherwise feasible.
        t = alt_topo()
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t, P], [2, t, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 0, 0, 1])
        self.assertEqual(out["status"], 0)
        self.assertEqual([r[1] for r in out["events"]], [0, 1])
        fr = self.flows(out["events"][0])[0]
        self.assertEqual(fr[9:16], [0, None, None, True, 1, 0, True])

    def test_window_per_scenario_independent(self):
        # alt_topo reroutes only x/z at clock 1; a single event passes
        # everywhere (first reroute, no prior record).
        t = alt_topo()
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1000000, 1000000, 1000000, 1])
        self.assertEqual(out["status"], 0)
        scenarios = out["events"][0][4][3]
        # no-failure: no move; x/z: first move, prior clock null, wm 1.
        self.assertEqual(self.flows(out["events"][0], 0)[0][9:16],
                         [0, None, None, True, -999999, 0, True])
        for sx in scenarios[1:]:
            self.assertEqual(sx[8][0][9:16],
                             [1, None, None, True, -999999, 1, True])
            self.assertTrue(sx[7])

    def test_window_per_flow_independent(self):
        # f1 (n0->n4) and f2 (n0->n3) both reroute on every change; each
        # keeps its own count and wm 2, never merged across flows.
        t1, t2 = moved_topo(), base_topo()
        flows = [flow(), flow("f2", "n0", "n3", 40, 200)]
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [2, t2, P]], flows, SCENARIOS,
             1000000, 1000000, 1000000, 0, 100, 1])
        self.assertEqual(out["status"], 2)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[5:7], [2, 2])
        self.assertEqual([f[14] for f in s0[8]], [2, 2])
        self.assertTrue(all(not f[15] for f in s0[8]))

    def test_r_cap_still_rejects(self):
        t = moved_topo()
        # R=0 rejects the first move; windowPass stays true with Q large.
        out, before, after, _ = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 0, 0, 1000000, 1000000])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertTrue(s0[7])
        self.assertEqual(s0[8][0][9:16], [1, None, None, True,
                                          -999999, 1, True])

    def test_minimum_interval_still_gates(self):
        t1, t2 = moved_topo(), base_topo()
        # gap 3 < D=5 fails the interval; a wide window with Q large
        # passes the window gate on its own.
        out, before, after, _ = self.call(
            [31, 0, 0, [[1, t1, P], [4, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 5, 1000000, 1000000])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        fr = self.flows(out["events"][1])[0]
        self.assertEqual(fr[12], False)
        self.assertEqual(fr[13:16], [-999996, 2, True])

    def test_op28_gates_still_apply(self):
        t = moved_topo()
        # C gate: the no-failure scenario migrates all demand.
        out, before, after, _ = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             999999, 1000000, 1000000, 1000000, 1000000])
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["events"][0][4][3][0][7])
        self.assertEqual(after, before)
        # L gate boundary 400000.
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 399999,
             1000000, 1000000, 1000000, 1000000, 1000000])
        self.assertEqual(out["status"], 2)
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 400000,
             1000000, 1000000, 1000000, 1000000, 1000000])
        self.assertEqual(out["status"], 0)
        # Old-side infeasible at h[b] is code 5.
        self.call(
            [31, 0, 0, [[1, t, P]], [flow(mlat=109)], SCENARIOS,
             1000000, 1000000, 1000000, 1000000, 1000000, 1000000],
            expect_rc=5)

    def test_commit_resend_and_idempotent(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            [31, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 1000000, 1])
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            [31, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 1000000, 1], pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Same-state event: status 1 row, no write even with R=D=Q=0.
        out3, _, after3, _ = self.call(
            [31, 1, 1, [[2, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 0, 0, 1000000, 0], pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(after3, after2)

    def test_failed_batch_does_not_commit(self):
        t1, t2 = moved_topo(), base_topo()
        # The first event would commit; the second fails the burst
        # window (W=100 keeps the clock-1 record): mode 1 must leave
        # PACK at the pre-call version.
        out, before, after, tmps = self.call(
            [31, 1, 0, [[1, t1, P], [2, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 0, 100, 1])
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # Retrying after a failure with a feasible batch (W=4 drops the
        # prior record before each second reroute) is a fresh simulation
        # from h[b] and succeeds.
        out2, _, after2, _ = self.call(
            [31, 1, 0, [[6, t1, P], [12, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1000000, 0, 4, 1])
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_byte_deterministic(self):
        t = moved_topo()
        op = [31, 0, 0, [[1, t, P], [7, base_topo(), P]], [flow()],
              SCENARIOS, 1000000, 1000000, 2, 5, 3, 1]
        r1 = self.call_raw(op)
        r2 = self.call_raw(op)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        t = moved_topo()
        good = [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
                1000000, 1, 5, 6, 1]
        self.assertEqual(len(good), 12)
        bad = [
            # wrong arity: op 30's 10-element shape and an 11-element
            # shape accepted nowhere as op 31, and one element too many
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 6],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 6, 1, 1],
            # W negative / boolean / too large / string
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             -1, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             True, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             10 ** 18, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             "6", 1],
            # Q negative / boolean / too large / string
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, -1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, False],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 10 ** 18],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, "1"],
            # R, D, C, and L ranges still enforced
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, -1, 1,
             1, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, -1,
             1, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001,
             1, 1, 1, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000001, 1,
             1, 1, 1, 1],
            # bad mode
            [31, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1],
            # empty E / F / S
            [31, 0, 0, [], [flow()], SCENARIOS, 1, 1, 1, 1, 1, 1],
            [31, 0, 0, [[1, t, P]], [], SCENARIOS, 1, 1, 1, 1, 1, 1],
            [31, 0, 0, [[1, t, P]], [flow()], [], 1, 1, 1, 1, 1, 1],
            # clocks decrease
            [31, 0, 0, [[2, t, P], [1, t, P]], [flow()], SCENARIOS, 1,
             1, 1, 1, 1, 1],
            # invalid scenario reference at h[b]
            [31, 0, 0, [[1, t, P]], [flow()],
             [["q", ["n4"], []]], 1, 1, 1, 1, 1, 1],
            # flow endpoint absent at h[b]
            [31, 0, 0, [[1, t, P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1, 1, 1, 1, 1, 1],
        ]
        for op in bad:
            self.call(op, expect_rc=5)

    def test_stale_base_conflict_code5(self):
        t = moved_topo()
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        other = json.loads(json.dumps(base_topo()))
        other["links"][0]["latency"] = 7
        self.call(
            [31, 1, 0, [[6, other, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 1000000, 1], pk=pk1, expect_rc=5)

    def test_ops_0_to_30_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        t = moved_topo()
        # op 30 happy path and its 10-arity shape still parse; its flow
        # row keeps the 13-element op 30 shape.
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5])
        self.assertEqual(out["op"], 30)
        self.assertEqual(
            len(out["events"][0][4][3][0][7][0]), 13)
        # op 31's 12-arity shape must not parse as op 30.
        self.call(
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 6, 1], expect_rc=5)
        # op 29 still parses at arity 9 and op 28 at arity 8.
        out, _, _, _ = self.call(
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1])
        self.assertEqual(out["op"], 29)
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000])
        self.assertEqual(out["op"], 28)

    def test_json_and_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[31,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],"
                                "1,1,1,1,1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
