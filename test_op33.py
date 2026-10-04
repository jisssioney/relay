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


# Generous gate defaults except the caller overrides them: R/D/Q open,
# H and U both at the maximum parts-per-million cap.
def op33(events, flows_, h=1000000, u=1000000, w=5, q=10, m=0, b=0,
         l=1000000, c=1000000, r=10, d=0):
    return [33, m, b, events, flows_, SCENARIOS, l, c, r, d, w, q, h, u]


class Op33(unittest.TestCase):
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

    def test_preview_pass_renders_distinct_window_fields(self):
        t = moved_topo()
        out, before, after, tmps = self.call(op33([[1, t, P]], [flow()]))
        # Top-level key order is op 32's exactly.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [33, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 32's 12-element shape with
        # windowDistinctDemand/windowDistinctRatio inserted after
        # windowMovedRatio and before pass.
        s0 = scenarios[0]
        self.assertEqual(len(s0), 14)
        self.assertEqual(s0[0:12],
                         [None, "0.400000", 40, 40, "1.000000", 1, 1,
                          40, "1.000000", 40, "1.000000", True])
        self.assertIs(s0[11], True)
        # Flow row keeps op 31/32's exact 16-element structure.
        f0 = s0[12][0]
        self.assertEqual(len(f0), 16)
        self.assertEqual(f0,
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True, 1,
                          None, None, True, -4, 1, True])
        # x/z did not move: empty windows, both ratios 0, still passing.
        for sx in scenarios[1:]:
            self.assertEqual(sx[6:12],
                             [0, 0, "0.000000", 0, "0.000000", True])
            self.assertEqual(sx[12][0][7], False)

    def test_u_zero_rejects_every_retained_flow_keeps_candidate(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            op33([[1, t, P]], [flow()], h=1000000, u=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        # H admits the 40/40 demand; only the U gate fails.
        self.assertFalse(s0[11])
        self.assertEqual(s0[7:11], [40, "1.000000", 40, "1.000000"])
        fr = s0[12][0]
        # Q admits the candidate; the flow row keeps candidate stats.
        self.assertEqual(fr[14:16], [1, True])
        # Non-moving failure scenarios keep an empty window and pass.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[11])
            self.assertEqual(sx[9:11], [0, "0.000000"])

    def test_u_boundary_cross_multiplication(self):
        # f1 (demand 10) migrates on the no-failure side; f2 (demand
        # 90, n2->n4) never does. windowDistinctDemand/totalDemand =
        # 10/100 = 0.1 regardless of how often f1 later reroutes.
        t = moved_topo()
        f2 = ["f2", "n2", "n4", 90, 110]
        # 10*1000000 = 10000000 > 99999*100 = 9999900 fails ...
        out, _, _, _ = self.call(
            op33([[1, t, P]], [flow(demand=10), f2], h=1000000,
                 u=99999))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[7:11], [10, "0.100000", 10, "0.100000"])
        self.assertFalse(s0[11])
        # ... while U=100000 is exactly 10% and passes.
        out, _, _, _ = self.call(
            op33([[1, t, P]], [flow(demand=10), f2], h=1000000,
                 u=100000))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[7:12],
                         [10, "0.100000", 10, "0.100000", True])
        # The non-migrating f2 keeps an empty window in every scenario.
        for sx in out["events"][0][4][3]:
            self.assertEqual(sx[12][1][14:16], [0, True])

    def test_repeated_reroute_counts_flow_once(self):
        # Same two-flow batch: f1 reroutes at 1 and again at 6, both
        # records retained under W=5, so windowMovedDemand holds 20 but
        # windowDistinctDemand holds f1's 10 exactly once.
        t1, t2 = moved_topo(), base_topo()
        f2 = ["f2", "n2", "n4", 90, 110]
        out, before, after, _ = self.call(
            op33([[1, t1, P], [6, t2, P]],
                 [flow(demand=10), f2], w=5, h=1000000, u=100000))
        self.assertEqual(out["status"], 0)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (6, 0)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[7:11], [20, "0.200000", 10, "0.100000"])
        fr = s0[12][0]
        self.assertEqual(fr[9:16], [2, 1, 5, True, 1, 2, True])

    def test_distinct_demand_vanishes_when_last_record_slides_out(self):
        # f1 moves once at clock 1; event 2 at clock 7 is a different
        # topology that leaves f1 on the same n2 path, so it only slides
        # the window: W=5 makes windowStart=2, clock 1 drops and f1's
        # deque is empty - both window demands return to zero.
        t1 = moved_topo()
        t2 = json.loads(json.dumps(t1))
        t2["links"][0]["latency"] = 11
        f2 = ["f2", "n2", "n4", 90, 110]
        out, _, _, _ = self.call(
            op33([[1, t1, P], [7, t2, P]],
                 [flow(demand=10), f2], w=5, h=1000000, u=100000))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (7, 0)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[7:12],
                         [0, "0.000000", 0, "0.000000", True])
        self.assertEqual(s0[12][0][14:16], [0, True])

    def test_window_is_closed_when_sliding(self):
        t1 = moved_topo()
        f2 = ["f2", "n2", "n4", 90, 110]
        # A non-moving second event only slides the window. At clock 6
        # with W=5 the closed edge 1 keeps clock 1, so f1 stays in the
        # distinct set; with W=4 windowStart=2 drops clock 1 and the
        # distinct demand returns to zero.
        t3 = json.loads(json.dumps(t1))
        t3["links"][0]["latency"] = 11
        out, _, _, _ = self.call(
            op33([[1, t1, P], [6, t3, P]],
                 [flow(demand=10), f2], w=5, h=1000000, u=100000))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[9:12], [10, "0.100000", True])
        self.assertEqual(s0[12][0][13:16], [1, 1, True])
        out2, _, _, _ = self.call(
            op33([[1, t1, P], [6, t3, P]],
                 [flow(demand=10), f2], w=4, h=1000000, u=100000))
        self.assertEqual(out2["status"], 0)
        s0 = out2["events"][1][4][3][0]
        self.assertEqual(s0[7:12],
                         [0, "0.000000", 0, "0.000000", True])
        self.assertEqual(s0[12][0][13:16], [2, 0, True])

    def test_h_gate_still_rejects_independently(self):
        t = moved_topo()
        # U admits everything, but H=0 rejects the first reroute.
        out, before, after, _ = self.call(
            op33([[1, t, P]], [flow()], h=0, u=1000000))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[11])
        self.assertEqual(s0[7:11], [40, "1.000000", 40, "1.000000"])
        # The flow's Q window admitted the reroute.
        self.assertEqual(s0[12][0][15], True)

    def test_q_gate_still_rejects_independently(self):
        t = moved_topo()
        # H and U admit all demand, but Q=0 rejects the first reroute.
        out, before, after, _ = self.call(
            op33([[1, t, P]], [flow()], h=1000000, u=1000000, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[11])
        self.assertEqual(s0[7:11], [40, "1.000000", 40, "1.000000"])
        self.assertEqual(s0[12][0][15], False)

    def test_equal_state_event_adds_no_record(self):
        t1, t2 = moved_topo(), base_topo()
        # move@1, equal-state@2 (status 1, empty impact), move-back@3;
        # W=10 keeps clock 1 with its demand, so H=1000000 rejects the
        # move-back: windowMovedDemand 80 > 40 while the distinct set
        # still holds the one flow for 40. The equal event added no
        # record.
        out, _, _, _ = self.call(
            op33([[1, t1, P], [2, t1, P], [3, t2, P]], [flow()],
                 w=10, h=1000000, u=1000000))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 2)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[7:11], [80, "2.000000", 40, "1.000000"])

    def test_scenarios_never_merge(self):
        # alt event only moves the x/z failure scenarios; their windows
        # stay separate from the no-failure one.
        t = json.loads(json.dumps(base_topo()))
        t["nodes"].append("n5")
        t["links"][2]["cost"] = 2
        t["links"][3]["cost"] = 2
        t["links"].append(link("n0", "n5"))
        t["links"].append(link("n5", "n3"))
        out, _, _, _ = self.call(
            op33([[1, t, P]], [flow()], h=1000000, u=0, q=10))
        self.assertEqual(out["status"], 2)
        scenarios = out["events"][0][4][3]
        # no-failure flow never migrates: empty window, passes U=0.
        self.assertTrue(scenarios[0][11])
        self.assertEqual(scenarios[0][9:11], [0, "0.000000"])
        # x/z each hold their own 40 record and fail U independently.
        for sx in scenarios[1:]:
            self.assertFalse(sx[11])
            self.assertEqual(sx[9:11], [40, "1.000000"])
            self.assertEqual(sx[12][0][14:16], [1, True])

    def test_commit_resend_and_idempotent(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            op33([[1, t, P]], [flow()], h=1000000, u=1000000, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op33([[1, t, P]], [flow()], h=1000000, u=1000000, m=1),
            pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Same-state event: status 1 row, no write even with U=H=Q=0.
        out3, _, after3, _ = self.call(
            op33([[2, t, P]], [flow()], h=0, u=0, q=0, m=1, b=1),
            pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        t1, t2 = moved_topo(), base_topo()
        # The first event would commit; the second doubles the retained
        # moved demand inside W=10 (H=1000000 rejects 80 > 40): mode 1
        # must leave PACK untouched.
        out, before, after, tmps = self.call(
            op33([[1, t1, P], [2, t2, P]], [flow()], w=10,
                 h=1000000, u=1000000, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # A feasible retry is a fresh simulation from h[b] and commits.
        out2, _, after2, _ = self.call(
            op33([[1, t1, P], [8, t2, P]], [flow()], w=5,
                 h=1000000, u=1000000, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        t = moved_topo()
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        other = json.loads(json.dumps(base_topo()))
        other["links"][0]["latency"] = 7
        self.call(
            op33([[6, other, P]], [flow()], h=1000000, u=1000000, m=1),
            pk=pk1, expect_rc=5)

    def test_byte_deterministic(self):
        t = moved_topo()
        op_obj = op33([[1, t, P], [7, base_topo(), P]], [flow()],
                      w=5, h=1000000, u=1000000, r=2)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        t = moved_topo()
        good = op33([[1, t, P]], [flow()])
        self.assertEqual(len(good), 14)
        bad = [
            # wrong arity: op 32's 13-element shape and one too many
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1],
            # U negative / boolean / too large / string / float
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, -1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, True],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1000001],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, "1"],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 0.5],
            # op 32's H/W/Q/R/D/C/L ranges still enforced
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, -1, 1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, True, 1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             -1, 1, 1, 1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, True, 1, 1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, -1, 1,
             1, 1, 1, 1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001, 1,
             1, 1, 1, 1, 1],
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000001, 1, 1,
             1, 1, 1, 1, 1],
            # bad mode
            [33, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1],
            # empty E / F / S
            [33, 0, 0, [], [flow()], SCENARIOS, 1, 1, 1, 1, 1, 1, 1, 1],
            [33, 0, 0, [[1, t, P]], [], SCENARIOS, 1, 1, 1, 1, 1, 1,
             1, 1],
            [33, 0, 0, [[1, t, P]], [flow()], [], 1, 1, 1, 1, 1, 1,
             1, 1],
            # clocks decrease
            [33, 0, 0, [[2, t, P], [1, t, P]], [flow()], SCENARIOS, 1,
             1, 1, 1, 1, 1, 1, 1],
            # invalid scenario reference at h[b]
            [33, 0, 0, [[1, t, P]], [flow()],
             [["q", ["n4"], []]], 1, 1, 1, 1, 1, 1, 1, 1],
            # flow endpoint absent at h[b]
            [33, 0, 0, [[1, t, P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1, 1, 1, 1, 1,
             1, 1, 1],
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)

    def test_ops_0_to_32_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        t = moved_topo()
        # op 32 happy path keeps its 12-field scenario row and 16-field
        # flow row, with no windowDistinctDemand/windowDistinctRatio.
        out, _, _, _ = self.call(
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1, 1000000])
        self.assertEqual(out["op"], 32)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 12)
        self.assertEqual(len(s0[10][0]), 16)
        # op 32's 13-arity shape must not parse as op 33, and op 33's
        # 14-arity shape must not parse as op 32.
        self.call(
            [33, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1, 1000000], expect_rc=5)
        self.call(
            [32, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1, 1000000, 1000000], expect_rc=5)
        # op 31 still parses at its arity.
        out, _, _, _ = self.call(
            [31, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1])
        self.assertEqual(out["op"], 31)

    def test_json_and_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[33,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],"
                                "1,1,1,1,1,1,1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
