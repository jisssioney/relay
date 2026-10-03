import json
import os
import subprocess
import sys
import tempfile
import unittest

from test_op28 import (P, RELAY, SCENARIOS, base_topo, flow, link,
                       moved_topo, pack)

MAX_COST = 2147483647


def alt_topo():
    # A third route n0 -> n5 -> n3 -> n4 (cost 4, latency 30) joins the
    # two base routes. Under failure x (n1 down) the n2 route wins over
    # n5; raising n2->n3 cost pushes x onto n5.
    t = json.loads(json.dumps(base_topo()))
    t["nodes"].append("n5")
    t["links"].append(link("n0", "n5", cost=2, lat=10))
    t["links"].append(link("n5", "n3", cost=2, lat=10))
    return t


def t_a():
    # n1->n3 cost 2 and n2->n3 cost 4: the no-failure route stays the
    # n1 path (cost 3), while scenario x (n1 down) moves n2 (cost 5)
    # -> n5 (cost 4).
    t = alt_topo()
    t["links"][1]["cost"] = 2
    t["links"][3]["cost"] = 4
    return t


def t_b():
    # n1->n3 cost 2, n2->n3 back to cost 1: no failure moves n1 -> n2
    # (cost 3 beats 4) while scenario x moves n5 -> n2.
    t = alt_topo()
    t["links"][1]["cost"] = 2
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

    def op29(self, events, r, f=None, scenarios=None, mode=0, base=0,
             limit=1000000, moved=1000000):
        return [29, mode, base, events,
                f if f is not None else [flow()],
                scenarios if scenarios is not None else SCENARIOS,
                limit, moved, r]

    def test_preview_render_maxmoves_and_moves(self):
        t = moved_topo()
        out, before, after, tmps = self.call(
            self.op29([[1, t, P]], 1000000))
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
        scenarios = impact[3]
        self.assertEqual(len(scenarios), 3)
        s0 = scenarios[0]
        # [sid, peak, movedDemand, totalDemand, movedRatio, maxMoves,
        #  pass, flows, links]
        self.assertEqual(s0[0:7],
                         [None, "0.400000", 40, 40, "1.000000", 1, True])
        self.assertEqual(len(s0[7][0]), 10)
        self.assertEqual(s0[7][0],
                         ["f1", 3, 3, 30, 110,
                          ["n0", "n1", "n3", "n4"],
                          ["n0", "n2", "n3", "n4"], True, True, 1])
        # failure scenarios never route differently between the two
        # states: maxMoves 0 and each flow's moves 0.
        sx = scenarios[1]
        self.assertEqual(sx[0:7],
                         ["x", "0.400000", 0, 40, "0.000000", 0, True])
        self.assertEqual(sx[7][0][7:10], [False, True, 0])
        sz = scenarios[2]
        self.assertEqual(sz[5], 0)
        self.assertEqual(sz[7][0][9], 0)

    def test_r_breach_on_second_toggle_rejects_atomically(self):
        t1, t2 = moved_topo(), base_topo()
        out, before, after, tmps = self.call(
            self.op29([[1, t1, P], [2, t2, P], [3, t1, P]], 1))
        # simulation stops at the first breaching event: event 3 absent.
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1], r[2], r[3])
                          for r in out["events"]],
                         [(1, 0, 0, 1), (2, 2, 1, 1)])
        impact = out["events"][1][4]
        s0, sx, sz = impact[3]
        self.assertEqual(s0[5], 2)
        self.assertFalse(s0[6])
        self.assertEqual(s0[7][0][8:10], [True, 2])
        # failure scenarios never moved: their counters stay zero.
        self.assertEqual(sx[5], 0)
        self.assertEqual(sx[7][0][9], 0)
        self.assertEqual(sz[5], 0)

    def test_r_equal_to_boundary_passes(self):
        out, _, after, _ = self.call(
            self.op29([[1, moved_topo(), P], [2, base_topo(), P]], 2))
        self.assertEqual(out["status"], 0)
        self.assertEqual([out["old"], out["new"]], [0, 2])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[5], 2)
        self.assertTrue(s0[6])
        self.assertEqual(s0[7][0][9], 2)

    def test_r_zero_accepts_only_equal_state_events(self):
        # a genuine first move already breaches R=0
        out, before, after, _ = self.call(
            self.op29([[1, moved_topo(), P]], 0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        # an equal-state event at h[b] is idempotent under R=0
        out, _, _, _ = self.call(
            self.op29([[5, base_topo(), P]], 0))
        self.assertEqual(out["status"], 0)
        self.assertEqual(out["events"], [[5, 1, 0, 0, []]])

    def test_equal_state_event_does_not_count(self):
        # move, equal event, move back: the equal event freezes the
        # counter, so the third event breaches R=1 with exactly 2 moves.
        t1 = moved_topo()
        out, _, _, _ = self.call(
            self.op29([[1, t1, P], [2, t1, P], [3, base_topo(), P]], 1))
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 2)])
        self.assertEqual(out["events"][1][4], [])
        self.assertEqual(out["events"][2][4][3][0][5], 2)
        # with R=2 the same batch passes entirely.
        out, _, _, _ = self.call(
            self.op29([[1, t1, P], [2, t1, P], [3, base_topo(), P]], 2))
        self.assertEqual(out["status"], 0)

    def test_scenario_counts_are_independent(self):
        # event 1 moves flow f1 only in scenario x; event 2 moves it only
        # in the no-failure scenario and back in x. With R=1 x breaches
        # at event 2 while the no-failure count is just 1.
        out, _, _, _ = self.call(
            self.op29([[1, t_a(), P], [2, t_b(), P]], 1), )
        r1, r2 = out["events"]
        self.assertEqual(r1[1], 0)
        s0_1, sx_1, sz_1 = r1[4][3]
        self.assertEqual(s0_1[5], 0)
        self.assertEqual(sx_1[5], 1)
        self.assertEqual(sx_1[7][0][9], 1)
        self.assertEqual(sx_1[7][0][6],
                         ["n0", "n5", "n3", "n4"])
        self.assertEqual(r2[1], 2)
        s0_2, sx_2, _ = r2[4][3]
        self.assertEqual(s0_2[5], 1)
        self.assertTrue(s0_2[6])
        self.assertEqual(sx_2[5], 2)
        self.assertFalse(sx_2[6])
        self.assertEqual(out["status"], 2)

    def test_stationary_flow_keeps_moves_zero(self):
        f = [flow(), ["f2", "n3", "n4", 10, 110]]
        out, _, _, _ = self.call(
            self.op29([[1, moved_topo(), P], [2, base_topo(), P]], 2,
                      f=f))
        s0 = out["events"][1][4][3][0]
        # maxMoves is the scenario maximum: f1 at 2, f2 stays at 0.
        self.assertEqual(s0[5], 2)
        self.assertEqual([row[9] for row in s0[7]], [2, 0])
        # R=1 rejects on f1 even though f2 never moved.
        out, _, _, _ = self.call(
            self.op29([[1, moved_topo(), P], [2, base_topo(), P]], 1,
                      f=f))
        self.assertEqual(out["status"], 2)

    def test_commit_resend_and_equal_state_idempotent(self):
        t1, t2 = moved_topo(), base_topo()
        events = [[1, t1, P], [2, t2, P]]
        out, before, after, tmps = self.call(
            self.op29(events, 2, mode=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 2])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 2)
        # exact resend against the advanced pack: status 1, no rewrite
        pk2 = pack(t2, v=2,
                   history=[[0, base_topo(), P], [1, t1, P], [2, t2, P]])
        out2, _, after2, tmps2 = self.call(
            self.op29(events, 2, mode=1), pk=pk2)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 2, False])
        self.assertEqual(json.loads(after2)["v"], 2)
        self.assertEqual(tmps2, [])
        # same-state event at v=2: row status 1, [] impact, no rewrite
        out3, _, after3, _ = self.call(
            self.op29([[7, t2, P]], 2, mode=1, base=2), pk=pk2)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[7, 1, 2, 2, []]])
        self.assertEqual(after3, after2)

    def test_unreachable_new_side_moves_zero_and_rejects(self):
        topo3 = {"nodes": ["n0", "n1", "n3", "n4"],
                 "links": [link("n0", "n1", lat=10),
                           link("n1", "n3", lat=10),
                           link("n3", "n4", lat=10)]}
        out, before, after, _ = self.call(
            self.op29([[1, topo3, P]], 1000000))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        sx = out["events"][0][4][3][1]
        self.assertFalse(sx[6])
        self.assertEqual(sx[5], 0)
        # old side routes via n2 (cost 3, latency 110); the new side is
        # unreachable, so its slots are null/[] and no move is counted.
        self.assertEqual(sx[7][0],
                         ["f1", 3, None, 110, None,
                          ["n0", "n2", "n3", "n4"], [], False, False, 0])

    def test_latency_and_c_and_l_gates_still_apply(self):
        # latency violation in scenarios x/z, R generous
        t = json.loads(json.dumps(base_topo()))
        t["links"][2]["latency"] = 51
        t["links"][3]["latency"] = 51
        out, _, _, _ = self.call(
            self.op29([[1, t, P]], 1000000))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["events"][0][4][3][1][6])
        # per-scenario C cap (movedRatio 1.0 > 999999 ppm)
        out, _, _, _ = self.call(
            self.op29([[1, moved_topo(), P]], 1000000, moved=999999))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["events"][0][4][3][0][6])
        # L worst-peak-increase cap
        topo1 = json.loads(json.dumps(base_topo()))
        topo1["links"][4]["bandwidth"] = 50
        out, _, _, _ = self.call(
            self.op29([[1, topo1, P]], 1000000, limit=399999))
        self.assertEqual(out["status"], 2)
        out, _, _, _ = self.call(
            self.op29([[1, topo1, P]], 1000000, limit=400000))
        self.assertEqual(out["status"], 0)

    def test_old_side_infeasible_is_code5(self):
        self.call(self.op29([[1, moved_topo(), P]], 1000000,
                            f=[flow(mlat=109)]), expect_rc=5)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(moved_topo(), v=1,
                   history=[[0, base_topo(), P], [1, moved_topo(), P]])
        other = json.loads(json.dumps(base_topo()))
        other["links"][0]["latency"] = 7
        self.call(self.op29([[1, other, P]], 1, mode=1), pk=pk1,
                  expect_rc=5)

    def test_shape_and_range_code5(self):
        t = moved_topo()
        good = self.op29([[1, t, P]], 1000000)
        self.assertEqual(len(good), 9)
        bad = [
            # op 29 must not accept op 28's 8-arity, and op 28 must not
            # accept op 29's 9-arity
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000],
            [28, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 1],
            # R out of range / boolean / wrong type
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, -1],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, True],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, "1"],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1.0],
            [29, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1,
             MAX_COST + 1],
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

    def test_r_max_cost_accepted(self):
        out, _, _, _ = self.call(
            self.op29([[1, moved_topo(), P]], MAX_COST))
        self.assertEqual(out["status"], 0)

    def test_deterministic_bytes(self):
        payloads = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as d:
                pp = os.path.join(d, "pack.json")
                with open(pp, "w") as f:
                    json.dump(pack(), f)
                r = subprocess.run(
                    [sys.executable, RELAY, "config", pp,
                     json.dumps(self.op29(
                         [[1, moved_topo(), P], [2, base_topo(), P]], 2))],
                    capture_output=True)
                payloads.append(r.stdout)
        self.assertEqual(payloads[0], payloads[1])

    def test_ops_0_to_28_unchanged_smoke(self):
        # op 28's own 8-arity shape still parses and gates exactly as
        # before; a 9-arity array is not op 28.
        out, _, _, _ = self.call(
            [28, 0, 0, [[1, moved_topo(), P]], [flow()], SCENARIOS,
             1000000, 1000000])
        self.assertEqual(out["op"], 28)
        self.assertEqual(out["status"], 0)
        self.call(
            [28, 0, 0, [[1, moved_topo(), P]], [flow()], SCENARIOS,
             1000000, 1000000, 1], expect_rc=5)
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})

    def test_json_and_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[29,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],"
                                "1,1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
