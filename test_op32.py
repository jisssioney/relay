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


# Generous gate defaults except the demand window: R/D/Q open.
def op32(events, flows_, h=1000000, w=5, q=10, m=0, b=0,
         l=1000000, c=1000000, r=10, d=0):
    return [32, m, b, events, flows_, SCENARIOS, l, c, r, d, w, q, h]


class Op32(unittest.TestCase):
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

    def test_preview_pass_renders_demand_window_fields(self):
        t = moved_topo()
        out, before, after, tmps = self.call(op32([[1, t, P]], [flow()]))
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [32, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 31's 10-element shape with windowMovedDemand
        # and windowMovedRatio inserted after maxWindowMoves.
        s0 = scenarios[0]
        self.assertEqual(len(s0), 12)
        self.assertEqual(s0[0:10],
                         [None, "0.400000", 40, 40, "1.000000", 1, 1,
                          40, "1.000000", True])
        self.assertIs(s0[9], True)
        # Flow row keeps op 31's exact 16-element structure.
        f0 = s0[10][0]
        self.assertEqual(len(f0), 16)
        self.assertEqual(f0,
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True, 1,
                          None, None, True, -4, 1, True])
        # x/z did not move: no retained demand, ratio 0, still passing.
        for sx in scenarios[1:]:
            self.assertEqual(sx[6:10], [0, 0, "0.000000", True])
            self.assertEqual(sx[10][0][7], False)

    def test_h_zero_rejects_every_reroute_keeps_candidate_stats(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            op32([[1, t, P]], [flow()], h=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        # Q admits the candidate; only the H gate fails the scenario.
        self.assertFalse(s0[9])
        self.assertEqual(s0[7:9], [40, "1.000000"])
        fr = s0[10][0]
        self.assertEqual(fr[14:16], [1, True])
        # Non-moving failure scenarios keep an empty window and pass.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[9])
            self.assertEqual(sx[7:9], [0, "0.000000"])

    def test_h_boundary_cross_multiplication(self):
        # f1 (demand 1) migrates on the no-failure side; f2 (demand 2,
        # n2->n4) never does. windowMovedDemand/totalDemand = 1/3.
        t = moved_topo()
        f2 = ["f2", "n2", "n4", 2, 110]
        # 1000000 <= 333333 * 3 = 999999 fails ...
        out, _, _, _ = self.call(
            op32([[1, t, P]], [flow(demand=1), f2], h=333333))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[7:9], [1, "0.333333"])
        self.assertFalse(s0[9])
        # ... while 333334 passes (exact six-decimal rendering kept).
        out, _, _, _ = self.call(
            op32([[1, t, P]], [flow(demand=1), f2], h=333334))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[7:10], [1, "0.333333", True])
        # The non-migrating f2 keeps an empty window in every scenario.
        for sx in out["events"][0][4][3]:
            self.assertEqual(sx[10][1][14:16], [0, True])

    def test_repeated_migration_counts_demand_each_time(self):
        t1, t2 = moved_topo(), base_topo()
        # move@1 and move-back@6 inside the closed W=5 window: both
        # records retained, windowMovedDemand 40+40=80 against a total
        # of 40, so even H=1000000 rejects the second event.
        out, before, after, _ = self.call(
            op32([[1, t1, P], [6, t2, P]], [flow()], w=5, h=1000000))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (6, 2)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[6:9], [2, 80, "2.000000"])
        fr = s0[10][0]
        # Q/D are open: only the demand window fails; candidate stats
        # retained.
        self.assertEqual(fr[9:16], [2, 1, 5, True, 1, 2, True])
        # At clock 7 the closed lower edge e-W=2 drops clock 1, leaving
        # only the candidate's 40: the batch passes.
        out2, _, _, _ = self.call(
            op32([[1, t1, P], [7, t2, P]], [flow()], w=5, h=1000000))
        self.assertEqual(out2["status"], 0)
        s0 = out2["events"][1][4][3][0]
        self.assertEqual(s0[7:10], [40, "1.000000", True])
        self.assertEqual(s0[10][0][14:16], [1, True])

    def test_window_is_closed_when_sliding(self):
        t1, t2 = moved_topo(), base_topo()
        # @6 with W=4: windowStart=2 drops clock 1, only the candidate
        # remains. With W=5 the closed edge 1 keeps clock 1 and fails.
        out, _, _, _ = self.call(
            op32([[1, t1, P], [6, t2, P]], [flow()], w=5, h=1000000))
        self.assertEqual(out["status"], 2)
        out2, _, _, _ = self.call(
            op32([[1, t1, P], [6, t2, P]], [flow()], w=4, h=1000000))
        self.assertEqual(out2["status"], 0)
        self.assertEqual(
            out2["events"][1][4][3][0][10][0][13:16], [2, 1, True])

    def test_q_gate_still_rejects_independently(self):
        t = moved_topo()
        # H admits all demand, but Q=0 rejects the first reroute.
        out, before, after, _ = self.call(
            op32([[1, t, P]], [flow()], h=1000000, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[9])
        self.assertEqual(s0[7:9], [40, "1.000000"])
        self.assertEqual(s0[10][0][15], False)

    def test_equal_state_event_adds_no_record(self):
        t1, t2 = moved_topo(), base_topo()
        # move@1, equal-state@2 (status 1, empty impact), move-back@3;
        # W=10 keeps clock 1 with its demand, so H=1000000 rejects the
        # move-back: 80 > 40. The equal event added no record.
        out, _, _, _ = self.call(
            op32([[1, t1, P], [2, t1, P], [3, t2, P]], [flow()],
                 w=10, h=1000000))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 2)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[7:9], [80, "2.000000"])

    def test_scenarios_never_merge(self):
        # alt event only moves the x/z failure scenarios; their windows
        # stay separate from the no-failure one.
        t = json.loads(json.dumps(base_topo()))
        t["nodes"].append("n5")
        t["links"][2]["cost"] = 2
        t["links"][3]["cost"] = 2
        t["links"].append(link("n0", "n5"))
        t["links"].append(link("n5", "n3"))
        out, _, _, _ = self.call(op32([[1, t, P]], [flow()], h=0, q=10))
        self.assertEqual(out["status"], 2)
        scenarios = out["events"][0][4][3]
        # no-failure flow never migrates: empty window, passes H=0.
        self.assertTrue(scenarios[0][9])
        self.assertEqual(scenarios[0][7:9], [0, "0.000000"])
        # x/z each hold their own 40 record and fail H independently.
        for sx in scenarios[1:]:
            self.assertFalse(sx[9])
            self.assertEqual(sx[7:9], [40, "1.000000"])
            self.assertEqual(sx[10][0][14:16], [1, True])

    def test_commit_resend_and_idempotent(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            op32([[1, t, P]], [flow()], h=1000000, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op32([[1, t, P]], [flow()], h=1000000, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Same-state event: status 1 row, no write even with H=Q=0.
        out3, _, after3, _ = self.call(
            op32([[2, t, P]], [flow()], h=0, q=0, m=1, b=1), pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        t1, t2 = moved_topo(), base_topo()
        # The first event would commit; the second doubles the retained
        # moved demand inside W=10: mode 1 must leave PACK untouched.
        out, before, after, tmps = self.call(
            op32([[1, t1, P], [2, t2, P]], [flow()], w=10, h=1000000,
                 m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # A feasible retry is a fresh simulation from h[b] and commits.
        out2, _, after2, _ = self.call(
            op32([[1, t1, P], [8, t2, P]], [flow()], w=5, h=1000000,
                 m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        t = moved_topo()
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        other = json.loads(json.dumps(base_topo()))
        other["links"][0]["latency"] = 7
        self.call(
            op32([[6, other, P]], [flow()], h=1000000, m=1),
            pk=pk1, expect_rc=5)

    def test_byte_deterministic(self):
        t = moved_topo()
        op_obj = op32([[1, t, P], [7, base_topo(), P]], [flow()],
                      w=5, h=1000000, r=2)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        t = moved_topo()
        good = op32([[1, t, P]], [flow()])
        self.assertEqual(len(good), 13)
        bad = [
            # wrong arity: op 31's 12-element shape and one too many
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1],
            # H negative / boolean / too large / string / float
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, -1],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, True],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1000001],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, "1"],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 0.5],
            # op 31's W/Q/R/D/C/L ranges still enforced
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             -1, 1, 1],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, True, 1],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, -1, 1,
             1, 1, 1],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001, 1,
             1, 1, 1, 1],
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000001, 1, 1,
             1, 1, 1, 1],
            # bad mode
            [32, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1],
            # empty E / F / S
            [32, 0, 0, [], [flow()], SCENARIOS, 1, 1, 1, 1, 1, 1, 1],
            [32, 0, 0, [[1, t, P]], [], SCENARIOS, 1, 1, 1, 1, 1, 1, 1],
            [32, 0, 0, [[1, t, P]], [flow()], [], 1, 1, 1, 1, 1, 1, 1],
            # clocks decrease
            [32, 0, 0, [[2, t, P], [1, t, P]], [flow()], SCENARIOS, 1,
             1, 1, 1, 1, 1, 1],
            # invalid scenario reference at h[b]
            [32, 0, 0, [[1, t, P]], [flow()],
             [["q", ["n4"], []]], 1, 1, 1, 1, 1, 1, 1],
            # flow endpoint absent at h[b]
            [32, 0, 0, [[1, t, P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1, 1, 1, 1, 1,
             1, 1],
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)

    def test_ops_0_to_31_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        t = moved_topo()
        # op 31 happy path keeps its 10-field scenario row and 16-field
        # flow row, with no windowMovedDemand/windowMovedRatio.
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1])
        self.assertEqual(out["op"], 31)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 10)
        self.assertEqual(len(s0[8][0]), 16)
        # op 32's 13-arity shape must not parse as op 31.
        self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1, 1], expect_rc=5)
        # op 30 still parses at its arity.
        out, _, _, _ = self.call(
            [30, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5])
        self.assertEqual(out["op"], 30)

    def test_json_and_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[32,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],"
                                "1,1,1,1,1,1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
