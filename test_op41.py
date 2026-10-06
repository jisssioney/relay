import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RELAY = os.path.join(HERE, "relay.py")

P = [0, 0, 0, 0, 0, 0]
MAX_TIME = 9223372036854775807
MAX_COST = 2147483647


def link(frm, to, cost=1, bw=10000, lat=10, up=True):
    return {"from": frm, "to": to, "cost": cost, "bandwidth": bw,
            "latency": lat, "up": up}


def cdiv_topo(sb=1, cdcost=3):
    # s -> d has two routes; both carry latency 20 but different COSTS:
    # via b costs 2 (s-b 1 + b-d 1) while via c costs 1 + cdcost (4 by
    # default). Raising s-b to 9 pushes onto c and changes the complete
    # path with a latency swing of 0 but a cost swing of 2. An isolated
    # n5 -> n6 link carries a stationary flow that only pads total
    # demand.
    return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "d"),
                      link("s", "c"), link("c", "d", cost=cdcost),
                      link("n5", "n6")]}


# T_A picks via b (cost 2, latency 20); T_B raises s-b so via c (cost
# 4, latency 20) wins: one migration with cost swing 2 and latency
# swing 0.
T_A = cdiv_topo()
T_B = cdiv_topo(sb=9)

# Failure of b already forced c at T_A (cost 4 both sides, no move) and
# failure of c keeps the b path on both sides of T_B (its cost changes
# but the complete path does not), so neither failure scenario ever
# migrates and both keep cost swing 0.
SCENARIOS = [["x", ["b"], []], ["z", ["c"], []]]

FLOWS = [["f1", "s", "d", 1, 1000],
         ["f2", "n5", "n6", 999, 1000]]


# An equal-cost forced migration: the direct [s,d] link ties the
# two-hop [s,r,d] path on cost 2 and wins the lexicographic tie;
# raising the direct link to 3 moves onto [s,r,d] with cost swing 0.
def zcost_topo(sdcost=2):
    return {"nodes": ["s", "r", "d", "z0", "z1"],
            "links": [link("s", "d", sdcost, lat=20),
                      link("s", "r", 1, lat=10), link("r", "d", 1, lat=10),
                      link("z0", "z1")]}


Z_A = zcost_topo()
Z_B = zcost_topo(sdcost=3)
Z_SCN = [["g", ["r"], []]]
Z_FLOWS = [["f1", "s", "d", 1, 1000],
           ["f2", "z0", "z1", 999, 1000]]


def dtop(crd=1, sdcost=9):
    # Two-hop [s,r,d] (cost 2) competing with a costly direct [s,d]
    # link (cost 9). Raising r-d pushes onto the direct link: last hop
    # r -> s, a cost swing of 7 with zero latency swing.
    return {"nodes": ["s", "r", "d", "z0", "z1"],
            "links": [link("s", "d", sdcost, lat=20),
                      link("s", "r", 1, lat=10),
                      link("r", "d", crd, lat=10),
                      link("z0", "z1")]}


D0 = dtop()
D1 = dtop(9)
D_FLOWS = [["g1", "s", "d", 1, 1000],
           ["g2", "z0", "z1", 999, 1000]]
D_SCN = [["g", ["r"], []]]


def pack(topo=None, v=0, history=None):
    topo = topo or T_A
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


def op41(events, flows_=None, scenarios=None, t=10, g=100, k=10, j=10,
         z=10, y=10, x=10, w=5, q=10, m=0, b=0, h=1000000, u=1000000,
         n=1000000, l=1000000, c=1000000, r=10, d=0):
    flows_ = FLOWS if flows_ is None else flows_
    return [41, m, b, events,
            flows_, SCENARIOS if scenarios is None else scenarios,
            l, c, r, d, w, q, h, u, n, x, y, z, j, k, g, t]


class Op41(unittest.TestCase):
    def call(self, op_obj, pk=None, expect_rc=0):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            with open(pp, "rb") as fh:
                before = fh.read()
            run = subprocess.run([sys.executable, RELAY, "config", pp,
                                  json.dumps(op_obj)], capture_output=True,
                                 text=True)
            self.assertEqual(run.returncode, expect_rc,
                             "rc=%s err=%s out=%s"
                             % (run.returncode, run.stderr, run.stdout))
            out = json.loads(run.stdout) if run.stdout else None
            with open(pp, "rb") as fh:
                after = fh.read()
            tmps = [name for name in os.listdir(d) if ".tmp." in name]
            return out, before, after, tmps

    def call_raw(self, op_obj=None, pk=None, raw_text=None):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            text = raw_text if raw_text is not None else json.dumps(op_obj)
            return subprocess.run([sys.executable, RELAY, "config", pp,
                                   text], capture_output=True)

    # ----------------------------------------------------------------
    # Rendering / field positions
    # ----------------------------------------------------------------
    def test_preview_pass_renders_cost_swing_fields(self):
        out, before, after, tmps = self.call(op41([[1, T_B, P]], t=100))
        # Top-level key order unchanged from op 40.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [41, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 40's 22-element shape with
        # maxWindowCostSwing inserted after maxWindowLatencySwing and
        # before pass (23 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 23)
        self.assertEqual(s0[17], 1)             # maxWindowDistinctLastHops
        self.assertEqual(s0[18], 0)             # maxWindowLatencySwing
        self.assertEqual(s0[19], 2)             # maxWindowCostSwing
        self.assertIs(s0[20], True)             # pass
        # Flow row gains windowMaxCostSwing / costSwingPass after
        # latencySwingPass and before nexthopDiversityPass: 30 fields.
        f0 = s0[21][0]
        self.assertEqual(len(f0), 30)
        self.assertEqual(f0,
                         ["f1", 2, 4, 20, 20,
                          ["s", "b", "d"], ["s", "c", "d"], True, True,
                          1, None, None, True, -4, 1, True,
                          1, 2, 1, 1, 1, True,
                          0, True, 2, True, True, True, True, True])
        # The stationary f2 keeps every window empty: cost swing 0.
        self.assertEqual(f0[24], 2)
        self.assertEqual(s0[21][1][24:30],
                         [0, True, True, True, True, True])
        # Failure scenarios do not migrate: their cost windows stay
        # empty and their rows still pass.
        for sx in scenarios[1:]:
            self.assertEqual(sx[18], 0)
            self.assertEqual(sx[19], 0)
            self.assertIs(sx[20], True)
            self.assertIs(sx[21][0][7], False)
            self.assertEqual(sx[21][0][24:30],
                             [0, True, True, True, True, True])

    # ----------------------------------------------------------------
    # T = 0 accepts only zero-swing records / empty windows
    # ----------------------------------------------------------------
    def test_t_zero_rejects_first_cost_swing_keeps_candidate(self):
        out, before, after, tmps = self.call(
            op41([[1, T_B, P]], g=0, t=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[19], 2)             # candidate cost swing
        self.assertFalse(s0[20])
        fr = s0[21][0]
        # Candidate post-event values retained: the 2 cost swing, T
        # failed; the latency gate (swing 0) and every other flag pass.
        self.assertEqual(fr[1], 2)
        self.assertEqual(fr[2], 4)
        self.assertEqual(fr[22:30],
                         [0, True, 2, False, True, True, True, True])
        # Failure scenarios never moved and still pass.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[20])
            self.assertEqual(sx[19], 0)

    def test_t_is_inclusive_at_the_boundary(self):
        # A 2 cost swing passes T = 2 but fails T = 1.
        out, _, _, _ = self.call(op41([[1, T_B, P]], t=2))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[19], 2)
        self.assertTrue(s0[20])
        out, _, _, _ = self.call(op41([[1, T_B, P]], t=1))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[19], 2)
        self.assertFalse(s0[20])

    def test_zero_cost_swing_reroute_passes_t_zero(self):
        # A migration between equal-cost paths records cost swing 0 and
        # so passes T = 0 even though the path, links, first hop, and
        # last hop all change.
        out, _, _, _ = self.call(
            op41([[1, Z_B, P]], t=0, g=0, scenarios=Z_SCN,
                 flows_=Z_FLOWS),
            pk=pack(Z_A))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        f0 = s0[21][0]
        self.assertIs(f0[7], True)
        self.assertEqual(f0[1], 2)
        self.assertEqual(f0[2], 2)
        self.assertEqual(f0[22], 0)             # zero latency swing
        self.assertEqual(f0[24], 0)             # zero cost swing
        self.assertIs(f0[25], True)             # T = 0 admits it
        self.assertEqual(s0[19], 0)
        self.assertTrue(s0[20])

    # ----------------------------------------------------------------
    # The T gate genuinely diverges from the G (latency) gate
    # ----------------------------------------------------------------
    def test_cost_gate_independent_of_latency_gate(self):
        # One reroute [s,r,d] -> [s,d] keeps latency 20 on both paths
        # (latency swing 0, G = 0 passes) but the cost jumps 2 -> 9, a
        # cost swing of 7 that T = 6 rejects.
        op_one = [41, 0, 0, [[1, D1, P]], D_FLOWS, D_SCN,
                  1000000, 1000000, 10, 0, 100, 10, 1000000, 1000000,
                  1000000, 10, 10, 10, 10, 10, 0, 6]
        out, before, after, _ = self.call(op_one, pk=pack(D0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        f0 = s0[21][0]
        self.assertEqual(f0[5], ["s", "r", "d"])
        self.assertEqual(f0[6], ["s", "d"])
        self.assertIs(f0[7], True)
        self.assertEqual(f0[22], 0)             # latency swing 0
        self.assertIs(f0[23], True)             # G = 0 passes
        self.assertEqual(f0[24], 7)             # cost swing 7
        self.assertIs(f0[25], False)            # T = 6 fails
        self.assertEqual(s0[18], 0)
        self.assertEqual(s0[19], 7)
        self.assertFalse(s0[20])
        # Giving T room admits the same event.
        op_pass = list(op_one)
        op_pass[21] = 7
        out, _, _, _ = self.call(op_pass, pk=pack(D0))
        self.assertEqual(out["status"], 0)

    def test_latency_gate_still_rejects_independently(self):
        # Use op40's unequal-latency diamond (cost swing 0 there because
        # both paths cost 2): T = 0 passes while G = 0 fails.
        def ldiv(sb=1, cdlat=25):
            return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
                    "links": [link("s", "b", sb), link("b", "d"),
                              link("s", "c"), link("c", "d", lat=cdlat),
                              link("n5", "n6")]}

        la, lb = ldiv(), ldiv(sb=9)
        out, before, after, _ = self.call(
            op41([[1, lb, P]], g=0, t=0), pk=pack(la))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        f0 = s0[21][0]
        self.assertEqual(f0[22], 15)            # latency swing 15
        self.assertIs(f0[23], False)            # G fails
        self.assertEqual(f0[24], 0)             # costs equal
        self.assertIs(f0[25], True)             # T passes

    # ----------------------------------------------------------------
    # The window keeps the MAX, never a sum, and slides closed
    # ----------------------------------------------------------------
    def test_window_keeps_max_not_sum(self):
        # Three branches b/c/h with path costs 2/4/7: event 1 moves
        # b -> c (swing 2) and event 2 moves c -> h (swing 3). With
        # W=100 both records are retained, so the window maximum grows
        # 2 -> 3 (never their sum 5). T = 2 admits event 1 but stops at
        # event 2; T = 3 admits the whole batch. The lone scenario
        # fails an isolated node w, so the flow routes exactly as in the
        # no-failure scenario.
        def tri(sb=1, sc=1):
            return {"nodes": ["s", "b", "c", "h", "d", "w", "n5", "n6"],
                    "links": [link("s", "b", sb), link("b", "d"),
                              link("s", "c", sc), link("c", "d", cost=3),
                              link("s", "h"), link("h", "d", cost=6),
                              link("n5", "n6")]}

        m0, m1, m2 = tri(), tri(sb=9), tri(sb=9, sc=9)
        scn = [["q", ["w"], []]]
        events = [[1, m1, P], [2, m2, P]]
        out, before, after, _ = self.call(
            op41(events, t=3, w=100, scenarios=scn), pk=pack(m0))
        self.assertEqual(out["status"], 0)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0)])
        s1 = out["events"][0][4][3][0]
        self.assertEqual(s1[19], 2)             # after event 1
        s2 = out["events"][1][4][3][0]
        f0 = s2[21][0]
        self.assertEqual(f0[14], 2)             # two retained reroutes
        self.assertEqual(s2[19], 3)             # max(2, 3), not 5
        self.assertTrue(s2[20])
        out, _, _, _ = self.call(
            op41(events, t=2, w=100, scenarios=scn), pk=pack(m0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s2 = out["events"][1][4][3][0]
        self.assertEqual(s2[19], 3)
        self.assertFalse(s2[20])

    def test_cost_window_is_closed_when_sliding(self):
        # One reroute (cost swing 2) at clock 1, then a quiet event at
        # clock 2 that moves nothing. W = 1 keeps clock 1 on the closed
        # edge e-W so the 2 survives into event 2, while W = 0 drops it
        # and the window is empty at event 2.
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][4]["latency"] = 11
        events = [[1, T_B, P], [2, t_quiet, P]]
        out, _, _, _ = self.call(op41(events, t=2, w=1))
        self.assertEqual(out["status"], 0)
        s1 = out["events"][1][4][3][0]
        self.assertIs(s1[21][0][7], False)
        self.assertEqual(s1[19], 2)
        self.assertTrue(s1[20])
        out, _, _, _ = self.call(op41(events, t=2, w=0))
        self.assertEqual(out["status"], 0)
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[19], 0)
        self.assertTrue(s1[20])

    def test_max_queue_front_slides_with_old_maximum(self):
        # Three branches b/c/h (path costs 2/7/9): cost swings 5 @ 1
        # (b -> c) then 2 @ 2 (c -> h); a quiet event 3 with W = 1 trims
        # clock 1 strictly below 3-1 = 2, so the old maximum 5 leaves
        # and the retained maximum falls to 2 - exercising the
        # monotonic max queue's front eviction, not a stale max.
        nodes = ["s", "b", "c", "h", "d", "w", "n5", "n6"]

        def topo(sb=1, sc=1):
            return {"nodes": nodes,
                    "links": [link("s", "b", sb), link("b", "d"),
                              link("s", "c", sc), link("c", "d", cost=6),
                              link("s", "h"), link("h", "d", cost=8),
                              link("n5", "n6")]}

        m0, m1, m2 = topo(), topo(sb=9), topo(sb=9, sc=9)
        m3 = json.loads(json.dumps(m2))
        m3["links"][6]["latency"] = 11
        events = [[1, m1, P], [2, m2, P], [3, m3, P]]
        out, _, _, _ = self.call(
            op41(events, t=5, w=1, scenarios=[["q", ["w"], []]]),
            pk=pack(m0))
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0)])
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[19], 5)             # max(5, 2)
        s2 = out["events"][2][4][3][0]
        self.assertEqual(s2[19], 2)             # 5 slid out, 2 stays
        self.assertTrue(s2[20])

    # ----------------------------------------------------------------
    # Predicate exclusions
    # ----------------------------------------------------------------
    def test_equal_state_and_unchanged_path_add_no_record(self):
        # Event 2 is equal state (status 1, empty impact); event 3
        # changes only the isolated n5->n6 latency, so nothing appends
        # and the earlier cost window still slides normally.
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][4]["latency"] = 11
        out, _, _, _ = self.call(
            op41([[1, T_B, P], [2, T_B, P], [3, t_quiet, P]],
                 t=100, w=100))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s2 = out["events"][2][4][3][0]
        self.assertEqual(s2[19], 2)
        f0 = s2[21][0]
        self.assertIs(f0[7], False)
        self.assertEqual(f0[24:30], [2, True, True, True, True, True])

    def test_unreachable_migration_adds_no_record(self):
        # The candidate side drops both s-branches: f1 is unreachable,
        # no reroute, so no cost-swing record even though the event
        # fails (and the batch stops) on reachability.
        t_dead = {"nodes": T_A["nodes"],
                  "links": [lk for lk in T_A["links"]
                            if (lk["from"], lk["to"])
                            not in (("s", "b"), ("s", "c"))]}
        out, before, after, _ = self.call(op41([[1, t_dead, P]], t=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[20])
        f0 = s0[21][0]
        self.assertEqual(f0[6], [])             # unreachable new side
        self.assertIs(f0[7], False)
        self.assertEqual(f0[24], 0)             # no cost-swing record
        self.assertIs(f0[25], True)             # T itself does not fail

    def test_cost_change_without_path_change_adds_no_record(self):
        # Scenario z fails c; the flow stays on [s,b,d] across the
        # event even though s-b's cost rises, so the path is unchanged
        # and no cost-swing record is appended there despite the cost
        # difference.
        out, _, _, _ = self.call(op41([[1, T_B, P]], t=0))
        self.assertEqual(out["status"], 2)      # no-failure scenario
        rows = out["events"][0][4][3]
        sz = rows[2]
        self.assertEqual(sz[0], "z")
        self.assertTrue(sz[20])
        f0 = sz[21][0]
        self.assertIs(f0[7], False)
        self.assertEqual(f0[24], 0)
        self.assertEqual(f0[25], True)

    # ----------------------------------------------------------------
    # No merging across scenarios or flows
    # ----------------------------------------------------------------
    def test_scenarios_never_merge(self):
        # Only the no-failure scenario migrates (b -> c, cost swing 2);
        # in x b was already failed onto c and in z c failed keeps b, so
        # their cost windows stay empty.
        out, _, _, _ = self.call(op41([[1, T_B, P]], t=0))
        s0, sx, sz = out["events"][0][4][3]
        self.assertFalse(s0[20])
        self.assertEqual(s0[21][0][24:30],
                         [2, False, True, True, True, True])
        for other in (sx, sz):
            self.assertTrue(other[20])
            self.assertEqual(other[19], 0)
            self.assertEqual(other[21][0][24:30],
                             [0, True, True, True, True, True])

    def test_flows_never_merge(self):
        # Two independently migrating flows on disjoint diamonds with
        # cost swings 3 and 5, plus a stationary demand-999 flow. Over cb
        # then ca each flow keeps its own two equal records; the
        # scenario maxWindowCostSwing is max(3, 5) = 5, never the merged
        # sum 8 or either flow's sum.
        two = [["f1", "s", "d", 1, 1000],
               ["f3", "n0", "d2", 1, 1000],
               ["f4", "n5", "n6", 999, 1000]]

        def combo(sb=1, n0b=1):
            nodes = ["s", "b", "c", "d",
                     "n0", "b2", "c2", "d2", "n5", "n6"]
            return {"nodes": nodes,
                    "links": [link("s", "b", sb), link("b", "d"),
                              link("s", "c"), link("c", "d", cost=4),
                              link("n0", "b2", n0b), link("b2", "d2"),
                              link("n0", "c2"),
                              link("c2", "d2", cost=6),
                              link("n5", "n6")]}

        ca, cb = combo(), combo(sb=9, n0b=9)
        events = [[1, cb, P], [2, ca, P]]
        out, _, _, _ = self.call(
            op41(events, flows_=two, scenarios=[["x", ["b"], []]],
                 t=5, w=100), pk=pack(ca))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        f1, f3, f4 = s0[21]
        self.assertEqual(f1[24], 3)
        self.assertEqual(f3[24], 5)
        self.assertEqual(f4[24], 0)
        self.assertEqual(s0[19], 5)             # max, not sum/merge
        # T = 4 rejects on f3's 5 at the very first event.
        out, _, _, _ = self.call(
            op41(events, flows_=two, scenarios=[["x", ["b"], []]],
                 t=4, w=100), pk=pack(ca))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[19], 5)
        self.assertFalse(s0[20])

    # ----------------------------------------------------------------
    # Op 40's other gates still reject independently
    # ----------------------------------------------------------------
    def test_k_gate_still_rejects_independently(self):
        # The equal-cost migration has cost swing 0 (T = 0 passes) but
        # still changes the last hop, so K = 0 rejects on its own.
        out, before, after, _ = self.call(
            op41([[1, Z_B, P]], t=0, g=0, k=0, scenarios=Z_SCN,
                 flows_=Z_FLOWS),
            pk=pack(Z_A))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[20])
        f0 = s0[21][0]
        self.assertIs(f0[21], False)            # K fails
        self.assertEqual(f0[24], 0)
        self.assertIs(f0[25], True)             # T passes

    def test_q_gate_still_rejects_independently(self):
        # T admits the 2 cost swing, but Q = 0 rejects the first
        # reroute.
        out, before, after, _ = self.call(
            op41([[1, T_B, P]], t=100, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[20])
        f0 = s0[21][0]
        self.assertIs(f0[15], False)            # windowPass fails
        # Candidate record still appended; cost swing rendered and all
        # diversity flags read true on the failed row.
        self.assertEqual(f0[22:30],
                         [0, True, 2, True, True, True, True, True])

    # ----------------------------------------------------------------
    # Commit / resend / rollback semantics
    # ----------------------------------------------------------------
    def test_commit_resend_and_idempotent(self):
        out, before, after, tmps = self.call(
            op41([[1, T_B, P]], t=100, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op41([[1, T_B, P]], t=100, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Equal-state event: status 0, no write even with every cap 0.
        out3, _, after3, _ = self.call(
            op41([[2, T_B, P]], t=0, g=0, k=0, j=0, z=0, y=0, x=0,
                 q=0, n=0, m=1, b=1),
            pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        # Three branches b/c/h (path costs 2/4/7): event 1 migrates
        # b -> c with a 2 cost swing (T = 2 admits); event 2 migrates
        # c -> h with a 3 cost swing so the retained window max grows
        # to 3 and T = 2 fails the second event - mode 1 leaves PACK
        # untouched and stops at once.
        def tri(sb=1, sc=1):
            return {"nodes": ["s", "b", "c", "h", "d", "w", "n5", "n6"],
                    "links": [link("s", "b", sb), link("b", "d"),
                              link("s", "c", sc), link("c", "d", cost=3),
                              link("s", "h"), link("h", "d", cost=6),
                              link("n5", "n6")]}

        m0, m1, m2 = tri(), tri(sb=9), tri(sb=9, sc=9)
        events = [[1, m1, P], [2, m2, P]]
        out, before, after, tmps = self.call(
            op41(events, t=2, w=100, m=1,
                 scenarios=[["q", ["w"], []]]),
            pk=pack(m0))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s1 = out["events"][1][4][3][0]
        self.assertEqual(s1[19], 3)
        self.assertFalse(s1[20])
        # A feasible retry (T = 3) commits from the same base.
        out2, _, after2, _ = self.call(
            op41(events, t=3, w=100, m=1,
                 scenarios=[["q", ["w"], []]]),
            pk=pack(m0))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        other = json.loads(json.dumps(T_A))
        other["links"][4]["latency"] = 7
        self.call(op41([[6, other, P]], t=100, m=1), pk=pk1,
                  expect_rc=5)

    # ----------------------------------------------------------------
    # Determinism / error codes / backward compatibility
    # ----------------------------------------------------------------
    def test_byte_deterministic(self):
        op_obj = op41([[1, T_B, P], [2, T_A, P]], t=3, w=100)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)
        # Exactly one trailing newline, compact UTF-8 JSON.
        self.assertTrue(r1.stdout.endswith(b"\n"))
        self.assertFalse(r1.stdout.endswith(b"\n\n"))
        self.assertNotIn(b", ", r1.stdout)
        self.assertNotIn(b": ", r1.stdout)

    def test_unparseable_json_code4(self):
        run = self.call_raw(raw_text="{not json")
        self.assertEqual(run.returncode, 4)

    def test_pack_read_error_code3(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "absent.json")
            run = subprocess.run(
                [sys.executable, RELAY, "config", missing,
                 json.dumps(op41([[1, T_B, P]]))], capture_output=True)
            self.assertEqual(run.returncode, 3)

    def test_unknown_command_and_argc_code2(self):
        run = subprocess.run([sys.executable, RELAY, "frobnicate"],
                             capture_output=True)
        self.assertEqual(run.returncode, 2)
        # config with a missing OP argument also keeps code 2.
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pack(), f)
            run = subprocess.run(
                [sys.executable, RELAY, "config", pp],
                capture_output=True)
            self.assertEqual(run.returncode, 2)

    def test_shape_and_range_code5(self):
        good = op41([[1, T_B, P]])
        self.assertEqual(len(good), 22)
        tail16 = [1] * 16
        bad = [
            # wrong arity: op 40's 21-element shape and one too many
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 17,
            # op 40 must not accept op 41's 22 elements and vice versa
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 16,
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            # T negative / boolean / too large / string / float
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True],
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
             MAX_TIME + 1],
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, "1"],
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5],
            # op 40's G range still enforced inside op 41 (G max is
            # MAX_COST, not MAX_TIME)
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1],
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
             MAX_COST + 1, 1],
            # bad mode
            [41, 2, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + tail16,
            # empty E / F / S
            [41, 0, 0, [], FLOWS, SCENARIOS] + tail16,
            [41, 0, 0, [[1, T_B, P]], [], SCENARIOS] + tail16,
            [41, 0, 0, [[1, T_B, P]], FLOWS, []] + tail16,
            # clocks decrease
            [41, 0, 0, [[2, T_B, P], [1, T_B, P]], FLOWS,
             SCENARIOS] + tail16,
            # invalid scenario reference at h[b]
            [41, 0, 0, [[1, T_B, P]], FLOWS,
             [["q", ["d"], []]]] + tail16,
            # flow endpoint absent at h[b]
            [41, 0, 0, [[1, T_B, P]],
             [["g", "s", "n9", 1, 1000]], SCENARIOS] + tail16,
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)
        # T = MAX_TIME is accepted; G = MAX_COST is accepted.
        self.call(op41([[1, T_B, P]], t=MAX_TIME, g=MAX_COST))

    def test_ops_0_to_40_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 40 keeps its 22-field scenario row and 28-field flow row,
        # with no cost-swing fields.
        out, _, _, _ = self.call(
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10, 10, 10, 10, 100])
        self.assertEqual(out["op"], 40)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 22)
        self.assertEqual(len(s0[20][0]), 28)
        # op 40's 21-arity shape must not parse as op 41 and op 41's
        # 22-arity shape must not parse as op 40.
        self.call(
            [41, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            expect_rc=5)
        self.call(
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 16,
            expect_rc=5)


if __name__ == "__main__":
    unittest.main()
