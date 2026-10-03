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
    # Only the failure scenarios reroute (no-failure path unchanged):
    # n5 ties the no-failure n1 path on cost and loses the tie break,
    # but beats the n2 detour the failure scenarios use.
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

    def test_preview_pass_renders_window_fields(self):
        t = moved_topo()
        op = [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
              1000000, 1, 5, 5, 1]
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
        # Scenario row: op 30's 9-element shape plus maxWindowMoves
        # inserted after maxMoves.
        s0 = scenarios[0]
        self.assertEqual(len(s0), 10)
        self.assertEqual(s0[0:8],
                         [None, "0.400000", 40, 40, "1.000000", 1, 1, True])
        f0 = s0[8][0]
        # [id,oldCost,newCost,oldLat,newLat,oldPath,newPath,moved,pass,
        # moves,previousMoveClock,gap,intervalPass,
        # windowStart,windowMoves,windowPass]
        self.assertEqual(f0,
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True, 1,
                          None, None, True, -4, 1, True])
        # x/z did not move: no record, windowMoves 0, windowStart fixed
        # at e-W, windowPass true.
        for sx in scenarios[1:]:
            self.assertEqual(sx[5:8], [0, 0, True])
            fr = sx[8][0]
            self.assertEqual(fr[7], False)
            self.assertEqual(fr[13:16], [-4, 0, True])

    def test_q_zero_rejects_every_reroute(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 10, 10, 5, 0])
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        s0 = out["events"][0][4][3][0]
        # R and D pass; only the window fails the scenario.
        self.assertFalse(s0[7])
        fr = s0[8][0]
        self.assertEqual(fr[9:16],
                         [1, None, None, True, -4, 1, False])
        # Non-moving failure scenarios keep their window empty/passing.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[7])
            self.assertEqual(sx[8][0][13:16], [-4, 0, True])

    def test_w_zero_accumulates_same_clock_reroutes(self):
        t1, t2 = moved_topo(), base_topo()
        # Two reroutes at clock 1 with W=0: the second counts with the
        # first (1 is not below e-W=1) and exceeds Q=1. D=0 so the
        # interval gate stays quiet.
        out, before, after, _ = self.call(
            [31, 0, 0, [[1, t1, P], [1, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 0, 0, 1])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (1, 2)])
        fr = out["events"][1][4][3][0][8][0]
        self.assertEqual(fr[9:16],
                         [2, 1, 0, True, 1, 2, False])
        # Q=2 admits both same-clock reroutes.
        out2, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [1, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 0, 0, 2])
        self.assertEqual(out2["status"], 0)
        self.assertEqual([r[1] for r in out2["events"]], [0, 0])
        self.assertEqual(out2["events"][1][4][3][0][8][0][14], 2)
        self.assertTrue(out2["events"][1][4][3][0][8][0][15])

    def test_window_is_closed_and_slides(self):
        t1, t2 = moved_topo(), base_topo()
        # reroutes at 1 and 6, W=5, Q=1: windowStart=1 keeps clock 1
        # (closed lower edge), so the candidate is the second record.
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [6, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 0, 5, 1])
        self.assertEqual(out["status"], 2)
        fr = out["events"][1][4][3][0][8][0]
        self.assertEqual(fr[13:16], [1, 2, False])
        # At clock 7 windowStart=2: clock 1 falls below and is dropped,
        # leaving only the candidate.
        out2, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [7, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 0, 5, 1])
        self.assertEqual(out2["status"], 0)
        fr2 = out2["events"][1][4][3][0][8][0]
        self.assertEqual(fr2[13:16], [2, 1, True])
        # A non-reroute between them slides the window without adding:
        # t1b keeps the flow on the n2 path but is a new state, so at
        # clock 6 with W=4 the retained window is [2, 6], holding only
        # the candidate once clock 1 is dropped.
        t1b = json.loads(json.dumps(base_topo()))
        t1b["links"][1]["cost"] = 3
        out3, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [3, t1b, P], [6, t2, P]],
             [flow()], SCENARIOS, 1000000, 1000000, 10, 0, 4, 1])
        self.assertEqual(out3["status"], 0)
        self.assertEqual([r[1] for r in out3["events"]], [0, 0, 0])
        self.assertEqual(
            out3["events"][1][4][3][0][8][0][7], False)
        fr3 = out3["events"][2][4][3][0][8][0]
        self.assertEqual(fr3[13:16], [2, 1, True])

    def test_equal_state_event_adds_no_record(self):
        t1, t2 = moved_topo(), base_topo()
        # move@1, equal-state@2 (status 1, empty impact), move-back@3;
        # W=10 keeps clock 1 in [−7, 3], so Q=1 rejects the move-back
        # with two records. The equal event added nothing.
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [2, t1, P], [3, t2, P]],
             [flow()], SCENARIOS, 1000000, 1000000, 10, 0, 10, 1])
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 2)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        fr = out["events"][2][4][3][0][8][0]
        self.assertEqual(fr[13:16], [-7, 2, False])
        # W=0: the equal event leaves no clock-2 record and clock 1 is
        # outside [2, 2], so the move-back passes as the only record.
        out0, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [2, t1, P], [2, t2, P]],
             [flow()], SCENARIOS, 1000000, 1000000, 10, 0, 0, 1])
        self.assertEqual(out0["status"], 0)
        self.assertEqual(
            out0["events"][2][4][3][0][8][0][13:16], [2, 1, True])

    def test_non_movement_adds_no_window_record(self):
        # alt_topo only moves x/z; the no-failure flow never migrates,
        # so with Q=0 the no-failure scenario still passes while x/z
        # fail on their first candidate. Simulation stops at this one
        # event.
        t = alt_topo()
        out, before, after, _ = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 10, 1, 1, 0])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([r[1] for r in out["events"]], [2])
        scenarios = out["events"][0][4][3]
        # no-failure flow: no record and still passing with Q=0.
        self.assertTrue(scenarios[0][7])
        self.assertEqual(scenarios[0][8][0][13:16], [0, 0, True])
        # x/z: the candidate is their first record and Q=0 rejects it.
        for sx in scenarios[1:]:
            self.assertFalse(sx[7])
            self.assertEqual(sx[8][0][13:16], [0, 1, False])

    def test_windows_per_scenario_and_per_flow_independent(self):
        # A single alt event with Q=0: x/z move and fail their windows,
        # the no-failure flow does not; scenarios never merge.
        t = alt_topo()
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 10, 5, 5, 0])
        self.assertEqual(out["status"], 2)
        scenarios = out["events"][0][4][3]
        self.assertTrue(scenarios[0][7])
        self.assertEqual(scenarios[0][8][0][14:16], [0, True])
        for sx in scenarios[1:]:
            self.assertFalse(sx[7])
            self.assertEqual(sx[8][0][14:16], [1, False])
        # f1 (n0->n4) migrates on moved_topo; f2 (n2->n4) keeps its
        # complete node path in every scenario and must keep an empty
        # window (n2 is untouched by both the n1 failure and the
        # n0->n1 link failure).
        f2 = ["f2", "n2", "n4", 40, 110]
        out2, _, _, _ = self.call(
            [31, 0, 0, [[1, moved_topo(), P]], [flow(), f2],
             SCENARIOS, 1000000, 1000000, 10, 5, 5, 0])
        self.assertEqual(out2["status"], 2)
        rows = out2["events"][0][4][3][0][8]
        self.assertEqual(rows[0][7:9], [True, True])
        self.assertEqual(rows[0][14:16], [1, False])
        self.assertEqual(rows[1][7:9], [False, True])
        self.assertEqual(rows[1][14:16], [0, True])
        self.assertEqual(rows[1][5:7],
                         [["n2", "n3", "n4"], ["n2", "n3", "n4"]])

    def test_r_and_d_gates_still_reject(self):
        t1, t2 = moved_topo(), base_topo()
        # R=0 rejects the first move; windowPass stays true.
        out, before, after, _ = self.call(
            [31, 0, 0, [[1, t1, P]], [flow()], SCENARIOS, 1000000,
             1000000, 0, 0, 5, 10])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertTrue(s0[7])
        self.assertEqual(s0[8][0][15], True)
        # D=5 rejects the clock-4 reroute while the W=10/Q=10 window
        # admits it: only intervalPass goes false.
        out2, _, _, _ = self.call(
            [31, 0, 0, [[1, t1, P], [4, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 5, 10, 10])
        self.assertEqual(out2["status"], 2)
        fr = out2["events"][1][4][3][0][8][0]
        self.assertEqual(fr[12], False)
        self.assertEqual(fr[13:16], [-6, 2, True])

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
             1000000, 1, 5, 5, 1])
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
             1000000, 1, 5, 5, 1], pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Same-state event: status 1 row, no write even with W=Q=R=D=0.
        out3, _, after3, _ = self.call(
            [31, 1, 1, [[2, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 0, 0, 0, 0], pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(after3, after2)

    def test_failed_batch_does_not_commit(self):
        t1, t2 = moved_topo(), base_topo()
        # The first event would commit; the second exceeds Q=1 with
        # W=10: mode 1 must leave PACK at the pre-call version.
        out, before, after, tmps = self.call(
            [31, 1, 0, [[1, t1, P], [2, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 0, 10, 1])
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # Retrying after a failure with a feasible batch is a fresh
        # simulation from h[b] and succeeds (clock 1 has left [2, 8]).
        out2, _, after2, _ = self.call(
            [31, 1, 0, [[1, t1, P], [8, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 0, 5, 1])
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_byte_deterministic(self):
        t = moved_topo()
        op = [31, 0, 0, [[1, t, P], [7, base_topo(), P]], [flow()],
              SCENARIOS, 1000000, 1000000, 2, 5, 5, 2]
        r1 = self.call_raw(op)
        r2 = self.call_raw(op)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        t = moved_topo()
        good = [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
                1000000, 1, 5, 5, 1]
        self.assertEqual(len(good), 12)
        bad = [
            # wrong arity: op 30's 11-element shape accepted nowhere as
            # op 31, and one element too many
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1, 1],
            # W negative / boolean / too large / string
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             -1, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             True, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             10 ** 18, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             "5", 1],
            # Q negative / boolean / too large / string
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1, 1,
             -1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1, 1,
             True],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1, 1,
             10 ** 18],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1, 1,
             "1"],
            # R, D, C, and L ranges still enforced
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, -1, 1, 1,
             1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, -1, 1,
             1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001, 1,
             1, 1, 1],
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000001, 1, 1,
             1, 1, 1],
            # bad mode
            [31, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1, 1,
             1],
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
             1000000, 1, 5, 5, 1], pk=pk1, expect_rc=5)

    def test_ops_0_to_30_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        t = moved_topo()
        # op 30 happy path and its 13-field flow row still parse.
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5])
        self.assertEqual(out["op"], 30)
        self.assertEqual(
            len(out["events"][0][4][3][0][7][0]), 13)
        self.assertEqual(
            len(out["events"][0][4][3][0]), 9)
        # op 31's 12-arity shape must not parse as op 30.
        self.call(
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1], expect_rc=5)
        # op 29/28 still parse at their arities.
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
