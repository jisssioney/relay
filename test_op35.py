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


def base_topo(c1=1, c2=1, c3=1):
    # Three parallel n0 -> n4 paths through n1/n2/n3 plus an isolated
    # n5 -> n6 link for a flow that never migrates. At equal cost the
    # full-node-sequence Unicode tie break picks n1 over n2 over n3.
    return {"nodes": ["n0", "n1", "n2", "n3", "n4", "n5", "n6"],
            "links": [link("n0", "n1", c1), link("n1", "n4", c1),
                      link("n0", "n2", c2), link("n2", "n4", c2),
                      link("n0", "n3", c3), link("n3", "n4", c3),
                      link("n5", "n6")]}


# tA routes n0->n4 via n1; raising the n1 links pushes it via n2 (tB),
# and raising n2 as well via n3 (tC).
T_A = base_topo()
T_B = base_topo(c1=9)
T_C = base_topo(c1=9, c2=9)

P1 = ["n0", "n1", "n4"]
P2 = ["n0", "n2", "n4"]
P3 = ["n0", "n3", "n4"]

SCENARIOS = [["x", ["n1"], []], ["z", [], [["n0", "n1"]]]]


def flow(fid="f1", src="n0", dst="n4", demand=1, mlat=1000):
    return [fid, src, dst, demand, mlat]


def pack(topo=None, v=0, history=None):
    topo = topo or T_A
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


# f1 (demand 1) is the migrating flow and f2 (demand 999 on n5->n6)
# never moves, so repeated f1 reroutes never approach the H/U demand
# gates. Generous defaults except the caller overrides X.
FLOWS = [flow(), ["f2", "n5", "n6", 999, 1000]]


def op35(events, flows_=None, x=10, w=5, q=10, m=0, b=0, h=1000000,
         u=1000000, n=1000000, l=1000000, c=1000000, r=10, d=0,
         scenarios=None):
    flows_ = FLOWS if flows_ is None else flows_
    return [35, m, b, events, flows_,
            SCENARIOS if scenarios is None else scenarios,
            l, c, r, d, w, q, h, u, n, x]


class Op35(unittest.TestCase):
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

    def test_preview_pass_renders_path_fields(self):
        out, before, after, tmps = self.call(op35([[1, T_B, P]], x=10))
        # Top-level key order is op 34's exactly.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [35, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 34's 16-element shape with
        # maxWindowDistinctPaths inserted after
        # windowDistinctFlowRatio and before pass (17 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 17)
        self.assertEqual(s0[11], 1)             # windowDistinctCount
        self.assertEqual(s0[12], "0.500000")    # 1 of 2 flows
        self.assertEqual(s0[13], 1)             # maxWindowDistinctPaths
        self.assertIs(s0[14], True)             # pass
        # Flow row gains windowDistinctPathCount/pathDiversityPass
        # after windowPass: 18 elements.
        f0 = s0[15][0]
        self.assertEqual(len(f0), 18)
        self.assertEqual(f0,
                         ["f1", 2, 2, 20, 20, P1, P2, True, True, 1,
                          None, None, True, -4, 1, True, 1, True])
        # The stationary f2 keeps an empty path window.
        self.assertEqual(s0[15][1][14:18], [0, True, 0, True])
        # In the failure scenarios f1 stays on the n2 path (n1 / the
        # n0->n1 link already removed at tA), so it does not migrate:
        # no path record, maxWindowDistinctPaths 0, scenario passes.
        for sx in scenarios[1:]:
            self.assertEqual(sx[13], 0)
            self.assertIs(sx[14], True)
            self.assertEqual(sx[15][0][7], False)
            self.assertEqual(sx[15][0][16:18], [0, True])

    def test_x_zero_rejects_first_retained_path_keeps_candidate(self):
        out, before, after, tmps = self.call(op35([[1, T_B, P]], x=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[13], 1)
        self.assertFalse(s0[14])
        fr = s0[15][0]
        # Candidate post-event values are retained on the failed row.
        self.assertEqual(fr[16:18], [1, False])
        # Q, N and the path windows of non-moving failure scenarios do
        # not fail.
        self.assertEqual(fr[14:16], [1, True])
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[14])
            self.assertEqual(sx[13], 0)

    def test_three_distinct_paths_boundary(self):
        # tA -> tB -> tC -> tA walks f1 through n1, n2, n3, back to n1:
        # three distinct complete paths in the window.
        events = [[1, T_B, P], [2, T_C, P], [3, T_A, P]]
        out, before, after, _ = self.call(op35(events, w=100, x=2))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 2)])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[13], 3)
        self.assertFalse(s0[14])
        self.assertEqual(s0[15][0][16:18], [3, False])
        # X = 3 admits exactly three distinct paths.
        out, _, _, _ = self.call(op35(events, w=100, x=3))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[13], 3)
        self.assertTrue(s0[14])
        self.assertEqual(s0[15][0][16:18], [3, True])

    def test_repeated_path_counts_once(self):
        # Oscillate tA -> tB -> tA -> tB -> tA: four reroute records but
        # only the two distinct paths n1/n2 ever appear, so X = 2
        # admits throughout while X = 1 rejects at event 2.
        events = [[1, T_B, P], [2, T_A, P], [3, T_B, P], [4, T_A, P]]
        out, _, _, _ = self.call(op35(events, w=100, x=2))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0), (4, 0)])
        f0 = out["events"][3][4][3][0][15][0]
        self.assertEqual(f0[9], 4)           # four cumulative reroutes
        self.assertEqual(f0[14], 4)          # four retained records
        self.assertEqual(f0[16:18], [2, True])
        out, _, _, _ = self.call(op35(events, w=100, x=1))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        f0 = out["events"][1][4][3][0][15][0]
        self.assertEqual(f0[16:18], [2, False])

    def test_path_leaves_only_after_last_record_slides_out(self):
        # Records for f1: n2@1 (tB), n1@2 (tA), n2@3 (tB). Event 4 is a
        # non-moving topology change (only the isolated n5->n6 latency
        # changes), so it slides the W=1 window to start 3 without
        # appending: n2@1 drops but n2 stays via its @3 record (its
        # retained count falls 2 -> 1), while n1's sole record @2 drops
        # and n1 leaves the set. The answer is exactly one distinct
        # path - neither a never-shrinking seen-set (two) nor a
        # pop-removes-path implementation (zero).
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][6]["latency"] = 11
        events = [[1, T_B, P], [2, T_A, P], [3, T_B, P],
                  [4, t_quiet, P]]
        out, _, _, _ = self.call(op35(events, w=1, x=2))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0), (4, 0)])
        s0 = out["events"][3][4][3][0]
        self.assertEqual(s0[13], 1)
        self.assertTrue(s0[14])
        f0 = s0[15][0]
        self.assertEqual(f0[7], False)          # event 4 moved nothing
        self.assertEqual(f0[14:18], [1, True, 1, True])
        # Right before the slide (event 3) both paths coexist on the
        # closed edge: windowStart 2 keeps n1@2 and adds n2@3.
        s3 = out["events"][2][4][3][0]
        self.assertEqual(s3[13], 2)
        self.assertEqual(s3[15][0][14:18], [2, True, 2, True])

    def test_distinct_paths_shrink_when_last_record_slides_out(self):
        # n2@1; at e100 f1 moves n2 -> n3. W=1 starts the window at 99,
        # so clock 1 slides out entirely: only n3 remains and X = 1
        # admits. The Q/H/U/N windows show exactly one record too.
        out, _, _, _ = self.call(
            op35([[1, T_B, P], [100, T_C, P]], w=1, x=1))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (100, 0)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 1)
        self.assertTrue(s0[14])
        f0 = s0[15][0]
        self.assertEqual(f0[13], 99)
        self.assertEqual(f0[14:18], [1, True, 1, True])

    def test_window_is_closed_when_sliding(self):
        # n2@1, n3@2. W=1 starts the window at 1, so clock 1 stays and
        # both paths count; X=1 fails at event 2. (W=0 would drop it.)
        out, _, _, _ = self.call(
            op35([[1, T_B, P], [2, T_C, P]], w=1, x=1))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 2)
        self.assertFalse(s0[14])
        out, _, _, _ = self.call(
            op35([[1, T_B, P], [2, T_C, P]], w=0, x=1))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 1)
        self.assertTrue(s0[14])

    def test_equal_state_and_unchanged_path_add_no_record(self):
        # Event 1 moves f1 (n1 -> n2). Event 2 is the same t/p: status
        # 1, an empty impact, no path record. Event 3 changes only the
        # isolated n5->n6 link latency, so neither flow's complete path
        # changes: the window slides but nothing is appended and f1
        # still shows the single n2 path.
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][6]["latency"] = 11
        out, _, _, _ = self.call(
            op35([[1, T_B, P], [2, T_B, P], [3, t_quiet, P]],
                 w=100, x=1))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[13], 1)
        self.assertTrue(s0[14])
        f0 = s0[15][0]
        self.assertEqual(f0[7], False)          # not a migration
        self.assertEqual(f0[14:18], [1, True, 1, True])

    def test_scenarios_never_merge(self):
        # The tA -> tB event moves f1 only in the no-failure scenario
        # (n1 -> n2); in x (n1 failed) and z (n0->n1 failed) f1 was
        # already on n2 at tA, so their path windows stay empty.
        out, _, _, _ = self.call(op35([[1, T_B, P]], x=0))
        self.assertEqual(out["status"], 2)
        scenarios = out["events"][0][4][3]
        s0, sx, sz = scenarios
        self.assertFalse(s0[14])
        self.assertEqual(s0[15][0][16:18], [1, False])
        for other in (sx, sz):
            self.assertTrue(other[14])
            self.assertEqual(other[13], 0)
            self.assertEqual(other[15][0][16:18], [0, True])

    def test_q_gate_still_rejects_independently(self):
        # X admits everything, but Q=0 rejects the first reroute.
        out, before, after, _ = self.call(
            op35([[1, T_B, P]], x=10, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[14])
        f0 = s0[15][0]
        self.assertEqual(f0[15], False)         # windowPass fails
        self.assertEqual(f0[17], True)          # path diversity is fine

    def test_n_gate_still_rejects_independently(self):
        # One of two flows affected: N below one half rejects while X
        # admits the single distinct path.
        out, before, after, _ = self.call(
            op35([[1, T_B, P]], x=10, n=499999))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[14])
        self.assertEqual(s0[11:14], [1, "0.500000", 1])
        self.assertEqual(s0[15][0][17], True)

    def test_commit_resend_and_idempotent(self):
        out, before, after, tmps = self.call(
            op35([[1, T_B, P]], x=10, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op35([[1, T_B, P]], x=10, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Equal-state event: status 0, no write even with X=Q=N=0.
        out3, _, after3, _ = self.call(
            op35([[2, T_B, P]], x=0, q=0, n=0, m=1, b=1), pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        # Event 1 leaves one distinct path (X=1 admits); event 2 adds a
        # second and fails - mode 1 must leave PACK untouched.
        events = [[1, T_B, P], [2, T_C, P]]
        out, before, after, tmps = self.call(
            op35(events, w=100, x=1, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # A feasible retry (X=2) commits from the same base.
        out2, _, after2, _ = self.call(
            op35(events, w=100, x=2, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        other = json.loads(json.dumps(T_A))
        other["links"][6]["latency"] = 7
        self.call(op35([[6, other, P]], x=10, m=1), pk=pk1,
                  expect_rc=5)

    def test_byte_deterministic(self):
        op_obj = op35([[1, T_B, P], [2, T_C, P]], w=100, x=2)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        good = op35([[1, T_B, P]])
        self.assertEqual(len(good), 16)
        bad = [
            # wrong arity: op 34's 15-element shape and one too many
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 12,
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            # and op 34 must not accept op 35's sixteen elements
            [34, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            # X negative / boolean / too large / string / float
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, True],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 2147483648],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, "1"],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5],
            # op 34's N/U/H/W/Q/R/D/C/L ranges still enforced
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, -1, 1],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, True, 1],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, -1, 1, 1],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, True, 1, 1, 1, 1],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, -1, 1, 1, 1, 1, 1, 1],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1000001, 1, 1, 1, 1, 1, 1, 1, 1],
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000001, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # bad mode
            [35, 2, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            # empty E / F / S
            [35, 0, 0, [], FLOWS, SCENARIOS] + [1] * 13,
            [35, 0, 0, [[1, T_B, P]], [], SCENARIOS] + [1] * 13,
            [35, 0, 0, [[1, T_B, P]], FLOWS, []] + [1] * 13,
            # clocks decrease
            [35, 0, 0, [[2, T_B, P], [1, T_B, P]], FLOWS,
             SCENARIOS] + [1] * 13,
            # invalid scenario reference at h[b]
            [35, 0, 0, [[1, T_B, P]], FLOWS,
             [["q", ["n4"], []]]] + [1] * 13,
            # flow endpoint absent at h[b]
            [35, 0, 0, [[1, T_B, P]],
             [["g", "n0", "n9", 1, 1000]], SCENARIOS] + [1] * 13,
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)
        # X = MAX_COST is accepted.
        self.call(op35([[1, T_B, P]], x=2147483647))

    def test_ops_0_to_34_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 34 happy path keeps its 16-field scenario row and 16-field
        # flow row, with no maxWindowDistinctPaths/pathDiversityPass.
        out, _, _, _ = self.call(
            [34, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000])
        self.assertEqual(out["op"], 34)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 16)
        self.assertEqual(len(s0[14][0]), 16)
        # op 34's 15-arity shape must not parse as op 35, and op 35's
        # 16-arity shape must not parse as op 34.
        self.call(
            [35, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000],
            expect_rc=5)
        self.call(
            [34, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             1000000], expect_rc=5)
        # op 33 keeps its 14-field scenario row.
        out, _, _, _ = self.call(
            [33, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000])
        self.assertEqual(out["op"], 33)
        self.assertEqual(len(out["events"][0][4][3][0]), 14)

    def test_json_file_and_argc_errors(self):
        with tempfile.TemporaryDirectory() as d:
            pp = os.path.join(d, "pack.json")
            with open(pp, "w") as f:
                f.write("{not json")
            r = subprocess.run([sys.executable, RELAY, "config", pp,
                                "[35,0,0,[[1,{},[0]]],"
                                "[['f','a','b',1,1]],[['s',[],[]]],"
                                "1,1,1,1,1,1,1,1,1,1]"],
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
