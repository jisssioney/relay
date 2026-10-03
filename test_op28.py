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

    def op(self, mode, topo, flows=None, scn=None, L=1000000, C=1000000,
           e=1, b=0):
        return [28, mode, b, [[e, topo, P]],
                flows if flows is not None else [flow()],
                scn if scn is not None else SCENARIOS, L, C]

    def reroute_topo(self):
        # Raising n0->n1 cost pushes no-failure f1 onto the n2 path
        # (old n0,n1,n3,n4 -> new n0,n2,n3,n4); under x/z f1 already
        # used n2, so it does not move there.
        t = json.loads(json.dumps(base_topo()))
        t["links"][0]["cost"] = 5
        t["links"][4]["bandwidth"] = 50  # peak 40/50 = 0.8
        return t

    def test_preview_pass_render_and_key_order(self):
        topo1 = self.reroute_topo()
        out, before, after, tmps = self.call(self.op(0, topo1))
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [28, 0, 0, 0, 1, False])
        self.assertEqual(after, before)  # preview writes nothing
        self.assertEqual(tmps, [])
        e, status, old, new, impact = out["events"][0]
        self.assertEqual([e, status, old, new], [1, 0, 0, 1])
        self.assertEqual(len(impact), 4)
        old_worst, new_worst, delta, scenarios = impact
        self.assertEqual(old_worst, [None, "0.400000"])
        self.assertEqual(new_worst, [None, "0.800000"])
        self.assertEqual(delta, "+0.400000")
        self.assertEqual(len(scenarios), 3)  # no-failure, x, z
        # no-failure scenario: the flow migrated n1 -> n2
        s0 = scenarios[0]
        sid, peak, moved_d, total_d, ratio, ok, flows, links = s0
        self.assertEqual([sid, peak, moved_d, total_d, ratio, ok],
                         [None, "0.800000", 40, 40, "1.000000", True])
        self.assertEqual(flows[0],
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True])
        self.assertEqual(links[4], ["n3", "n4", 50, 40, "0.800000"])
        # scenario x: forced n2 path on both sides -> not a migration
        sx = scenarios[1]
        self.assertEqual([sx[0], sx[2], sx[3], sx[4], sx[5]],
                         ["x", 0, 40, "0.000000", True])
        self.assertEqual(sx[6][0],
                         ["f1", 3, 3, 110, 110,
                          ["n0", "n2", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], False, True])
        # links incident on n1 still listed with used zero
        by_pair = {(l[0], l[1]): l for l in sx[7]}
        self.assertEqual(by_pair[("n0", "n1")][3:], [0, "0.000000"])
        self.assertEqual(by_pair[("n1", "n3")][3:], [0, "0.000000"])
        # scenario z shares the forced n2 path: also no migration
        sz = scenarios[2]
        self.assertEqual(sz[0], "z")
        self.assertEqual(sz[2], 0)
        self.assertFalse(sz[6][0][7])

    def test_commit_then_resend_and_idempotent(self):
        topo1 = self.reroute_topo()
        out, before, after, tmps = self.call(self.op(1, topo1))
        self.assertTrue(out["applied"])
        self.assertEqual(out["status"], 0)
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        saved = json.loads(after)
        self.assertEqual(saved["v"], 1)
        # exact resend against the advanced pack: status 1, no rewrite
        pk1 = pack(topo1, v=1, history=[[0, base_topo(), P],
                                        [1, topo1, P]])
        out2, _, after2, tmps2 = self.call(self.op(1, topo1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # idempotent event (same t/p as current): row status 1, [] impact
        out3, _, after3, _ = self.call(self.op(1, topo1, e=2, b=1),
                                       pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(after3, after2)

    def test_migration_cap_zero_rejects_reroute(self):
        # The no-failure flow moves 40 of 40: any C < 1000000 rejects,
        # exactly at C = 1000000 the integer comparison is an equality.
        topo1 = self.reroute_topo()
        out, before, after, tmps = self.call(self.op(1, topo1, C=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[5])
        self.assertEqual([s0[2], s0[3], s0[4]],
                         [40, 40, "1.000000"])
        # moved still renders true and the per-flow latency pass true:
        # the only violated gate is the migration cap
        self.assertTrue(s0[6][0][7])
        self.assertTrue(s0[6][0][8])
        # scenario x does not move and stays pass on its own
        self.assertTrue(out["events"][0][4][3][1][5])
        out, _, _, _ = self.call(self.op(0, topo1, C=999999))
        self.assertEqual(out["status"], 2)
        out, _, _, _ = self.call(self.op(0, topo1, C=1000000))
        self.assertEqual(out["status"], 0)

    def test_migration_cap_partial_share_cross_multiply(self):
        # f1 (demand 30, n0->n4) migrates n1 -> n2 in the no-failure
        # scenario; f2 (demand 70, n0->n2) keeps its direct path in
        # every scenario. movedDemand/totalDemand = 30/100 = 0.3.
        topo1 = self.reroute_topo()
        flows = [flow("f1", demand=30),
                 ["f2", "n0", "n2", 70, 110]]
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, topo1, P]], flows, SCENARIOS, 1000000,
             299999])
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertEqual([s0[2], s0[3], s0[4]],
                         [30, 100, "0.300000"])
        self.assertFalse(s0[5])
        rows = {r[0]: r for r in s0[6]}
        self.assertTrue(rows["f1"][7])
        self.assertFalse(rows["f2"][7])
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, topo1, P]], flows, SCENARIOS, 1000000,
             300000])
        self.assertEqual(out["status"], 0)

    def test_migration_cap_only_named_scenario_moves(self):
        # Candidate keeps the no-failure n1 path but adds a cheaper
        # n0->n5->n3 detour that wins only once n1 has failed: with
        # C = 0 the no-failure scenario passes (movedDemand 0) and the
        # named x scenario fails (movedDemand 40), and no utilization
        # peak moves either (L = 0).
        t = json.loads(json.dumps(base_topo()))
        t["links"][2]["cost"] = 3   # n0 -> n2
        t["links"][3]["cost"] = 3   # n2 -> n3
        t["nodes"].append("n5")
        t["links"].insert(4, link("n0", "n5", cost=2, lat=10))
        t["links"].insert(5, link("n5", "n3", cost=2, lat=10))
        scn = [["x", ["n1"], []]]
        out, before, after, tmps = self.call(
            [28, 1, 0, [[1, t, P]], [flow()], scn, 0, 0])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        scenarios = out["events"][0][4][3]
        s0, sx = scenarios
        self.assertTrue(s0[5])
        self.assertEqual([s0[2], s0[4]], [0, "0.000000"])
        self.assertEqual(s0[6][0][5], ["n0", "n1", "n3", "n4"])
        self.assertEqual(s0[6][0][6], ["n0", "n1", "n3", "n4"])
        self.assertFalse(s0[6][0][7])
        self.assertFalse(sx[5])
        self.assertEqual([sx[2], sx[3], sx[4]],
                         [40, 40, "1.000000"])
        self.assertEqual(sx[6][0][5], ["n0", "n2", "n3", "n4"])
        self.assertEqual(sx[6][0][6], ["n0", "n5", "n3", "n4"])
        self.assertEqual([sx[6][0][3], sx[6][0][4]], [110, 30])
        self.assertTrue(sx[6][0][7])
        # allowing the migration clears the gate with L still 0
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, t, P]], [flow()], scn, 0, 1000000])
        self.assertEqual(out["status"], 0)

    def test_latency_violation_fails_gate(self):
        t = json.loads(json.dumps(base_topo()))
        t["links"][2]["latency"] = 51
        t["links"][3]["latency"] = 51
        out, before, after, tmps = self.call(self.op(1, t))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        scenarios = out["events"][0][4][3]
        self.assertTrue(scenarios[0][5])          # no-failure still fine
        self.assertFalse(scenarios[1][5])         # x violates latency
        fx = scenarios[1][6][0]
        self.assertEqual(fx, ["f1", 3, 3, 110, 112,
                              ["n0", "n2", "n3", "n4"],
                              ["n0", "n2", "n3", "n4"], False, False])
        self.assertFalse(scenarios[2][5])

    def test_unreachable_renders_null_row_and_rejects(self):
        t = {"nodes": ["n0", "n1", "n3", "n4"],
             "links": [link("n0", "n1", lat=10),
                       link("n1", "n3", lat=10),
                       link("n3", "n4", lat=10)]}
        op = [28, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
              1000000]
        out, before, after, tmps = self.call(op)
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        sx = out["events"][0][4][3][1]
        self.assertFalse(sx[5])
        # old side forced n2; new side has no path at all: no migration
        self.assertEqual(sx[6][0],
                         ["f1", 3, None, 110, None,
                          ["n0", "n2", "n3", "n4"], [], False, False])
        pairs = [(l[0], l[1]) for l in sx[7]]
        self.assertEqual(pairs,
                         [("n0", "n1"), ("n1", "n3"), ("n3", "n4")])

    def test_overload_fails_gate(self):
        t = json.loads(json.dumps(base_topo()))
        t["links"][4]["bandwidth"] = 30
        out, before, after, _ = self.call(self.op(1, t))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertFalse(out["events"][0][4][3][0][5])

    def test_utilization_increase_cap_cross_multiply(self):
        topo1 = self.reroute_topo()
        f = [flow()]
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, topo1, P]], f, SCENARIOS, 399999, 1000000])
        self.assertEqual(out["status"], 2)
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, topo1, P]], f, SCENARIOS, 400000, 1000000])
        self.assertEqual(out["status"], 0)

    def test_old_side_infeasible_is_code5(self):
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, base_topo(), P]], [flow(mlat=109)],
             SCENARIOS, 1000000, 1000000], expect_rc=5)
        self.assertIsNone(out)

    def test_shape_and_range_code5(self):
        t = base_topo()
        good = [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
                1000000]
        self.call(good)
        bad = [
            # bad mode
            [28, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1],
            # C out of range
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001],
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, -1],
            # C a boolean
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, True],
            # L a boolean
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, True, 1],
            # wrong arity: op 27 shape (no C) and one field too many
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1],
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1],
            # empty E / F / S inherited from op 27
            [28, 0, 0, [], [flow()], SCENARIOS, 1, 1],
            [28, 0, 0, [[1, t, P]], [], SCENARIOS, 1, 1],
            [28, 0, 0, [[1, t, P]], [flow()], [], 1, 1],
            # bad flow maxLatency / endpoint
            [28, 0, 0, [[1, t, P]],
             [["f1", "n0", "n4", 40, -1]], SCENARIOS, 1, 1],
            [28, 0, 0, [[1, t, P]],
             [["f1", "n0", "n4", 40, True]], SCENARIOS, 1, 1],
            [28, 0, 0, [[1, t, P]],
             [["f1", "n0", "n0", 40, 110]], SCENARIOS, 1, 1],
            # scenario references an endpoint node n4
            [28, 0, 0, [[1, t, P]], [flow()],
             [["q", ["n4"], []]], 1, 1],
            # unknown explicit failure link
            [28, 0, 0, [[1, t, P]], [flow()],
             [["q", [], [["n0", "n4"]]]], 1, 1],
            # duplicate failure sets across scenarios
            [28, 0, 0, [[1, t, P]], [flow()],
             [["a", ["n1"], []], ["b", ["n1"], []]], 1, 1],
            # flow endpoint absent at h[b]
            [28, 0, 0, [[1, t, P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1, 1],
            # clocks decrease
            [28, 0, 0, [[2, t, P], [1, t, P]],
             [flow()], SCENARIOS, 1, 1],
        ]
        for op in bad:
            self.call(op, expect_rc=5)

    def test_stale_base_conflict_code5(self):
        topo1 = self.reroute_topo()
        pk1 = pack(topo1, v=1, history=[[0, base_topo(), P],
                                        [1, topo1, P]])
        other = json.loads(json.dumps(base_topo()))
        other["links"][0]["latency"] = 7
        self.call(
            [28, 1, 0, [[1, other, P]], [flow()], SCENARIOS,
             1000000, 1000000], pk=pk1, expect_rc=5)

    def test_deleted_scenario_reference_still_routes(self):
        t = {"nodes": ["n0", "n1", "n3", "n4"],
             "links": [link("n0", "n1", lat=10),
                       link("n1", "n3", lat=10),
                       link("n3", "n4", lat=10)]}
        op = [28, 0, 0, [[1, t, P]], [flow()],
               [["y", ["n2"], []]], 1000000, 1000000]
        out, _, _, _ = self.call(op)
        self.assertEqual(out["status"], 0)
        scenarios = out["events"][0][4][3]
        self.assertEqual(len(scenarios), 2)
        self.assertTrue(scenarios[1][5])
        self.assertEqual(scenarios[1][6][0][6],
                         ["n0", "n1", "n3", "n4"])

    def test_batch_two_passing_events_and_mid_failure(self):
        # Events 1 and 2 change n3->n4 bandwidth only (peak 0.8 then
        # 0.5): paths never change, so no scenario migrates. Event 3
        # adds a cheap direct n0->n3 hop and reroutes the no-failure
        # flow, which C = 0 rejects at event 3 only.
        t1 = json.loads(json.dumps(base_topo()))
        t1["links"][4]["bandwidth"] = 50
        t2 = json.loads(json.dumps(t1))
        t2["links"][4]["bandwidth"] = 80            # peak 0.5
        op = [28, 1, 0, [[1, t1, P], [2, t2, P]], [flow()],
              SCENARIOS, 1000000, 1000000]
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
        # second event changes bandwidth only: paths identical, no
        # migration in any scenario
        self.assertEqual(
            [s[2] for s in out["events"][1][4][3]],
            [0, 0, 0])
        # a later event adds a cheap direct n0->n3 hop, forcing a fresh
        # no-failure reroute; with C = 0 the migration cap rejects the
        # batch and keeps the pre-call pack
        t3 = json.loads(json.dumps(t2))
        t3["links"].insert(4, link("n0", "n3", cost=1, lat=10))
        op_bad = [28, 1, 0, [[1, t1, P], [2, t2, P], [3, t3, P]],
                  [flow()], SCENARIOS, 1000000, 0]
        out2, before2, after2, tmps2 = self.call(op_bad)
        self.assertEqual(out2["status"], 2)
        self.assertEqual([out2["old"], out2["new"]], [0, 0])
        self.assertEqual(after2, before2)
        self.assertEqual(tmps2, [])
        rows = out2["events"]
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [(1, 0), (2, 0), (3, 2)])

    def test_idempotent_event_ignores_migration_cap(self):
        # An event equal to the current state is status 1 with an empty
        # impact even when C = 0 would reject any actual reroute.
        t = base_topo()
        pk1 = pack(t, v=1, history=[[0, t, P], [1, t, P]])
        out, _, after, _ = self.call(
            [28, 1, 1, [[2, t, P]], [flow()], SCENARIOS, 0, 0], pk=pk1)
        self.assertEqual(out["status"], 0)
        self.assertEqual(out["events"], [[2, 1, 1, 1, []]])

    def test_integer_latency_sum_rendered(self):
        t = json.loads(json.dumps(base_topo()))
        t["links"][0]["latency"] = 1
        t["links"][1]["latency"] = 2
        t["links"][4]["latency"] = 4
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, t, P]], [flow(mlat=110)],
             [["x", ["n1"], []]], 1000000, 1000000])
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        # No-failure keeps the n1 path: old latency is the base sum
        # 10+10+10=30, the new (candidate) sum 1+2+4=7, same path so
        # moved is false.
        self.assertEqual(s0[6][0][:5], ["f1", 3, 3, 30, 7])
        self.assertEqual(s0[6][0][7], False)
        self.assertEqual(s0[6][0][8], True)
        # scenario x forces n2 on both sides: old 50+50+10=110, new
        # 50+50+4=104, same node path so moved stays false
        sx_row = out["events"][0][4][3][1][6][0]
        self.assertEqual(sx_row[3:5], [110, 104])
        self.assertEqual(sx_row[7], False)

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

    def test_ops_0_to_27_unchanged_smoke(self):
        # op 2 audit and op 27 happy path still behave.
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        out, _, _, _ = self.call(
            [27, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 1000000])
        self.assertEqual(out["op"], 27)
        self.assertEqual(out["status"], 0)
        self.assertEqual(out["events"][0][4][3][0][3][0],
                         ["f1", 3, 30, 110,
                          ["n0", "n1", "n3", "n4"], True])


if __name__ == "__main__":
    unittest.main()
