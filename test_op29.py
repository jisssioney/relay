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


class Op29(unittest.TestCase):
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

    def test_preview_pass_renders_moves(self):
        t = moved_topo()
        op = [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
              1000000, 1]
        out, before, after, tmps = self.call(op)
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [29, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        e, status, old, new, impact = row
        self.assertEqual([e, status, old, new], [1, 0, 0, 1])
        self.assertEqual(len(impact), 4)
        scenarios = impact[3]
        self.assertEqual(len(scenarios), 3)
        # no-failure row: [sid,peak,movedDemand,totalDemand,movedRatio,
        # maxMoves,pass,flows,links]
        s0 = scenarios[0]
        self.assertEqual(len(s0), 9)
        self.assertEqual(s0[0:7],
                         [None, "0.400000", 40, 40, "1.000000", 1, True])
        f0 = s0[7][0]
        # [id,oldCost,newCost,oldLat,newLat,oldPath,newPath,moved,pass,
        # moves]
        self.assertEqual(f0,
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True, 1])
        # x/z did not move: scenario maxMoves 0 and the flow row's
        # trailing moves 0.
        for sx in scenarios[1:]:
            self.assertEqual(sx[5], 0)
            self.assertTrue(sx[6])
            self.assertEqual(sx[7][0][7], False)
            self.assertEqual(sx[7][0][9], 0)
        self.assertEqual(scenarios[1][0], "x")
        self.assertEqual(scenarios[2][0], "z")

    def test_r_zero_rejects_first_move_but_keeps_impact(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 0])
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 2, 0, 0])
        s0 = row[4][3][0]
        # Candidate counts are the post-event values even on failure.
        self.assertEqual(s0[5], 1)
        self.assertEqual(s0[7][0][9], 1)
        # The op 28 gates themselves all pass; only R rejects.
        self.assertTrue(s0[6])

    def test_flap_back_and_forth_hits_r(self):
        t1 = moved_topo()
        t2 = base_topo()
        out, before, after, _ = self.call(
            [29, 1, 0, [[1, t1, P], [2, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 1])
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"]], [0, 0])
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # First event: no-failure count 1.
        self.assertEqual(out["events"][0][4][3][0][5], 1)
        # Second event flaps back: cumulative 2 in no-failure, still 0
        # in the failure scenarios (their paths never changed).
        s = out["events"][1][4][3]
        self.assertEqual([s[0][5], s[1][5], s[2][5]], [2, 0, 0])
        self.assertEqual(s[0][7][0][9], 2)
        self.assertEqual(s[1][7][0][9], 0)
        # R=2 admits the back-and-forth batch.
        out2, _, _, _ = self.call(
            [29, 0, 0, [[1, t1, P], [2, t2, P]], [flow()], SCENARIOS,
             1000000, 1000000, 2])
        self.assertEqual(out2["status"], 0)
        self.assertEqual([r[1] for r in out2["events"]], [0, 0])
        self.assertEqual(out2["events"][1][4][3][0][5], 2)

    def test_third_flap_exceeds_r_two(self):
        t1, t2 = moved_topo(), base_topo()
        out, before, after, _ = self.call(
            [29, 1, 0, [[1, t1, P], [2, t2, P], [3, t1, P]], [flow()],
             SCENARIOS, 1000000, 1000000, 2])
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 2)])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[5], 3)
        self.assertEqual(s0[7][0][9], 3)

    def test_equal_state_events_do_not_count(self):
        t = moved_topo()
        out, _, after, _ = self.call(
            [29, 1, 0, [[1, t, P], [2, t, P], [3, base_topo(), P]],
             [flow()], SCENARIOS, 1000000, 1000000, 1])
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 2)])
        # The equal-state row keeps the op 28 empty-impact shape.
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        # The final flap back sees cumulative 2 despite the middle
        # equal-state event.
        self.assertEqual(out["events"][2][4][3][0][5], 2)

    def test_scenarios_count_independently(self):
        # Only the failure scenarios reroute; no-failure maxMoves stays
        # 0 while x/z reach 1, so R=0 fails on x/z alone.
        t = alt_topo()
        out, before, after, _ = self.call(
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 0])
        self.assertEqual(out["status"], 2)
        s = out["events"][0][4][3]
        self.assertEqual([row[5] for row in s], [0, 1, 1])
        self.assertTrue(s[0][6])
        self.assertTrue(s[1][6])
        self.assertTrue(s[2][6])
        self.assertEqual(s[0][7][0][7], False)
        self.assertEqual(s[0][7][0][9], 0)
        self.assertEqual(s[1][7][0][7], True)
        self.assertEqual(s[2][7][0][7], True)
        # R=1 admits it.
        out2, _, _, _ = self.call(
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1])
        self.assertEqual(out2["status"], 0)

    def test_per_flow_counts(self):
        # f2 (n3->n4) shares the n3->n4 edge in every routing, so only
        # f1 flaps; the scenario max follows f1 while f2 stays at 0.
        t1, t2 = moved_topo(), base_topo()
        f = [flow(), ["f2", "n3", "n4", 10, 110]]
        out, _, _, _ = self.call(
            [29, 0, 0, [[1, t1, P], [2, t2, P]], f, SCENARIOS,
             1000000, 1000000, 1])
        self.assertEqual(out["status"], 2)
        flows = out["events"][1][4][3][0][7]
        self.assertEqual([row[9] for row in flows], [2, 0])
        self.assertEqual([row[7] for row in flows], [True, False])

    def test_op28_gates_still_apply(self):
        t = moved_topo()
        # C gate: the no-failure scenario migrates all demand.
        out, before, after, _ = self.call(
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             999999, 1000000])
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["events"][0][4][3][0][6])
        self.assertEqual(after, before)
        # L gate: shrinking n3->n4 bandwidth to 50 raises the peak 0.4.
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        out, _, _, _ = self.call(
            [29, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 399999,
             1000000, 1000000])
        self.assertEqual(out["status"], 2)
        out, _, _, _ = self.call(
            [29, 0, 0, [[1, topo1, P]], [flow()], SCENARIOS, 400000,
             1000000, 1000000])
        self.assertEqual(out["status"], 0)
        # Old-side infeasible at h[b] is code 5.
        self.call(
            [29, 0, 0, [[1, t, P]], [flow(mlat=109)], SCENARIOS,
             1000000, 1000000, 1000000], expect_rc=5)

    def test_commit_resend_and_idempotent(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            [29, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1])
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        out2, _, after2, tmps2 = self.call(
            [29, 1, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1], pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Same-state event with R=0: status 1 row, no write.
        out3, _, after3, _ = self.call(
            [29, 1, 1, [[2, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 0], pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(after3, after2)

    def test_byte_deterministic(self):
        t = moved_topo()
        op = [29, 0, 0, [[1, t, P], [2, base_topo(), P]], [flow()],
              SCENARIOS, 1000000, 1000000, 2]
        r1 = self.call_raw(op)
        r2 = self.call_raw(op)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        t = moved_topo()
        good = [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
                1000000, 1]
        self.assertEqual(len(good), 9)
        bad = [
            # wrong arity: op 28 shape accepted nowhere as op 29, and
            # one element too many
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 1],
            # R out of range / boolean / negative / string
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, -1],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, True],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1,
             10 ** 18],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, "1"],
            # C and L ranges still enforced
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001, 1],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000001, 1, 1],
            # bad mode
            [29, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1],
            # empty E / F / S
            [29, 0, 0, [], [flow()], SCENARIOS, 1, 1, 1],
            [29, 0, 0, [[1, t, P]], [], SCENARIOS, 1, 1, 1],
            [29, 0, 0, [[1, t, P]], [flow()], [], 1, 1, 1],
            # clocks decrease
            [29, 0, 0, [[2, t, P], [1, t, P]], [flow()], SCENARIOS, 1,
             1, 1],
            # invalid scenario reference at h[b]
            [29, 0, 0, [[1, t, P]], [flow()],
             [["q", ["n4"], []]], 1, 1, 1],
            # flow endpoint absent at h[b]
            [29, 0, 0, [[1, t, P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1, 1, 1],
        ]
        for op in bad:
            self.call(op, expect_rc=5)

    def test_stale_base_conflict_code5(self):
        t = moved_topo()
        pk1 = pack(t, v=1, history=[[0, base_topo(), P], [1, t, P]])
        other = json.loads(json.dumps(base_topo()))
        other["links"][0]["latency"] = 7
        self.call(
            [29, 1, 0, [[1, other, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1], pk=pk1, expect_rc=5)

    def test_ops_0_to_28_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        t = moved_topo()
        # op 28 happy path and its 8-arity shape still parse.
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000])
        self.assertEqual(out["op"], 28)
        # op 29 arity must not be accepted as op 28.
        self.call(
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1], expect_rc=5)

    def test_json_and_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[29,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],1,1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
