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
    # the n2 path (cost 3 vs 4); the x/z scenarios were already on n2.
    t = json.loads(json.dumps(base_topo()))
    t["links"][1]["cost"] = 2
    return t


def tweak_topo():
    # A state different from moved_topo() that leaves every routed path
    # unchanged: only the (currently unused) n0->n1 cost changes. In
    # no-failure the flow stays on the n2 path, so the event is a real
    # non-idempotent event yet records no reroute for any flow/scenario.
    t = moved_topo()
    t["links"][0]["cost"] = 2
    return t


def alt_topo():
    # Adds an n0 -> n5 -> n3 detour (cost 1 per edge) and raises the n2
    # edges to cost 2. In no-failure the n0->n4 route stays on the n1
    # path (cost 3 ties the n5 path and "n1" < "n5" in the
    # full-node-sequence tie break); scenarios x/z, forced off the n1
    # side, have a cost-4 n2 path vs the cost-3 n5 path and switch.
    t = json.loads(json.dumps(base_topo()))
    t["nodes"].append("n5")
    t["links"][2]["cost"] = 2
    t["links"][3]["cost"] = 2
    t["links"].append(link("n0", "n5"))
    t["links"].append(link("n5", "n3"))
    return t


class Op30(unittest.TestCase):
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

    def test_preview_pass_appends_interval_fields(self):
        t = moved_topo()
        op = [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
              1000000, 1, 5]
        out, before, after, tmps = self.call(op)
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [30, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        e, status, old, new, impact = row
        self.assertEqual([e, status, old, new], [1, 0, 0, 1])
        self.assertEqual(len(impact), 4)
        scenarios = impact[3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row keeps op 29's 9-element shape.
        for s in scenarios:
            self.assertEqual(len(s), 9)
        # no-failure row: [sid,peak,movedDemand,totalDemand,movedRatio,
        # maxMoves,pass,flows,links]
        s0 = scenarios[0]
        self.assertEqual(s0[0:7],
                         [None, "0.400000", 40, 40, "1.000000", 1, True])
        f0 = s0[7][0]
        # [id,oldCost,newCost,oldLat,newLat,oldPath,newPath,moved,pass,
        # moves,previousMoveClock,gap,intervalPass]
        self.assertEqual(f0,
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True, 1,
                          None, None, True])
        # x/z did not move: maxMoves 0, moves 0, and the first two
        # appended fields are null with intervalPass true.
        for sx in scenarios[1:]:
            self.assertEqual(sx[5], 0)
            self.assertTrue(sx[6])
            self.assertEqual(sx[7][0][7], False)
            self.assertEqual(sx[7][0][9], 0)
            self.assertEqual(sx[7][0][10:13], [None, None, True])
        self.assertEqual(scenarios[1][0], "x")
        self.assertEqual(scenarios[2][0], "z")

    def test_first_move_passes_even_with_large_d(self):
        t = moved_topo()
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 10 ** 9])
        self.assertEqual(out["status"], 0)
        f0 = out["events"][0][4][3][0][7][0]
        self.assertEqual(f0[10:13], [None, None, True])

    def test_gap_below_d_fails_event_and_scenario(self):
        t1, t2 = moved_topo(), base_topo()
        out, before, after, tmps = self.call(
            [30, 1, 0, [[1, t1, P], [2, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 2])
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s = out["events"][1][4][3]
        # Only the no-failure scenario rerouted twice; its scenario pass
        # aggregates the false intervalPass.
        self.assertFalse(s[0][6])
        self.assertTrue(s[1][6])
        self.assertTrue(s[2][6])
        f = s[0][7][0]
        # Candidate count/clock retained on the failing event.
        self.assertEqual(f[9], 2)
        self.assertEqual(f[10:13], [1, 1, False])
        # The non-flapping failure scenarios keep null gap fields.
        for sx in s[1:]:
            self.assertEqual(sx[7][0][10:13], [None, None, True])

    def test_gap_equal_to_d_passes(self):
        t1, t2 = moved_topo(), base_topo()
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t1, P], [3, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 2])
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (3, 0)])
        f = out["events"][1][4][3][0][7][0]
        self.assertEqual(f[10:13], [1, 2, True])

    def test_d_zero_admits_same_clock_reroutes(self):
        t1, t2 = moved_topo(), base_topo()
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t1, P], [1, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 0])
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (1, 0)])
        f = out["events"][1][4][3][0][7][0]
        self.assertEqual(f[10:13], [1, 0, True])

    def test_same_clock_second_reroute_fails_for_positive_d(self):
        t1, t2 = moved_topo(), base_topo()
        out, before, after, _ = self.call(
            [30, 1, 0, [[1, t1, P], [1, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 1])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (1, 2)])
        f = out["events"][1][4][3][0][7][0]
        self.assertEqual(f[10:13], [1, 0, False])

    def test_no_reroute_keeps_previous_clock_but_null_gap(self):
        # Event 1 reroutes in no-failure (clock 1). Event 2 changes the
        # state (tweaks an unused edge) without changing any routed
        # path: previousMoveClock renders the last reroute clock, gap is
        # null and intervalPass true, and the count/clock stay put.
        t1, tw = moved_topo(), tweak_topo()
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t1, P], [4, tw, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 100])
        self.assertEqual(out["status"], 0)
        s = out["events"][1][4][3]
        f = s[0][7][0]
        self.assertFalse(f[7])          # not a reroute this event
        self.assertEqual(f[9], 1)       # count unchanged
        self.assertEqual(f[10:13], [1, None, True])
        # A later real flap back at clock 5 still measures from clock 1.
        out2, _, _, _ = self.call(
            [30, 0, 0, [[1, t1, P], [4, tw, P], [5, base_topo(), P]],
             [flow()], SCENARIOS, 1000000, 1000000, 10, 4])
        self.assertEqual(out2["status"], 0)
        f2 = out2["events"][2][4][3][0][7][0]
        self.assertEqual(f2[10:13], [1, 4, True])
        out3, _, _, _ = self.call(
            [30, 0, 0, [[1, t1, P], [4, tw, P], [5, base_topo(), P]],
             [flow()], SCENARIOS, 1000000, 1000000, 10, 5])
        self.assertEqual(out3["status"], 2)

    def test_equal_state_events_update_nothing(self):
        t = moved_topo()
        out, _, after, _ = self.call(
            [30, 1, 0, [[1, t, P], [2, t, P], [3, base_topo(), P]],
             [flow()], SCENARIOS, 1000000, 1000000, 1, 5])
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 2)])
        # The equal-state row keeps the op 28/29 empty-impact shape.
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        # The final flap back sees the clock gap measured across the
        # equal-state event (3 - 1) and fails D = 5.
        f = out["events"][2][4][3][0][7][0]
        self.assertEqual(f[9], 2)
        self.assertEqual(f[10:13], [1, 2, False])
        # D = 2 admits the same batch.
        out2, _, _, _ = self.call(
            [30, 0, 0, [[1, t, P], [2, t, P], [3, base_topo(), P]],
             [flow()], SCENARIOS, 1000000, 1000000, 2, 2])
        self.assertEqual(out2["status"], 0)

    def test_scenarios_track_clocks_independently(self):
        # alt_topo reroutes only the x/z failure scenarios. Two alt
        # variants force a second reroute there; no-failure never moves.
        t = alt_topo()
        t2 = json.loads(json.dumps(t))
        # Raise the n5 detour cost so x/z switch back to the n2 path.
        for lk in t2["links"]:
            if lk["from"] == "n0" and lk["to"] == "n5":
                lk["cost"] = 5
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t, P], [2, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 2])
        self.assertEqual(out["status"], 2)
        s = out["events"][1][4][3]
        # no-failure: no moves at all; x/z: second reroute, gap 1.
        self.assertEqual(s[0][7][0][10:13], [None, None, True])
        self.assertTrue(s[0][6])
        for sx in s[1:]:
            self.assertFalse(sx[6])
            self.assertEqual(sx[7][0][10:13], [1, 1, False])
        out2, _, _, _ = self.call(
            [30, 0, 0, [[1, t, P], [3, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 10, 2])
        self.assertEqual(out2["status"], 0)

    def test_r_cap_still_enforced(self):
        t1, t2 = moved_topo(), base_topo()
        # R = 2 with D = 0: the interval never rejects but the third
        # cumulative reroute breaches R.
        out, before, after, _ = self.call(
            [30, 1, 0, [[1, t1, P], [2, t2, P], [3, t1, P]], [flow()],
             SCENARIOS, 1000000, 1000000, 2, 0])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 2)])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[5], 3)
        self.assertEqual(s0[7][0][9], 3)
        # The interval itself was fine; only R rejects, so pass stays
        # true exactly as op 29 renders it.
        self.assertTrue(s0[6])

    def test_op28_29_gates_still_apply(self):
        t = moved_topo()
        # C gate: the no-failure scenario migrates all demand.
        out, before, after, _ = self.call(
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             999999, 1000000, 1])
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["events"][0][4][3][0][6])
        self.assertEqual(after, before)
        # L gate: shrinking n3->n4 bandwidth to 50 raises the peak 0.4.
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 399999,
             1000000, 1000000, 1])
        self.assertEqual(out["status"], 2)
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 400000,
             1000000, 1000000, 1])
        self.assertEqual(out["status"], 0)
        # Old-side infeasible at h[b] is code 5.
        self.call(
            [30, 0, 0, [[1, t, P]], [flow(mlat=109)], SCENARIOS,
             1000000, 1000000, 1000000, 1], expect_rc=5)

    def test_failure_stops_later_events(self):
        t1, t2 = moved_topo(), base_topo()
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t1, P], [2, t2, P], [3, t1, P]], [flow()],
             SCENARIOS, 1000000, 1000000, 10, 5])
        self.assertEqual(out["status"], 2)
        # Simulation stops at the first failing event: no third row.
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])

    def test_commit_preview_resend_and_idempotent(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            [30, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5])
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        # Exact resend is recognized (status 1) and writes nothing.
        out2, _, after2, tmps2 = self.call(
            [30, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5], pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Same-state event: status 1 row, no write, D/R irrelevant.
        out3, _, after3, _ = self.call(
            [30, 1, 1, [[2, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 0, 0], pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(after3, after2)
        # A failing commit leaves PACK at v=1 and the identical batch
        # fails the same way on retry (failed rollback idempotency).
        fail_batch = [30, 1, 1, [[2, base_topo(), P], [3, t, P]],
                      [flow()], SCENARIOS, 1000000, 1000000, 2, 5]
        out4, _, after4, _ = self.call(fail_batch, pk=pk1)
        self.assertEqual(out4["status"], 2)
        self.assertEqual([out4["old"], out4["new"], out4["applied"]],
                         [1, 1, False])
        self.assertEqual(json.loads(after4)["v"], 1)
        out5, _, after5, _ = self.call(fail_batch, pk=pk1)
        self.assertEqual(out5["status"], 2)
        self.assertEqual(json.loads(after5)["v"], 1)

    def test_byte_deterministic(self):
        t = moved_topo()
        op = [30, 0, 0, [[1, t, P], [2, base_topo(), P]], [flow()],
              SCENARIOS, 1000000, 1000000, 2, 1]
        r1 = self.call_raw(op)
        r2 = self.call_raw(op)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        t = moved_topo()
        good = [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
                1000000, 1, 1]
        self.assertEqual(len(good), 10)
        bad = [
            # wrong arity: the op 29 shape is not accepted as op 30, and
            # one element too many
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1],
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 1, 1],
            # D out of range / boolean / negative / string
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, -1],
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, True],
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1,
             10 ** 18],
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, "1"],
            # R, C and L ranges still enforced
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, -1, 1],
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, True, 1],
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001, 1,
             1],
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000001, 1, 1,
             1],
            # bad mode
            [30, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1],
            # empty E / F / S
            [30, 0, 0, [], [flow()], SCENARIOS, 1, 1, 1, 1],
            [30, 0, 0, [[1, t, P]], [], SCENARIOS, 1, 1, 1, 1],
            [30, 0, 0, [[1, t, P]], [flow()], [], 1, 1, 1, 1],
            # clocks decrease
            [30, 0, 0, [[2, t, P], [1, t, P]], [flow()], SCENARIOS, 1,
             1, 1, 1],
            # invalid scenario reference at h[b]
            [30, 0, 0, [[1, t, P]], [flow()],
             [["q", ["n4"], []]], 1, 1, 1, 1],
            # flow endpoint absent at h[b]
            [30, 0, 0, [[1, t, P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1, 1, 1, 1],
        ]
        for op in bad:
            self.call(op, expect_rc=5)

    def test_stale_base_conflict_code5(self):
        t = moved_topo()
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        other = json.loads(json.dumps(base_topo()))
        other["links"][0]["latency"] = 7
        self.call(
            [30, 1, 0, [[1, other, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 1], pk=pk1, expect_rc=5)

    def test_ops_0_to_29_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        t = moved_topo()
        # op 29 happy path and its 9-arity shape still parse.
        out, _, _, _ = self.call(
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1])
        self.assertEqual(out["op"], 29)
        # op 29's flow row keeps its 10-field shape (no op 30 tail).
        self.assertEqual(len(out["events"][0][4][3][0][7][0]), 10)
        # The op 30 arity must not be accepted as op 29.
        self.call(
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 1], expect_rc=5)

    def test_json_and_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[30,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],"
                                "1,1,1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
