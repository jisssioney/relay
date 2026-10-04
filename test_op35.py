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


NODES = ["n0", "n1", "n2", "n3", "n4", "n5"]


def topo(a2=2, b1=2, b2=2, g1=2, g2=2, lat01=10, keep_n3n4=True):
    # Three n0->n3 branches feed n3->n4; n0->n4 always costs 3 plus the
    # n3->n4 hop. Setting one branch's two links to cost 1 selects that
    # branch uniquely: A (n1), B (n2), or G (n5). When the branches tie
    # the full-node-sequence Unicode tie break picks n1.
    links = [link("n0", "n1", 1, lat=lat01), link("n1", "n3", a2),
             link("n0", "n2", b1), link("n2", "n3", b2),
             link("n0", "n5", g1), link("n5", "n3", g2)]
    if keep_n3n4:
        links.append(link("n3", "n4", 1))
    return {"nodes": list(NODES), "links": links}


def topo_a():
    return topo(a2=1)


def topo_b():
    return topo(b1=1, b2=1)


def topo_g():
    return topo(g1=1, g2=1)


PATH_A = ["n0", "n1", "n3", "n4"]
PATH_B = ["n0", "n2", "n3", "n4"]
PATH_G = ["n0", "n5", "n3", "n4"]


def pack(topo_obj=None, v=0, history=None):
    topo_obj = topo_obj or topo_a()
    h = history if history is not None else [[0, topo_obj, P]]
    return {"v": v, "t": topo_obj, "p": P, "h": h}


SCENARIOS = [["x", ["n1"], []], ["z", [], [["n0", "n1"]]]]


def flow(fid="f1", src="n0", dst="n4", demand=40, mlat=110):
    return [fid, src, dst, demand, mlat]


# Generous gate defaults except the caller overrides them: R/D/Q open,
# H, U, N at the maximum parts-per-million caps and X wide.
def op35(events, flows_, x=10, h=1000000, u=1000000, n=1000000, w=10,
         q=10, m=0, b=0, l=1000000, c=1000000, r=10, d=0):
    return [35, m, b, events, flows_, SCENARIOS, l, c, r, d, w, q, h, u,
            n, x]


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
            tmps = [n_ for n_ in os.listdir(d) if ".tmp." in n_]
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

    def test_preview_pass_renders_path_fields(self):
        out, before, after, tmps = self.call(
            op35([[1, topo_b(), P]], [flow()], x=1))
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
        # maxWindowDistinctPaths inserted after windowDistinctFlowRatio
        # and before pass (17 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 17)
        self.assertEqual(s0[0:13],
                         [None, "0.400000", 40, 40, "1.000000", 1, 1,
                          40, "1.000000", 40, "1.000000", 1,
                          "1.000000"])
        self.assertEqual(s0[13], 1)
        self.assertIs(s0[14], True)
        # Flow row: op 34's 16 elements with windowDistinctPathCount and
        # pathDiversityPass appended after windowPass (18 elements).
        f0 = s0[15][0]
        self.assertEqual(len(f0), 18)
        self.assertEqual(f0,
                         ["f1", 3, 3, 30, 30, PATH_A, PATH_B, True, True,
                          1, None, None, True, -9, 1, True, 1, True])
        # x/z were already on the n2 path at h[b], so they do not move:
        # empty windows, zero distinct paths, still passing.
        for sx in scenarios[1:]:
            self.assertEqual(sx[6:15],
                             [0, 0, "0.000000", 0, "0.000000",
                              0, "0.000000", 0, True])
            self.assertEqual(sx[15][0][7], False)
            self.assertEqual(sx[15][0][16:18], [0, True])

    def test_x_zero_rejects_any_retained_record(self):
        out, before, after, tmps = self.call(
            op35([[1, topo_b(), P]], [flow()], x=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        # Q admits the one record but the diversity gate fails.
        self.assertFalse(s0[14])
        self.assertEqual(s0[13], 1)
        fr = s0[15][0]
        self.assertEqual(fr[14:18], [1, True, 1, False])
        # Non-moving failure scenarios keep an empty window and pass.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[14])
            self.assertEqual(sx[13], 0)
            self.assertEqual(sx[15][0][16:18], [0, True])

    def test_two_distinct_paths_fail_x_one(self):
        # A->B at clock 1 retains PATH_B; B->G at clock 2 retains PATH_G
        # too under W=10: two distinct paths, X=1 rejects at event 2.
        # A static n2->n4 flow keeps the H retained-demand gate open so
        # the X gate is the cause.
        f2 = ["f2", "n2", "n4", 90, 110]
        out, _, _, _ = self.call(
            op35([[1, topo_b(), P], [2, topo_g(), P]],
                 [flow(demand=10), f2], x=1, w=10))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 2)
        self.assertFalse(s0[14])
        fr = s0[15][0]
        # Two records (Q count) and two distinct paths.
        self.assertEqual(fr[14:18], [2, True, 2, False])
        self.assertEqual(fr[5], PATH_B)
        self.assertEqual(fr[6], PATH_G)
        # x/z move once PATH_B -> PATH_G on the second event and retain
        # only that one kind, so they stay within X=1 independently.
        for sx in out["events"][1][4][3][1:]:
            self.assertTrue(sx[14])
            self.assertEqual(sx[13], 1)
            self.assertTrue(sx[15][0][7])
            self.assertEqual(sx[15][0][16:18], [1, True])

    def test_x_two_admits_two_paths_three_fails(self):
        f2 = ["f2", "n2", "n4", 90, 110]
        out, _, _, _ = self.call(
            op35([[1, topo_b(), P], [2, topo_g(), P]],
                 [flow(demand=10), f2], x=2, w=10))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 2)
        self.assertTrue(s0[14])
        self.assertEqual(s0[15][0][16:18], [2, True])
        # A third distinct path trips X=2.
        out3, _, _, _ = self.call(
            op35([[1, topo_b(), P], [2, topo_a(), P], [3, topo_g(), P]],
                 [flow(demand=10), f2], x=2, w=10))
        self.assertEqual(out3["status"], 2)
        s0 = out3["events"][2][4][3][0]
        self.assertEqual(s0[13], 3)
        self.assertFalse(s0[14])
        self.assertEqual(s0[15][0][16:18], [3, False])

    def test_repeated_path_counts_once(self):
        # A->B at 1 (PATH_B), B->A at 2 (PATH_A), A->B at 3 (PATH_B)
        # under W=10: three retained records of only two distinct
        # paths. X=1 already fails at event 2 once the two kinds exist;
        # X=2 admits all three events and the final flow row shows three
        # Q records but only two distinct path kinds - the repeated
        # PATH_B counted once. The static n2->n4 flow keeps H open.
        f2 = ["f2", "n2", "n4", 90, 110]
        events = [[1, topo_b(), P], [2, topo_a(), P], [3, topo_b(), P]]
        out, _, _, _ = self.call(
            op35(events, [flow(demand=10), f2], x=1, w=10, q=10))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 2)
        self.assertEqual(s0[15][0][14:18], [2, True, 2, False])
        out2, _, _, _ = self.call(
            op35(events, [flow(demand=10), f2], x=2, w=10, q=10))
        self.assertEqual(out2["status"], 0)
        s0 = out2["events"][2][4][3][0]
        self.assertEqual(s0[13], 2)
        self.assertTrue(s0[14])
        fr = s0[15][0]
        # Three retained records but only two distinct kinds.
        self.assertEqual(fr[14:18], [3, True, 2, True])

    def test_q_gate_distinct_from_x_gate(self):
        # A->B at 1 (PATH_B), B->A at 2 (PATH_A): at event 2 there are
        # two retained records of two distinct path kinds. With Q=1 the
        # record-count gate rejects the second reroute while X=2 admits
        # the two kinds, so the failure is Q's alone:
        # windowPass False but pathDiversityPass True. The static
        # n2->n4 flow keeps H open.
        f2 = ["f2", "n2", "n4", 90, 110]
        events = [[1, topo_b(), P], [2, topo_a(), P]]
        out, before, after, _ = self.call(
            op35(events, [flow(demand=10), f2], x=2, q=1, w=10))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][1][4][3][0]
        fr = s0[15][0]
        self.assertEqual(fr[14:18], [2, False, 2, True])
        self.assertFalse(s0[14])

    def test_path_kind_vanishes_when_last_record_slides_out(self):
        # A->B at clock 1 (PATH_B). Event 2 at clock 7 is a latency-only
        # change to the B topology, so f1 stays on PATH_B and only the
        # window slides. X=1 admits one retained kind; the rendered
        # distinct count shows whether the clock-1 record survived. With
        # W=5 windowStart=2 the record drops and the count returns to
        # zero; with W=6 the closed edge 1 keeps it.
        b2 = topo(b1=1, b2=1, lat01=11)
        events = [[1, topo_b(), P], [7, b2, P]]
        out, _, _, _ = self.call(op35(events, [flow()], x=1, w=5))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 0)
        self.assertTrue(s0[14])
        self.assertEqual(s0[15][0][13:18], [2, 0, True, 0, True])
        out2, _, _, _ = self.call(op35(events, [flow()], x=1, w=6))
        self.assertEqual(out2["status"], 0)
        s0 = out2["events"][1][4][3][0]
        self.assertEqual(s0[13], 1)
        self.assertTrue(s0[14])
        self.assertEqual(s0[15][0][13:18], [1, 1, True, 1, True])

    def test_window_closed_edge_keeps_path(self):
        # Record at clock 1; non-moving event at clock 6. W=5 keeps the
        # closed edge 1 (windowStart=1), W=4 drops it (windowStart=2).
        # X=1 admits one kind either way; the rendered count shows the
        # edge handling.
        b2 = topo(b1=1, b2=1, lat01=11)
        events = [[1, topo_b(), P], [6, b2, P]]
        out, _, _, _ = self.call(op35(events, [flow()], x=1, w=5))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][1][4][3][0]
        self.assertEqual(s0[13], 1)
        self.assertEqual(s0[15][0][13:18], [1, 1, True, 1, True])
        out2, _, _, _ = self.call(op35(events, [flow()], x=1, w=4))
        self.assertEqual(out2["status"], 0)
        s0 = out2["events"][1][4][3][0]
        self.assertEqual(s0[13], 0)
        self.assertEqual(s0[15][0][13:18], [2, 0, True, 0, True])

    def test_slid_out_path_frees_diversity_slot(self):
        # The X gate itself reacts to the slide: f1 moves A->B at 1
        # (PATH_B), holds its place while a non-moving event at 7 slides
        # the window, then moves to PATH_G at 8. With X=1 the third event
        # passes only when the PATH_B record has already left the closed
        # window. W=5 (windowStart=3 at clock 8) dropped clock 1, so only
        # PATH_G remains and the batch passes; W=7 (windowStart=1) keeps
        # the closed edge 1, so two distinct kinds coexist and event 8
        # fails. A static n2->n4 flow keeps the H retained-demand gate
        # open so the X gate is the cause.
        f2 = ["f2", "n2", "n4", 90, 110]
        b2 = topo(b1=1, b2=1, lat01=11)
        events = [[1, topo_b(), P], [7, b2, P], [8, topo_g(), P]]
        out, _, _, _ = self.call(
            op35(events, [flow(demand=10), f2], x=1, w=5))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[13], 1)
        self.assertTrue(s0[14])
        self.assertEqual(s0[15][0][16:18], [1, True])
        out2, before, after, _ = self.call(
            op35(events, [flow(demand=10), f2], x=1, w=7))
        self.assertEqual(out2["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out2["events"]],
                         [(1, 0), (7, 0), (8, 2)])
        s0 = out2["events"][2][4][3][0]
        self.assertEqual(s0[13], 2)
        self.assertFalse(s0[14])
        self.assertEqual(s0[15][0][16:18], [2, False])

    def test_equal_state_event_adds_no_record(self):
        # move A->B at 1, equal-state at 2 (status 1, empty impact),
        # B->A at 3. W=10 keeps both move records (PATH_B, PATH_A) so
        # X=1 fails at event 3; the equal event added no path record.
        # The static n2->n4 flow keeps the H retained-demand gate open.
        f2 = ["f2", "n2", "n4", 90, 110]
        events = [[1, topo_b(), P], [2, topo_b(), P], [3, topo_a(), P]]
        out, _, _, _ = self.call(
            op35(events, [flow(demand=10), f2], x=1, w=10))
        self.assertEqual(out["status"], 2)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 2)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[13], 2)
        self.assertEqual(s0[15][0][16:18], [2, False])

    def test_non_moving_event_adds_no_path_record(self):
        # A latency tweak leaves f1 on PATH_A; X=0 must still pass and
        # show zero distinct paths.
        out, _, _, _ = self.call(
            op35([[1, topo(lat01=11), P]], [flow()], x=0))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        self.assertTrue(s0[14])
        self.assertEqual(s0[13], 0)
        self.assertEqual(s0[15][0][7], False)
        self.assertEqual(s0[15][0][16:18], [0, True])

    def test_unreachable_event_adds_no_path_record(self):
        # Dropping n3->n4 makes f1 unreachable on every new side; the
        # batch fails reachability, not X, and no path record is added.
        out, _, _, _ = self.call(
            op35([[1, topo(keep_n3n4=False), P]], [flow()], x=0))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[14])
        fr = s0[15][0]
        self.assertEqual(fr[6], [])
        self.assertFalse(fr[7])
        self.assertEqual(fr[16:18], [0, True])

    def test_scenarios_never_merge(self):
        # At h[b]=A the no-failure side uses PATH_A while x/z (n1 or
        # n0->n1 failed) use PATH_B. An event making the n5 branch cheap
        # (n1 still cost-1) leaves the no-failure flow on PATH_A but
        # moves x/z from PATH_B to PATH_G. With X=0 the no-failure
        # scenario keeps an empty window and passes while x/z each keep
        # their own single record and fail independently.
        t0 = topo(a2=1)
        t1 = topo(a2=1, g1=1, g2=1)
        out, _, _, _ = self.call(
            op35([[1, t1, P]], [flow()], x=0, w=10), pk=pack(t0))
        self.assertEqual(out["status"], 2)
        scenarios = out["events"][0][4][3]
        s_none, s_x, s_z = scenarios
        self.assertTrue(s_none[14])
        self.assertEqual(s_none[13], 0)
        self.assertFalse(s_none[15][0][7])
        self.assertEqual(s_none[15][0][16:18], [0, True])
        for sx in (s_x, s_z):
            self.assertEqual(len(sx), 17)
            self.assertFalse(sx[14])
            self.assertEqual(sx[13], 1)
            self.assertTrue(sx[15][0][7])
            self.assertEqual(sx[15][0][5], PATH_B)
            self.assertEqual(sx[15][0][6], PATH_G)
            self.assertEqual(sx[15][0][16:18], [1, False])

    def test_two_flows_counted_separately(self):
        # f1 accumulates three kinds (PATH_B at 1, PATH_A at 2, PATH_G
        # at 3); f2 n2->n4 never moves. maxWindowDistinctPaths is 3 from
        # f1 alone, X=2 fails; f2 keeps zero distinct paths.
        f2 = ["f2", "n2", "n4", 90, 110]
        events = [[1, topo_b(), P], [2, topo_a(), P], [3, topo_g(), P]]
        out, _, _, _ = self.call(
            op35(events, [flow(demand=10), f2], x=2, w=10))
        self.assertEqual(out["status"], 2)
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[13], 3)
        self.assertFalse(s0[14])
        fr1, fr2 = s0[15]
        self.assertEqual(fr1[16:18], [3, False])
        self.assertEqual(fr2[16:18], [0, True])
        # X=3 admits f1's three kinds.
        out3, _, _, _ = self.call(
            op35(events, [flow(demand=10), f2], x=3, w=10))
        self.assertEqual(out3["status"], 0)
        s0 = out3["events"][2][4][3][0]
        self.assertEqual(s0[13], 3)
        self.assertTrue(s0[14])

    def test_n_gate_still_rejects_independently(self):
        # X admits everything, N=0 rejects the first reroute.
        out, before, after, _ = self.call(
            op35([[1, topo_b(), P]], [flow()], x=10, n=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[14])
        self.assertEqual(s0[11:14], [1, "1.000000", 1])
        # The flow's diversity gate admitted the one kind.
        self.assertEqual(s0[15][0][16:18], [1, True])

    def test_u_h_q_gates_still_reject(self):
        t = topo_b()
        out, before, after, _ = self.call(
            op35([[1, t, P]], [flow()], x=10, u=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertFalse(out["events"][0][4][3][0][14])
        out, before, after, _ = self.call(
            op35([[1, t, P]], [flow()], x=10, h=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertFalse(out["events"][0][4][3][0][14])
        out, before, after, _ = self.call(
            op35([[1, t, P]], [flow()], x=10, q=0))
        self.assertEqual(out["status"], 2)
        fr = out["events"][0][4][3][0][15][0]
        self.assertEqual(fr[15], False)

    def test_commit_resend_and_idempotent(self):
        t = topo_b()
        out, before, after, tmps = self.call(
            op35([[1, t, P]], [flow()], x=1, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(t, v=1, history=[[0, topo_a(), P], [1, t, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op35([[1, t, P]], [flow()], x=1, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Same-state event: status 1 row, no write even with every gate
        # closed.
        out3, _, after3, _ = self.call(
            op35([[2, t, P]], [flow()], x=0, h=0, u=0, n=0, q=0, m=1,
                 b=1), pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit(self):
        # First event commits; the second introduces a second distinct
        # path and X=1 rejects: mode 1 must leave PACK untouched. A
        # static n2->n4 flow keeps H open so X is the failing gate.
        f2 = ["f2", "n2", "n4", 90, 110]
        events = [[1, topo_b(), P], [2, topo_g(), P]]
        out, before, after, tmps = self.call(
            op35(events, [flow(demand=10), f2], x=1, w=10, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 2)])
        # A feasible retry widening X commits.
        out2, _, after2, _ = self.call(
            op35(events, [flow(demand=10), f2], x=2, w=10, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 2)

    def test_stale_base_conflict_code5(self):
        t = topo_b()
        pk1 = pack(t, v=1, history=[[0, topo_a(), P], [1, t, P]])
        other = topo(b1=1, b2=1, lat01=7)
        self.call(
            op35([[6, other, P]], [flow()], x=1, m=1),
            pk=pk1, expect_rc=5)

    def test_byte_deterministic(self):
        events = [[1, topo_b(), P], [7, topo_a(), P]]
        op_obj = op35(events, [flow()], x=1, w=5, n=500000)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_shape_and_range_code5(self):
        t = topo_b()
        good = op35([[1, t, P]], [flow()])
        self.assertEqual(len(good), 16)
        bad = [
            # wrong arity: op 34's 15-element shape and one too many
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1, 1, 1],
            # op 34 must not accept op 35's sixteen elements and vice
            # versa
            [34, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1, 1],
            # X negative / boolean / too large / string / float. X range
            # is 0..MAX_COST, so 2147483648 is out but MAX_COST is in.
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1, -1],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1, True],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1, 2147483648],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1, "1"],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1, 0.5],
            # op 34's N/U/H/W/Q/R/D/C/L ranges still enforced
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, -1, 1],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1000001, 1],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, -1, 1, 1],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, -1, 1, 1, 1],
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1000001, 1,
             1, 1, 1, 1, 1, 1, 1],
            # bad mode
            [35, 2, 0, [[1, t, P]], [flow()], SCENARIOS, 1, 1, 1, 1,
             1, 1, 1, 1, 1, 1],
            # empty E / F / S
            [35, 0, 0, [], [flow()], SCENARIOS, 1, 1, 1, 1, 1, 1, 1, 1,
             1, 1],
            [35, 0, 0, [[1, t, P]], [], SCENARIOS, 1, 1, 1, 1, 1, 1,
             1, 1, 1, 1],
            [35, 0, 0, [[1, t, P]], [flow()], [], 1, 1, 1, 1, 1, 1,
             1, 1, 1, 1],
            # clocks decrease
            [35, 0, 0, [[2, t, P], [1, t, P]], [flow()], SCENARIOS, 1,
             1, 1, 1, 1, 1, 1, 1, 1, 1],
            # invalid scenario reference at h[b]
            [35, 0, 0, [[1, t, P]], [flow()],
             [["q", ["n4"], []]], 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # flow endpoint absent at h[b]
            [35, 0, 0, [[1, t, P]],
             [["g", "n0", "n9", 40, 110]], SCENARIOS, 1, 1, 1, 1, 1,
             1, 1, 1, 1, 1],
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)

    def test_x_max_cost_accepted(self):
        t = topo_b()
        out, _, _, _ = self.call(
            op35([[1, t, P]], [flow()], x=2147483647))
        self.assertEqual(out["status"], 0)

    def test_ops_0_to_34_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        t = topo_b()
        # op 34 happy path keeps its 16-field scenario row and 16-field
        # flow row, with no maxWindowDistinctPaths.
        out, _, _, _ = self.call(
            [34, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1, 1000000, 1000000, 1000000])
        self.assertEqual(out["op"], 34)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 16)
        self.assertEqual(len(s0[14][0]), 16)
        # op 34's 15-arity shape must not parse as op 35, and op 35's
        # 16-arity shape must not parse as op 34.
        self.call(
            [35, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1, 1000000, 1000000, 1000000],
            expect_rc=5)
        self.call(
            [34, 0, 0, [[1, t, P]], [flow()], SCENARIOS, 1000000,
             1000000, 1, 5, 5, 1, 1000000, 1000000, 1000000, 1],
            expect_rc=5)

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
