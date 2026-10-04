import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RELAY = os.path.join(HERE, "relay.py")

P = [0, 0, 0, 0, 0, 0]


def link(frm, to, cost=1, bw=10000, lat=10, up=True):
    return {"from": frm, "to": to, "cost": cost, "bandwidth": bw,
            "latency": lat, "up": up}


def base_topo(cab=1, cac=1):
    # n0 -> n4 has two equal-length routes that share the n0->a head
    # link: via b (n0,a,b,n4) and via c (n0,a,c,n4). Raising a-b pushes
    # the route via c and raising a-c pushes it back via b. An isolated
    # n5 -> n6 link carries a flow that never migrates. At equal cost the
    # full-node-sequence tie break picks b before c.
    return {"nodes": ["n0", "a", "b", "c", "n4", "n5", "n6"],
            "links": [link("n0", "a"),
                      link("a", "b", cab), link("b", "n4"),
                      link("a", "c", cac), link("c", "n4"),
                      link("n5", "n6")]}


# tA ties on cost 3 via b/c and picks b; tB raises a-b so the route via
# c wins; tC raises a-c instead (still cheap via b).
T_A = base_topo()
T_B = base_topo(cab=9)
T_C = base_topo(cac=9)

P1 = ["n0", "a", "b", "n4"]
P2 = ["n0", "a", "c", "n4"]

# P1 links: n0a, ab, bn4; P2 links: n0a, ac, cn4. The head link n0a is
# shared, so both paths retained together span five distinct directed
# links (not six).
L1 = {("n0", "a"), ("a", "b"), ("b", "n4")}
L2 = {("n0", "a"), ("a", "c"), ("c", "n4")}

# b failed reroutes tA onto the c route; c failed keeps tA on the b
# route and tB there too, so its window stays empty across the event.
SCENARIOS = [["x", ["b"], []], ["z", ["c"], []]]


def flow(fid="f1", src="n0", dst="n4", demand=1, mlat=1000):
    return [fid, src, dst, demand, mlat]


def pack(topo=None, v=0, history=None):
    topo = topo or T_A
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


# f1 (demand 1) is the migrating flow and f2 (demand 999 on n5->n6)
# never moves. Generous defaults except the caller overrides Y/X.
FLOWS = [flow(), ["f2", "n5", "n6", 999, 1000]]


def op36(events, flows_=None, y=10, x=10, w=5, q=10, m=0, b=0,
         h=1000000, u=1000000, n=1000000, l=1000000, c=1000000, r=10,
         d=0, scenarios=None):
    flows_ = FLOWS if flows_ is None else flows_
    return [36, m, b, events, flows_,
            SCENARIOS if scenarios is None else scenarios,
            l, c, r, d, w, q, h, u, n, x, y]


class Op36(unittest.TestCase):
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
            tmps = [name for name in os.listdir(d) if ".tmp." in name]
            return out, before, after, tmps

    def call_raw(self, op_obj, pk=None):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w", encoding="utf-8") as f:
                json.dump(pk, f)
            return subprocess.run([sys.executable, RELAY, "config", pp,
                                   json.dumps(op_obj)], capture_output=True)

    def test_preview_pass_renders_link_fields(self):
        out, before, after, tmps = self.call(op36([[1, T_B, P]], y=10))
        # Top-level key order stays op 35's exactly.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [36, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 35's 17-element shape with
        # maxWindowDistinctLinks inserted after maxWindowDistinctPaths
        # and before pass (18 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 18)
        self.assertEqual(s0[13], 1)             # maxWindowDistinctPaths
        self.assertEqual(s0[14], 3)             # maxWindowDistinctLinks
        self.assertIs(s0[15], True)             # pass
        # Flow row gains windowDistinctLinkCount/linkDiversityPass after
        # windowDistinctPathCount and before pathDiversityPass:
        # 20 elements.
        f0 = s0[16][0]
        self.assertEqual(len(f0), 20)
        self.assertEqual(f0,
                         ["f1", 3, 3, 30, 30, P1, P2, True, True, 1,
                          None, None, True, -4, 1, True, 1, 3, True,
                          True])
        # The stationary f2 keeps empty path and link windows.
        self.assertEqual(s0[16][1][14:20],
                         [0, True, 0, 0, True, True])
        # In x (b failed) f1 already used the c route at tA; in z
        # (c failed) f1 keeps the b route at tB: neither migrates, so
        # both link windows stay empty and the scenarios pass.
        for sx in scenarios[1:]:
            self.assertEqual(sx[14], 0)
            self.assertIs(sx[15], True)
            self.assertEqual(sx[16][0][7], False)
            self.assertEqual(sx[16][0][16:20], [0, 0, True, True])

    def test_y_zero_rejects_first_retained_links_keeps_candidate(self):
        out, before, after, tmps = self.call(op36([[1, T_B, P]], y=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[14], 3)
        self.assertFalse(s0[15])
        fr = s0[16][0]
        # Candidate post-event values are retained on the failed row:
        # three distinct directed links, link gate failed, path gate
        # still fine with X generous.
        self.assertEqual(fr[17:20], [3, False, True])
        # Q, N and the windows of non-moving failure scenarios do not
        # fail.
        self.assertEqual(fr[14:17], [1, True, 1])
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[15])
            self.assertEqual(sx[14], 0)

    def test_single_path_spans_three_links_boundary(self):
        # One reroute to P2 spans three directed links: Y = 2 rejects
        # the very first event even though only one distinct path is
        # retained (X admits), while Y = 3 admits exactly.
        out, before, after, _ = self.call(op36([[1, T_B, P]], y=2))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[14], 3)
        self.assertFalse(s0[15])
        self.assertEqual(s0[16][0][17:20], [3, False, True])
        out, _, _, _ = self.call(op36([[1, T_B, P]], y=3))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[14], 3)
        self.assertTrue(s0[15])
        self.assertEqual(s0[16][0][17:20], [3, True, True])

    def test_shared_head_link_counts_once_across_paths(self):
        # tA -> tB -> tA retains P2 then P1. The two paths differ (X = 2
        # admits throughout) but share n0->a, so together they touch five
        # distinct directed links: Y = 4 rejects at event 2 while the
        # path gate still passes - the two gates genuinely diverge.
        events = [[1, T_B, P], [2, T_A, P]]
        out, before, after, _ = self.call(op36(events, w=100, x=2, y=4))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 2)             # two distinct paths
        self.assertEqual(s0[14], 5)             # five distinct links
        self.assertFalse(s0[15])
        f0 = s0[16][0]
        self.assertEqual(f0[16:20], [2, 5, False, True])
        # Y = 5 admits exactly.
        out, _, _, _ = self.call(op36(events, w=100, x=2, y=5))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][2 - 1][4][3][0]
        self.assertEqual(s0[13:16], [2, 5, True])
        self.assertEqual(s0[16][0][16:20], [2, 5, True, True])

    def test_link_leaves_only_after_last_record_slides_out(self):
        # Records for f1: P2@1 (tB), P1@2 (tA), P2@3 (tB). Event 4 is a
        # non-moving topology change (only the isolated n5->n6 latency
        # changes), so W=1 slides the window to start 3 without
        # appending: P2@1 drops (ac/cn4 leave, n0a stays via P1@2 and
        # P2@3), then P1@2 drops (ab/bn4 leave, n0a stays via P2@3),
        # leaving exactly P2's three links - neither a never-shrinking
        # seen-set (five) nor a pop-drops-link implementation
        # (n0a would vanish at event 2).
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][5]["latency"] = 11
        events = [[1, T_B, P], [2, T_A, P], [3, T_B, P],
                  [4, t_quiet, P]]
        out, _, _, _ = self.call(op36(events, w=1, y=5))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0), (4, 0)])
        s0 = out["events"][3][4][3][0]
        self.assertEqual(s0[14], 3)
        self.assertTrue(s0[15])
        f0 = s0[16][0]
        self.assertEqual(f0[7], False)          # event 4 moved nothing
        self.assertEqual(f0[16:20], [1, 3, True, True])
        # Right before the slide (event 3) both paths coexist on the
        # closed edge: windowStart 2 keeps P1@2 and adds P2@3, so the
        # shared n0a plus the four branch links all count (five).
        s3 = out["events"][2][4][3][0]
        self.assertEqual(s3[14], 5)
        self.assertEqual(s3[16][0][16:20], [2, 5, True, True])

    def test_distinct_links_shrink_when_last_record_slides_out(self):
        # P2@1; at e100 f1 moves P2 -> P1. W=1 starts the window at 99,
        # so clock 1 slides out entirely: only P1's three links remain
        # and Y = 3 admits.
        out, _, _, _ = self.call(
            op36([[1, T_B, P], [100, T_A, P]], w=1, y=3))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (100, 0)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[14], 3)
        self.assertTrue(s0[15])
        f0 = s0[16][0]
        self.assertEqual(f0[13], 99)
        self.assertEqual(f0[16:20], [1, 3, True, True])

    def test_window_is_closed_when_sliding(self):
        # P2@1, P1@2. W=1 starts the window at 1, so clock 1 stays and
        # the union spans five links; Y=4 fails at event 2. (W=0 drops
        # the @1 record, leaving P1's three links.)
        out, _, _, _ = self.call(
            op36([[1, T_B, P], [2, T_A, P]], w=1, y=4))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[14], 5)
        self.assertFalse(s0[15])
        out, _, _, _ = self.call(
            op36([[1, T_B, P], [2, T_A, P]], w=0, y=3))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[14], 3)
        self.assertTrue(s0[15])

    def test_equal_state_and_unchanged_path_add_no_record(self):
        # Event 1 moves f1 (P1 -> P2). Event 2 is the same t/p: status
        # 1, an empty impact, no record. Event 3 changes only the
        # isolated n5->n6 link latency, so neither flow's complete path
        # changes: the window slides but nothing is appended and f1
        # still shows P2's three links.
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][5]["latency"] = 11
        out, _, _, _ = self.call(
            op36([[1, T_B, P], [2, T_B, P], [3, t_quiet, P]],
                 w=100, y=3))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[14], 3)
        self.assertTrue(s0[15])
        f0 = s0[16][0]
        self.assertEqual(f0[7], False)          # not a migration
        self.assertEqual(f0[16:20], [1, 3, True, True])

    def test_scenarios_never_merge(self):
        # The tA -> tB event moves f1 only in the no-failure scenario
        # (P1 -> P2); in x (b failed) f1 was already on P2 and in z
        # (c failed) f1 keeps P1, so their link windows stay empty.
        out, _, _, _ = self.call(op36([[1, T_B, P]], y=0))
        self.assertEqual(out["status"], 2)
        scenarios = out["events"][0][4][3]
        s0, sx, sz = scenarios
        self.assertFalse(s0[15])
        self.assertEqual(s0[16][0][17:20], [3, False, True])
        for other in (sx, sz):
            self.assertTrue(other[15])
            self.assertEqual(other[14], 0)
            self.assertEqual(other[16][0][17:20], [0, True, True])

    def test_x_gate_still_rejects_independently(self):
        # Y admits everything (two paths span only five links), but
        # X = 1 rejects the second distinct path.
        out, before, after, _ = self.call(
            op36([[1, T_B, P], [2, T_A, P]], w=100, x=1, y=10))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][1][4][3][0]
        self.assertFalse(s0[15])
        f0 = s0[16][0]
        self.assertEqual(f0[17:20], [5, True, False])   # links fine...
        self.assertEqual(f0[16], 2)                     # ...paths fail

    def test_q_gate_still_rejects_independently(self):
        # Y admits everything, but Q=0 rejects the first reroute.
        out, before, after, _ = self.call(
            op36([[1, T_B, P]], y=10, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[15])
        f0 = s0[16][0]
        self.assertIs(f0[15], False)        # windowPass fails
        self.assertIs(f0[18], True)         # link diversity is fine
        self.assertIs(f0[19], True)         # path diversity is fine

    def test_n_gate_still_rejects_independently(self):
        # One of two flows affected: N below one half rejects while Y
        # admits the three touched links.
        out, before, after, _ = self.call(
            op36([[1, T_B, P]], y=10, n=499999))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[15])
        self.assertEqual(s0[11:15], [1, "0.500000", 1, 3])
        self.assertIs(s0[16][0][18], True)

    def test_commit_resend_and_idempotent(self):
        out, before, after, tmps = self.call(
            op36([[1, T_B, P]], y=10, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op36([[1, T_B, P]], y=10, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Equal-state event: status 0, no write even with Y=X=Q=N=0.
        out3, _, after3, _ = self.call(
            op36([[2, T_B, P]], y=0, x=0, q=0, n=0, m=1, b=1), pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        # Event 1 leaves three distinct links (Y=3 admits); event 2 adds
        # the second path and reaches five links - fails - mode 1 must
        # leave PACK untouched.
        events = [[1, T_B, P], [2, T_A, P]]
        out, before, after, tmps = self.call(
            op36(events, w=100, y=3, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # A feasible retry (Y=5) commits from the same base.
        out2, _, after2, _ = self.call(
            op36(events, w=100, y=5, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        other = json.loads(json.dumps(T_A))
        other["links"][5]["latency"] = 7
        self.call(op36([[6, other, P]], y=10, m=1), pk=pk1,
                  expect_rc=5)

    def test_byte_deterministic(self):
        op_obj = op36([[1, T_B, P], [2, T_A, P]], w=100, y=5)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        good = op36([[1, T_B, P]])
        self.assertEqual(len(good), 17)
        bad = [
            # wrong arity: op 35's 16-element shape and one too many
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            # and op 35 must not accept op 36's seventeen elements
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            # Y negative / boolean / too large / string / float
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2147483648],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, "1"],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5],
            # op 35's X/N/U/H/W/Q/R/D/C/L ranges still enforced
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, True, 1],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, -1, 1, 1],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, True, 1, 1, 1, 1, 1],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, -1, 1, 1, 1, 1, 1, 1, 1],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1000001, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000001, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # bad mode
            [36, 2, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            # empty E / F / S
            [36, 0, 0, [], FLOWS, SCENARIOS] + [1] * 14,
            [36, 0, 0, [[1, T_B, P]], [], SCENARIOS] + [1] * 14,
            [36, 0, 0, [[1, T_B, P]], FLOWS, []] + [1] * 14,
            # clocks decrease
            [36, 0, 0, [[2, T_B, P], [1, T_B, P]], FLOWS,
             SCENARIOS] + [1] * 14,
            # invalid scenario reference at h[b]
            [36, 0, 0, [[1, T_B, P]], FLOWS,
             [["q", ["n4"], []]]] + [1] * 14,
            # flow endpoint absent at h[b]
            [36, 0, 0, [[1, T_B, P]],
             [["g", "n0", "n9", 1, 1000]], SCENARIOS] + [1] * 14,
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)
        # Y = MAX_COST is accepted.
        self.call(op36([[1, T_B, P]], y=2147483647))

    def test_ops_0_to_35_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 35 happy path keeps its 17-field scenario row and 18-field
        # flow row, with no maxWindowDistinctLinks/linkDiversityPass.
        out, _, _, _ = self.call(
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10])
        self.assertEqual(out["op"], 35)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 17)
        self.assertEqual(len(s0[15][0]), 18)
        # op 35's 16-arity shape must not parse as op 36, and op 36's
        # 17-arity shape must not parse as op 35.
        self.call(
            [36, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10],
            expect_rc=5)
        self.call(
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10], expect_rc=5)
        # op 34 keeps its 16-field scenario row.
        out, _, _, _ = self.call(
            [34, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000])
        self.assertEqual(out["op"], 34)
        self.assertEqual(len(out["events"][0][4][3][0]), 16)

    def test_json_file_and_argc_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[36,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],"
                                "1,1,1,1,1,1,1,1,1,1,1]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 4)
            r = subprocess.run([sys.executable, RELAY, "config",
                                os.path.join(d, "missing.json"), "[]"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 3)
            # Wrong config argument count is still code 2.
            r = subprocess.run([sys.executable, RELAY, "config", pp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
