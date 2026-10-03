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


class Op28(unittest.TestCase):
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

    def test_preview_pass_render_and_migration(self):
        t = moved_topo()
        op = [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
              1000000]
        out, before, after, tmps = self.call(op)
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [28, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        e, status, old, new, impact = row
        self.assertEqual([e, status, old, new], [1, 0, 0, 1])
        self.assertEqual(len(impact), 4)
        old_worst, new_worst, delta, scenarios = impact
        # Peaks stay 0.4 on both sides; the no-failure scenario wins
        # the equal-peak tie.
        self.assertEqual(old_worst, [None, "0.400000"])
        self.assertEqual(new_worst, [None, "0.400000"])
        self.assertEqual(delta, "0.000000")
        self.assertEqual(len(scenarios), 3)
        s0 = scenarios[0]
        # [sid, peak, movedDemand, totalDemand, movedRatio, ok, f, l]
        self.assertEqual(s0[0:6],
                         [None, "0.400000", 40, 40, "1.000000", True])
        self.assertEqual(s0[6][0],
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True])
        self.assertEqual(s0[7][4],
                         ["n3", "n4", 100, 40, "0.400000"])
        # scenario x: old and new both on the n2 path -> not moved
        sx = scenarios[1]
        self.assertEqual(sx[0:6],
                         ["x", "0.400000", 0, 40, "0.000000", True])
        self.assertEqual(sx[6][0],
                         ["f1", 3, 3, 110, 110,
                          ["n0", "n2", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], False, True])
        # scenario z likewise
        sz = scenarios[2]
        self.assertEqual(sz[0], "z")
        self.assertEqual(sz[6][0][7], False)

    def test_migration_cap_cross_multiply(self):
        t = moved_topo()
        f = [flow()]
        # movedDemand/totalDemand = 1.0 in the no-failure scenario.
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, t, P]], f, SCENARIOS, 1000000, 999999])
        self.assertEqual(out["status"], 2)
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 2, 0, 0])
        s0 = row[4][3][0]
        self.assertFalse(s0[5])
        # the failure scenarios themselves were still fine
        self.assertTrue(row[4][3][1][5])
        # exactly 1000000 ppm passes
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, t, P]], f, SCENARIOS, 1000000, 1000000])
        self.assertEqual(out["status"], 0)

    def test_migration_ratio_partial_and_threshold(self):
        # f2 stays on the single n3->n4 edge in every scenario, so only
        # f1 migrates: 40 / (40+10) = 0.8.
        t = moved_topo()
        f = [flow(), ["f2", "n3", "n4", 10, 110]]
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, t, P]], f, SCENARIOS, 1000000, 799999])
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[2:5], [40, 50, "0.800000"])
        self.assertEqual(s0[6][1][7], False)
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, t, P]], f, SCENARIOS, 1000000, 800000])
        self.assertEqual(out["status"], 0)

    def test_commit_resend_and_idempotent(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            [28, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000])
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        # exact resend against the advanced pack: status 1, no rewrite
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        out2, _, after2, tmps2 = self.call(
            [28, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000], pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # same-state event: row status 1, [] impact
        out3, _, after3, _ = self.call(
            [28, 1, 1, [[2, t, P]], [flow()], SCENARIOS, 1000000,
             1000000], pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(after3, after2)

    def test_unreachable_new_side_renders_nulls_and_rejects(self):
        # candidate deletes n2; under scenario x (n1 down) n0 cannot
        # reach n3 on the new side while the old side routed via n2.
        topo3 = {"nodes": ["n0", "n1", "n3", "n4"],
                 "links": [link("n0", "n1", lat=10),
                           link("n1", "n3", lat=10),
                           link("n3", "n4", lat=10)]}
        out, before, after, tmps = self.call(
            [28, 1, 0, [[1, topo3, P]], [flow()], SCENARIOS, 1000000,
             1000000])
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        scenarios = out["events"][0][4][3]
        sx = scenarios[1]
        self.assertFalse(sx[5])
        # old side values present, new side null/[]; never "moved"
        self.assertEqual(sx[6][0],
                         ["f1", 3, None, 110, None,
                          ["n0", "n2", "n3", "n4"], [], False, False])
        pairs = [(l[0], l[1]) for l in sx[7]]
        self.assertEqual(pairs,
                         [("n0", "n1"), ("n1", "n3"), ("n3", "n4")])

    def test_latency_violation_fails_gate(self):
        # candidate keeps the same paths but raises the n2-path latency
        # past the budget in scenarios x and z (both forced onto n2).
        t = json.loads(json.dumps(base_topo()))
        t["links"][2]["latency"] = 51
        t["links"][3]["latency"] = 51
        out, before, after, _ = self.call(
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        scenarios = out["events"][0][4][3]
        self.assertTrue(scenarios[0][5])
        self.assertFalse(scenarios[1][5])
        self.assertEqual(scenarios[1][6][0],
                         ["f1", 3, 3, 110, 112,
                          ["n0", "n2", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], False, False])

    def test_utilization_increase_cap_still_applies(self):
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50  # peak 40/50 = 0.8
        f = [flow()]
        # identical paths everywhere -> migration cap trivially met;
        # L=399999 rejects the 0.4 increase, L=400000 passes
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, topo1, P]], f, SCENARIOS, 399999, 1000000])
        self.assertEqual(out["status"], 2)
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, topo1, P]], f, SCENARIOS, 400000, 1000000])
        self.assertEqual(out["status"], 0)

    def test_batch_mid_failure_rejects_atomically(self):
        t1 = moved_topo()                       # passes with C=1.0
        t2 = json.loads(json.dumps(base_topo()))
        t2["links"][2]["latency"] = 51
        t2["links"][3]["latency"] = 51         # x/z latency 112 > 110
        out, before, after, tmps = self.call(
            [28, 1, 0, [[1, t1, P], [2, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000])
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"]], [0, 0])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])

    def test_old_side_infeasible_is_code5(self):
        # h[b] scenario x already violates maxLatency 109 (path 110).
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, moved_topo(), P]], [flow(mlat=109)],
             SCENARIOS, 1000000, 1000000], expect_rc=5)
        self.assertIsNone(out)

    def test_shape_and_range_code5(self):
        t = moved_topo()
        good = [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
                1000000]
        self.assertEqual(len(good), 8)
        bad = [
            # wrong arity (op 27 shape) and one too few/too many
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000],
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1],
            # C out of range / boolean / negative
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001],
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, True],
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, -1],
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, "0"],
            # bad L still code 5
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000001, 1],
            # bad mode
            [28, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1],
            # empty E / F / S
            [28, 0, 0, [], [flow()], SCENARIOS, 1, 1],
            [28, 0, 0, [[1, t, P]], [], SCENARIOS, 1, 1],
            [28, 0, 0, [[1, t, P]], [flow()], [], 1, 1],
            # clocks decrease
            [28, 0, 0, [[2, t, P], [1, t, P]], [flow()], SCENARIOS, 1,
             1],
            # invalid scenario reference at h[b]
            [28, 0, 0, [[1, t, P]], [flow()],
             [["q", ["n4"], []]], 1, 1],
            # flow endpoint absent at h[b]
            [28, 0, 0, [[1, t, P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1, 1],
        ]
        for op in bad:
            self.call(op, expect_rc=5)

    def test_stale_base_conflict_code5(self):
        t = moved_topo()
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        other = json.loads(json.dumps(base_topo()))
        other["links"][0]["latency"] = 7
        self.call(
            [28, 1, 0, [[1, other, P]], [flow()], SCENARIOS, 1000000,
             1000000], pk=pk1, expect_rc=5)

    def test_ops_0_to_27_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 27 happy path and its 7-arity shape still parse
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        out, _, _, _ = self.call(
            [27, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 1000000])
        self.assertEqual(out["op"], 27)
        self.assertEqual(out["status"], 0)
        # op 28 arity must not be accepted as op 27
        self.call(
            [27, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 1000000,
             1000000], expect_rc=5)

    def test_json_and_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[28,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
