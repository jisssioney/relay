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


class Op27(unittest.TestCase):
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

    def test_preview_pass_render_and_key_order(self):
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50  # peak 40/50 = 0.8
        op = [27, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 1000000]
        out, before, after, tmps = self.call(op)
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [27, 0, 0, 0, 1, False])
        self.assertEqual(after, before)  # preview writes nothing
        self.assertEqual(tmps, [])
        row = out["events"][0]
        e, status, old, new, impact = row
        self.assertEqual([e, status, old, new], [1, 0, 0, 1])
        self.assertEqual(len(impact), 4)
        old_worst, new_worst, delta, scenarios = impact
        self.assertEqual(old_worst, [None, "0.400000"])
        self.assertEqual(new_worst, [None, "0.800000"])
        self.assertEqual(delta, "+0.400000")
        self.assertEqual(len(scenarios), 3)  # no-failure, x, z
        # no-failure scenario
        s0 = scenarios[0]
        sid, peak, ok, flows, links = s0
        self.assertEqual([sid, peak, ok], [None, "0.800000", True])
        self.assertEqual(flows[0],
                         ["f1", 3, 30, 110,
                          ["n0", "n1", "n3", "n4"], True])
        self.assertEqual(links[4],
                         ["n3", "n4", 50, 40, "0.800000"])
        # scenario x: node n1 down -> via n2, latency 51? no, 50+50+10
        sx = scenarios[1]
        self.assertEqual(sx[0], "x")
        self.assertEqual(sx[1], "0.800000")
        self.assertTrue(sx[2])
        self.assertEqual(sx[3][0],
                         ["f1", 3, 110, 110,
                          ["n0", "n2", "n3", "n4"], True])
        # links incident on n1 still listed with used zero
        by_pair = {(l[0], l[1]): l for l in sx[4]}
        self.assertEqual(by_pair[("n0", "n1")][3:], [0, "0.000000"])
        self.assertEqual(by_pair[("n1", "n3")][3:], [0, "0.000000"])
        # scenario z: explicit directed link n0->n1 removed
        sz = scenarios[2]
        self.assertEqual(sz[0], "z")
        self.assertEqual(sz[3][0][4], ["n0", "n2", "n3", "n4"])
        self.assertEqual(sz[3][0][2], 110)

    def test_commit_then_resend_and_idempotent(self):
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        op1 = [27, 1, 0, [[1, topo1, P]], [flow()], SCENARIOS, 1000000]
        out, before, after, tmps = self.call(op1)
        self.assertTrue(out["applied"])
        self.assertEqual(out["status"], 0)
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        saved = json.loads(after)
        self.assertEqual(saved["v"], 1)
        # exact resend against the advanced pack: status 1, no rewrite
        pk1 = pack(topo1, v=1, history=[[0, base_topo(), P],
                                        [1, topo1, P]])
        out2, _, after2, tmps2 = self.call(
            [27, 1, 0, [[1, topo1, P]], [flow()], SCENARIOS, 1000000],
            pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # idempotent event (same t/p as current): row status 1, [] impact
        out3, _, after3, _ = self.call(
            [27, 1, 1, [[2, topo1, P]], [flow()], SCENARIOS, 1000000],
            pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(after3, after2)  # neither call rewrote PACK

    def test_latency_violation_fails_gate(self):
        topo2 = json.loads(json.dumps(base_topo()))
        topo2["links"][2]["latency"] = 51
        topo2["links"][3]["latency"] = 51
        # x scenario now routes n0-n2-n3-n4 = 112 > maxLatency 110
        op = [27, 1, 0, [[1, topo2, P]], [flow()], SCENARIOS, 1000000]
        out, before, after, tmps = self.call(op)
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 2, 0, 0])
        scenarios = row[4][3]
        self.assertTrue(scenarios[0][2])          # no-failure still fine
        self.assertFalse(scenarios[1][2])         # x violates latency
        fx = scenarios[1][3][0]
        self.assertEqual(fx, ["f1", 3, 112, 110,
                              ["n0", "n2", "n3", "n4"], False])
        # z shares the forced n2 path: 112 > 110 too
        self.assertFalse(scenarios[2][2])
        self.assertEqual(scenarios[2][3][0],
                         ["f1", 3, 112, 110,
                          ["n0", "n2", "n3", "n4"], False])

    def test_unreachable_renders_null_row_and_rejects(self):
        # candidate deletes n2; under scenario x (n1 down) n0 cannot
        # reach n3 at all
        topo3 = {"nodes": ["n0", "n1", "n3", "n4"],
                 "links": [link("n0", "n1", lat=10),
                           link("n1", "n3", lat=10),
                           link("n3", "n4", lat=10)]}
        op = [27, 1, 0, [[1, topo3, P]], [flow()], SCENARIOS, 1000000]
        out, before, after, tmps = self.call(op)
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        scenarios = out["events"][0][4][3]
        self.assertFalse(scenarios[1][2])
        self.assertEqual(scenarios[1][3][0],
                         ["f1", None, None, 110, [], False])
        # topology-order links of the candidate side; n2 links gone
        pairs = [(l[0], l[1]) for l in scenarios[1][4]]
        self.assertEqual(pairs,
                         [("n0", "n1"), ("n1", "n3"), ("n3", "n4")])

    def test_overload_fails_gate(self):
        topo4 = json.loads(json.dumps(base_topo()))
        topo4["links"][4]["bandwidth"] = 30  # demand 40 overloads n3->n4
        op = [27, 1, 0, [[1, topo4, P]], [flow()], SCENARIOS, 1000000]
        out, before, after, tmps = self.call(op)
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertFalse(out["events"][0][4][3][0][2])

    def test_utilization_increase_cap_cross_multiply(self):
        # 40/100 = 0.4 old; candidate 40/50 = 0.8 new; increase 0.4
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        f = [flow()]
        out, _, _, _ = self.call(
            [27, 0, 0, [[1, topo1, P]], f, SCENARIOS, 399999])
        self.assertEqual(out["status"], 2)
        out, _, _, _ = self.call(
            [27, 0, 0, [[1, topo1, P]], f, SCENARIOS, 400000])
        self.assertEqual(out["status"], 0)

    def test_old_side_infeasible_is_code5(self):
        # maxLatency 109 already violated at h[b] scenario x (path 110)
        out, _, _, _ = self.call(
            [27, 0, 0, [[1, base_topo(), P]], [flow(mlat=109)],
             SCENARIOS, 1000000], expect_rc=5)
        self.assertIsNone(out)

    def test_shape_and_range_code5(self):
        good = [27, 0, 0, [[1, base_topo(), P]], [flow()], SCENARIOS,
                1000000]
        bad = [
            [27, 2, 0, [[1, base_topo(), P]], [flow()], SCENARIOS, 1],
            [27, 0, 0, [[1, base_topo(), P]], [flow()], SCENARIOS,
             1000001],
            [27, 0, 0, [], [flow()], SCENARIOS, 1],
            [27, 0, 0, [[1, base_topo(), P]], [], SCENARIOS, 1],
            [27, 0, 0, [[1, base_topo(), P]],
             [["f1", "n0", "n4", 40, -1]], SCENARIOS, 1],
            [27, 0, 0, [[1, base_topo(), P]],
             [["f1", "n0", "n4", 40, True]], SCENARIOS, 1],
            [27, 0, 0, [[1, base_topo(), P]],
             [["f1", "n0", "n4", 40, 2147483648]], SCENARIOS, 1],
            [27, 0, 0, [[1, base_topo(), P]],
             [["f1", "n0", "n0", 40, 110]], SCENARIOS, 1],
            [27, 0, 0, [[1, base_topo(), P]], [flow()], [], 1],
            # scenario references an endpoint node n4
            [27, 0, 0, [[1, base_topo(), P]], [flow()],
             [["q", ["n4"], []]], 1],
            # unknown explicit failure link
            [27, 0, 0, [[1, base_topo(), P]], [flow()],
             [["q", [], [["n0", "n4"]]]], 1],
            # duplicate failure sets across scenarios
            [27, 0, 0, [[1, base_topo(), P]], [flow()],
             [["a", ["n1"], []], ["b", ["n1"], []]], 1],
            # flow endpoint absent at h[b]
            [27, 0, 0, [[1, base_topo(), P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1],
            # clocks decrease
            [27, 0, 0, [[2, base_topo(), P], [1, base_topo(), P]],
             [flow()], SCENARIOS, 1],
            # wrong arity
            [27, 0, 0, [[1, base_topo(), P]], [flow()], SCENARIOS],
        ]
        for op in bad:
            self.call(op, expect_rc=5)

    def test_stale_base_conflict_code5(self):
        topo1 = json.loads(json.dumps(base_topo()))
        pk1 = pack(topo1, v=1, history=[[0, base_topo(), P],
                                        [1, topo1, P]])
        # base 0 with a *different* suffix than history already holds
        topo_other = json.loads(json.dumps(base_topo()))
        topo_other["links"][0]["latency"] = 7
        self.call(
            [27, 1, 0, [[1, topo_other, P]], [flow()], SCENARIOS,
             1000000], pk=pk1, expect_rc=5)

    def test_deleted_scenario_reference_still_routes(self):
        # scenario y fails n2; the candidate deletes n2 and its links
        # (a referenced object simply unavailable), flow still reaches
        # via n1 in both no-failure and y scenarios
        topo3 = {"nodes": ["n0", "n1", "n3", "n4"],
                 "links": [link("n0", "n1", lat=10),
                           link("n1", "n3", lat=10),
                           link("n3", "n4", lat=10)]}
        op = [27, 0, 0, [[1, topo3, P]], [flow()],
               [["y", ["n2"], []]], 1000000]
        out, _, _, _ = self.call(op)
        self.assertEqual(out["status"], 0)
        scenarios = out["events"][0][4][3]
        self.assertEqual(len(scenarios), 2)
        self.assertTrue(scenarios[1][2])
        self.assertEqual(scenarios[1][3][0][4],
                         ["n0", "n1", "n3", "n4"])

    def test_batch_two_passing_events_and_mid_failure(self):
        t1 = json.loads(json.dumps(base_topo()))
        t1["links"][4]["bandwidth"] = 50   # peak 0.8
        t2 = json.loads(json.dumps(t1))
        t2["links"][4]["bandwidth"] = 80   # peak 0.5; old worst 0.8
        op = [27, 1, 0, [[1, t1, P], [2, t2, P]], [flow(mlat=110)],
              SCENARIOS, 1000000]
        out, before, after, tmps = self.call(op)
        self.assertEqual(out["status"], 0)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 2, True])
        statuses = [(r[0], r[1], r[2], r[3]) for r in out["events"]]
        self.assertEqual(statuses, [(1, 0, 0, 1), (2, 0, 1, 2)])
        saved = json.loads(after)
        self.assertEqual(saved["v"], 2)
        self.assertEqual(saved["h"][1][1], t1)
        self.assertEqual(saved["h"][2][1], t2)
        # a later failing event stops simulation and keeps pre-call pack
        t3 = json.loads(json.dumps(t2))
        t3["links"][2]["latency"] = 51
        t3["links"][3]["latency"] = 51     # scenario x/z latency 112
        op_bad = [27, 1, 0,
                  [[1, t1, P], [2, t2, P], [3, t3, P]],
                  [flow()], SCENARIOS, 1000000]
        out2, before2, after2, tmps2 = self.call(op_bad)
        self.assertEqual(out2["status"], 2)
        self.assertEqual([out2["old"], out2["new"]], [0, 0])
        self.assertEqual(after2, before2)
        self.assertEqual(tmps2, [])
        rows = out2["events"]
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [(1, 0), (2, 0), (3, 2)])

    def test_integer_latency_sum_rendered(self):
        # A candidate lowers the chosen n1 path's link latencies to
        # 1+2+4: the rendered flow latency is the exact integer sum 7
        # (base scenario x already needs an 110 budget, so mlat=110
        # keeps h[b] feasible).
        t = json.loads(json.dumps(base_topo()))
        t["links"][0]["latency"] = 1
        t["links"][1]["latency"] = 2
        t["links"][4]["latency"] = 4
        out, _, _, _ = self.call(
            [27, 0, 0, [[1, t, P]], [flow(mlat=110)],
             [["x", ["n1"], []]], 1000000])
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[3][0][:3], ["f1", 3, 7])
        self.assertEqual(s0[3][0][5], True)
        # scenario x forces the n2 path: 50+50+4 = 104
        self.assertEqual(out["events"][0][4][3][1][3][0][2], 104)

    def test_no_failure_scenario_latency_event_failure(self):
        # Raising the n1-path latencies keeps cost ties (so the n1
        # sequence still wins the Unicode tie) but pushes no-failure
        # latency to 60+60+10=130 > 111; h[b] (30/110) is feasible,
        # so this is an events-row status 2 rather than code 5.
        t = json.loads(json.dumps(base_topo()))
        t["links"][0]["latency"] = 60
        t["links"][1]["latency"] = 60
        out, before, after, tmps = self.call(
            [27, 1, 0, [[1, t, P]], [flow(mlat=111)],
             [["x", ["n1"], []]], 1000000])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        scenarios = out["events"][0][4][3]
        self.assertFalse(scenarios[0][2])
        self.assertEqual(scenarios[0][3][0],
                         ["f1", 3, 130, 111,
                          ["n0", "n1", "n3", "n4"], False])
        self.assertTrue(scenarios[1][2])      # n2 path still 110
        self.assertEqual(scenarios[1][3][0][2], 110)

    def test_json_and_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[27,0,0,[[1,{},[0]]],[['f','a','b',1,1]],"
                                "[['s',[],[]]],1]"], capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)

    def test_ops_0_to_26_unchanged_smoke(self):
        # op 2 audit and op 26 happy path still behave.
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        f26 = ["f1", "n0", "n4", 40]
        out, _, _, _ = self.call(
            [26, 0, 0, [[1, topo1, P]], [f26], SCENARIOS, 1000000])
        self.assertEqual(out["op"], 26)
        self.assertEqual(out["status"], 0)
        self.assertEqual(out["events"][0][4][3][0][3][0],
                         ["f1", 3, ["n0", "n1", "n3", "n4"]])


if __name__ == "__main__":
    unittest.main()
