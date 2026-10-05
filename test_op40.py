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


def swing_topo(sb=1, bl=20):
    # s -> d has two routes that diverge at the source and converge
    # only at the destination: via b (s,b,d) and via c (s,c,d). The
    # b branch carries bl latency on b->d while c->d stays at 10, so
    # migrating b<->c swings the path latency by abs(bl-10). An
    # isolated n5 -> n6 link pads total demand with a stationary flow.
    return {"nodes": ["s", "b", "c", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "d", lat=bl),
                      link("s", "c"), link("c", "d"),
                      link("n5", "n6")]}


# tA ties on cost 2 via b/c and the tie break picks b; tB raises s-b
# so the c route wins. Via b latency 30, via c 20: every migration
# swings 10. Failure of b already forced c at tA and failure of c
# keeps b at tB, so neither failure scenario ever migrates.
T_A = swing_topo()
T_B = swing_topo(sb=9)

SCENARIOS = [["x", ["b"], []], ["z", ["c"], []]]

FLOWS = [["f1", "s", "d", 1, 1000],
         ["f2", "n5", "n6", 999, 1000]]

# Equal-latency diamond: both branches cost 2 / latency 20, so a
# b<->c reroute changes path, first hop, and last hop but swings 0.
E_A = swing_topo(bl=10)
E_B = swing_topo(sb=9, bl=10)


def tail_topo(sb=1, bl=20):
    # A diamond whose two routes SHARE the tail node a before the
    # destination: s -> {b,c} -> a -> d. Rerouting b -> c changes the
    # complete path, the first hop, and the latency (b->a is bl) but
    # never the last hop (always a), so the G swing gate diverges
    # from the K last-hop gate.
    return {"nodes": ["s", "b", "c", "a", "d", "n5", "n6"],
            "links": [link("s", "b", sb), link("b", "a", lat=bl),
                      link("s", "c"), link("c", "a"),
                      link("a", "d"),
                      link("n5", "n6")]}


H_A = tail_topo()
H_B = tail_topo(sb=9)


# Adjustable swing magnitudes for sliding-window tests: via b uses a
# configurable b->d latency, via c always latency 20.
W0 = swing_topo(1, 100)    # via b latency 110
W1 = swing_topo(9, 100)    # via c latency 20, swing 90
W2 = swing_topo(1, 30)     # via b latency 40, swing 20
W3 = swing_topo(9, 30)     # via c latency 20, swing 20


def pack(topo=None, v=0, history=None):
    topo = topo or T_A
    h = history if history is not None else [[0, topo, P]]
    return {"v": v, "t": topo, "p": P, "h": h}


def op40(events, flows_=None, scenarios=None, g=10, k=10, j=10, z=10,
         y=10, x=10, w=5, q=10, m=0, b=0, base_topo=None, h=1000000,
         u=1000000, n=1000000, l=1000000, c=1000000, r=10, d=0):
    flows_ = FLOWS if flows_ is None else flows_
    return [40, m, b, events,
            flows_, SCENARIOS if scenarios is None else scenarios,
            l, c, r, d, w, q, h, u, n, x, y, z, j, k, g]


class Op40(unittest.TestCase):
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

    def call_raw(self, op_obj=None, pk=None, raw_text=None, pack_path=None):
        pk = pk if pk is not None else pack()
        with tempfile.TemporaryDirectory() as d:
            if pack_path is None:
                pp = os.path.join(d, "pack.json")
                with open(pp, "w", encoding="utf-8") as f:
                    json.dump(pk, f)
            else:
                pp = pack_path
            text = raw_text if raw_text is not None else json.dumps(op_obj)
            return subprocess.run([sys.executable, RELAY, "config", pp,
                                   text], capture_output=True)

    # ----------------------------------------------------------------
    # Rendering / field positions
    # ----------------------------------------------------------------
    def test_preview_pass_renders_swing_fields(self):
        out, before, after, tmps = self.call(op40([[1, T_B, P]], g=10))
        # Top-level key order unchanged.
        self.assertEqual(list(out.keys()),
                         ["op", "mode", "status", "old", "new", "applied",
                          "events", "config"])
        self.assertEqual([out["op"], out["mode"], out["status"],
                          out["old"], out["new"], out["applied"]],
                         [40, 0, 0, 0, 1, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        row = out["events"][0]
        self.assertEqual(row[0:4], [1, 0, 0, 1])
        scenarios = row[4][3]
        self.assertEqual(len(scenarios), 3)
        # Scenario row: op 39's 21-element shape with
        # maxWindowLatencySwing inserted after
        # maxWindowDistinctLastHops and before pass (22 elements).
        s0 = scenarios[0]
        self.assertEqual(len(s0), 22)
        self.assertEqual(s0[16], 1)             # maxWindowDistinctNexthops
        self.assertEqual(s0[17], 1)             # maxWindowDistinctLastHops
        self.assertEqual(s0[18], 10)            # maxWindowLatencySwing
        self.assertIs(s0[19], True)             # pass
        # Flow row gains windowMaxLatencySwing / latencySwingPass after
        # lastHopDiversityPass and before nexthopDiversityPass:
        # 28 elements.
        f0 = s0[20][0]
        self.assertEqual(len(f0), 28)
        self.assertEqual(f0,
                         ["f1", 2, 2, 30, 20,
                          ["s", "b", "d"], ["s", "c", "d"], True, True,
                          1, None, None, True, -4, 1, True,
                          1, 2, 1, 1, 1, True, 10, True,
                          True, True, True, True])
        # The stationary f2 keeps every window empty: swing 0.
        self.assertEqual(s0[20][1][22:28],
                         [0, True, True, True, True, True])
        # Failure scenarios do not migrate: their swing stays 0.
        for sx in scenarios[1:]:
            self.assertEqual(sx[17], 0)
            self.assertEqual(sx[18], 0)
            self.assertIs(sx[19], True)
            self.assertEqual(sx[20][0][7], False)
            self.assertEqual(sx[20][0][22:28],
                             [0, True, True, True, True, True])

    # ----------------------------------------------------------------
    # G = 0 accepts only a zero jump or an empty window
    # ----------------------------------------------------------------
    def test_g_zero_rejects_first_swing_keeps_candidate(self):
        out, before, after, tmps = self.call(op40([[1, T_B, P]], g=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual([out["old"], out["new"], out["applied"]],
                         [0, 0, False])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[18], 10)
        self.assertFalse(s0[19])
        fr = s0[20][0]
        # Candidate post-event values retained: swing 10, G failed,
        # all op 39 diversity flags fine.
        self.assertEqual(fr[22:28], [10, False, True, True, True, True])
        # Failure scenarios never moved and still pass.
        for sx in out["events"][0][4][3][1:]:
            self.assertTrue(sx[19])
            self.assertEqual(sx[18], 0)

    def test_g_zero_accepts_zero_swing_reroute(self):
        # Equal-latency diamond: path, first hop, and last hop all
        # change but abs(newLatency-oldLatency) = 0, so G = 0 admits
        # the reroute even though K = 0 would reject it.
        out, _, _, _ = self.call(
            op40([[1, E_B, P]], g=0, k=10), pk=pack(E_A))
        self.assertEqual(out["status"], 0)
        f0 = out["events"][0][4][3][0][20][0]
        self.assertIs(f0[7], True)
        self.assertEqual(f0[3:5], [20, 20])
        self.assertEqual(f0[22:28], [0, True, True, True, True, True])
        # With K = 0 the same event fails op 39's last-hop gate while
        # the swing gate stays green.
        out2, _, _, _ = self.call(
            op40([[1, E_B, P]], g=0, k=0), pk=pack(E_A))
        self.assertEqual(out2["status"], 2)
        f0 = out2["events"][0][4][3][0][20][0]
        self.assertEqual(f0[21:28],
                         [False, 0, True, True, True, True, True])

    def test_g_boundary_values_pass_and_fail(self):
        # swing exactly 10: G = 10 passes, G = 9 fails.
        out, _, _, _ = self.call(op40([[1, T_B, P]], g=10))
        self.assertEqual(out["status"], 0)
        out, before, after, _ = self.call(op40([[1, T_B, P]], g=9))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)

    # ----------------------------------------------------------------
    # The window keeps the maximum and slides on the closed edge
    # ----------------------------------------------------------------
    def test_window_max_retained_and_evicted(self):
        # Swings 90@1 (W1), 20@2 (W2), 20@3 (W3); event 4 changes
        # only the isolated link so nothing appends. W = 2: at e3 the
        # closed start clock 1 still retains the 90; at e4 start 2
        # drops it and the retained maximum falls to 20.
        t_quiet = json.loads(json.dumps(W3))
        t_quiet["links"][4]["latency"] = 11
        events = [[1, W1, P], [2, W2, P], [3, W3, P], [4, t_quiet, P]]
        out, _, _, _ = self.call(
            op40(events, g=1000, w=2), pk=pack(W0))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 0), (3, 0), (4, 0)])
        swings = [r[4][3][0][18] for r in out["events"]]
        self.assertEqual(swings, [90, 90, 90, 20])
        f_swings = [r[4][3][0][20][0][22] for r in out["events"]]
        self.assertEqual(f_swings, [90, 90, 90, 20])
        # G = 50 stops the batch at event 1 with the 90 candidate.
        out, before, after, _ = self.call(
            op40(events, g=50, w=2), pk=pack(W0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])

    def test_window_is_closed_when_sliding(self):
        # 90@1 then 20@2. W = 1 keeps clock 1 on the edge so the
        # retained maximum is still 90 and G = 20 fails at event 2;
        # W = 0 drops @1 leaving only 20 and G = 20 passes.
        events = [[1, W1, P], [2, W2, P]]
        out, _, _, _ = self.call(
            op40(events, g=20, w=1), pk=pack(W0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(out["events"][1][4][3][0][18], 90)
        out, _, _, _ = self.call(
            op40(events, g=20, w=0), pk=pack(W0))
        self.assertEqual(out["status"], 0)
        self.assertEqual(out["events"][1][4][3][0][18], 20)

    # ----------------------------------------------------------------
    # The G gate genuinely diverges from the K last-hop gate
    # ----------------------------------------------------------------
    def test_shared_tail_swing_with_one_last_hop(self):
        # H_A -> H_B reroutes s,b,a,d (latency 40) onto s,c,a,d
        # (latency 30): the complete path and first hop change and the
        # latency swings 10, but both paths end through the SAME last
        # hop a, so K = 1 admits while G = 0 rejects.
        out, before, after, _ = self.call(
            op40([[1, H_B, P]], flows_=FLOWS, g=0, k=1),
            pk=pack(H_A))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(s0[17], 1)             # one distinct last hop
        self.assertEqual(s0[18], 10)            # swing 10
        self.assertFalse(s0[19])
        f0 = s0[20][0]
        self.assertEqual(f0[5], ["s", "b", "a", "d"])
        self.assertEqual(f0[6], ["s", "c", "a", "d"])
        self.assertEqual(f0[21:28],
                         [True, 10, False, True, True, True, True])
        # Giving G room admits; the first-hop J gate can still fail
        # independently.
        out, _, _, _ = self.call(
            op40([[1, H_B, P]], flows_=FLOWS, g=10, k=1),
            pk=pack(H_A))
        self.assertEqual(out["status"], 0)
        out, _, _, _ = self.call(
            op40([[1, H_B, P]], flows_=FLOWS, g=10, k=1, j=0),
            pk=pack(H_A))
        self.assertEqual(out["status"], 2)
        f0 = out["events"][0][4][3][0][20][0]
        self.assertEqual(f0[21:28],
                         [True, 10, True, False, True, True, True])

    # ----------------------------------------------------------------
    # Predicate exclusions
    # ----------------------------------------------------------------
    def test_equal_state_and_unchanged_path_add_no_record(self):
        # Event 2 is equal state (status 1, empty impact); event 3
        # changes only the isolated n5->n6 latency, so no path changes
        # and no swing is appended. f1 still shows just the swing 10.
        t_quiet = json.loads(json.dumps(T_B))
        t_quiet["links"][4]["latency"] = 11
        out, _, _, _ = self.call(
            op40([[1, T_B, P], [2, T_B, P], [3, t_quiet, P]],
                 w=100, g=0))
        self.assertEqual(out["status"], 0)
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 0), (2, 1), (3, 0)])
        self.assertEqual(out["events"][1], [2, 1, 1, 1, []])
        s0 = out["events"][2][4][3][0]
        self.assertEqual(s0[18], 10)
        f0 = s0[20][0]
        self.assertIs(f0[7], False)
        self.assertEqual(f0[22:28],
                         [10, False, True, True, True, True])

    def test_unreachable_migration_adds_no_record(self):
        # The candidate side drops both s-branches: f1 is unreachable,
        # no reroute, so no swing record even though the event fails
        # (and the batch stops) on reachability.
        t_dead = {"nodes": T_A["nodes"],
                  "links": [lk for lk in T_A["links"]
                            if (lk["from"], lk["to"])
                            not in (("s", "b"), ("s", "c"))]}
        out, before, after, _ = self.call(op40([[1, t_dead, P]], g=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[19])
        f0 = s0[20][0]
        self.assertEqual(f0[6], [])             # unreachable new side
        self.assertIs(f0[7], False)
        self.assertEqual(f0[22], 0)             # no swing record
        self.assertIs(f0[23], True)             # G itself does not fail

    # ----------------------------------------------------------------
    # No merging across scenarios or flows
    # ----------------------------------------------------------------
    def test_scenarios_never_merge(self):
        # Only the no-failure scenario migrates with swing 10; in x b
        # was already failed onto c and in z c failed keeps b, so
        # their swing windows stay empty at 0.
        out, _, _, _ = self.call(op40([[1, T_B, P]], g=0))
        s0, sx, sz = out["events"][0][4][3]
        self.assertFalse(s0[19])
        self.assertEqual(s0[20][0][22:28],
                         [10, False, True, True, True, True])
        for other in (sx, sz):
            self.assertTrue(other[19])
            self.assertEqual(other[18], 0)
            self.assertEqual(other[20][0][22:28],
                             [0, True, True, True, True, True])

    def test_flows_never_merge(self):
        # Two migrating flows on disjoint diamonds carrying different
        # swings plus a stationary padding flow. The scenario maximum
        # is the larger per-flow swing, never a merged/summed value.
        two = [["f1", "s", "d", 1, 1000],
               ["f3", "n0", "n4", 1, 1000],
               ["f4", "n5", "n6", 999, 1000]]

        def combo(sb=1):
            # f1's diamond s->{b,c}->d (b->d lat 20) and f3's
            # diamond n0->{e,f}->n4 (e->n4 lat 90), both tied at cost
            # 2 with the tie break picking the first branch.
            nodes = ["s", "b", "c", "d", "n0", "e", "f", "n4",
                     "n5", "n6"]
            return {"nodes": nodes,
                    "links": [link("s", "b", sb), link("b", "d", lat=20),
                              link("s", "c"), link("c", "d"),
                              link("n0", "e", sb), link("e", "n4", lat=90),
                              link("n0", "f"), link("f", "n4"),
                              link("n5", "n6")]}

        ca, cb = combo(1), combo(9)
        # f1 swings 10 (30 -> 20); f3 swings 80 (100 -> 20).
        out, _, _, _ = self.call(
            op40([[1, cb, P]], flows_=two, scenarios=[["x", ["b"], []]],
                 g=1000),
            pk=pack(ca))
        self.assertEqual(out["status"], 0)
        s0 = out["events"][0][4][3][0]
        f1, f3, f4 = s0[20]
        self.assertEqual(f1[22], 10)
        self.assertEqual(f3[22], 80)
        self.assertEqual(f4[22], 0)
        self.assertEqual(s0[18], 80)            # max, not sum
        # G = 50 passes f1 but rejects f3, failing the event.
        out, before, after, _ = self.call(
            op40([[1, cb, P]], flows_=two, scenarios=[["x", ["b"], []]],
                 g=50),
            pk=pack(ca))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        f1, f3, f4 = s0[20]
        self.assertTrue(f1[23])
        self.assertFalse(f3[23])

    # ----------------------------------------------------------------
    # Op 39's other gates still reject independently
    # ----------------------------------------------------------------
    def test_q_gate_still_rejects_independently(self):
        # G admits the swing, but Q = 0 rejects the first reroute.
        out, before, after, _ = self.call(
            op40([[1, T_B, P]], g=10, q=0))
        self.assertEqual(out["status"], 2)
        self.assertEqual(after, before)
        s0 = out["events"][0][4][3][0]
        self.assertFalse(s0[19])
        f0 = s0[20][0]
        self.assertIs(f0[15], False)            # windowPass fails
        # Candidate swing still recorded; G reads green on the
        # failed row.
        self.assertEqual(f0[22:28],
                         [10, True, True, True, True, True])

    # ----------------------------------------------------------------
    # Commit / resend / rollback semantics
    # ----------------------------------------------------------------
    def test_commit_resend_and_idempotent(self):
        out, before, after, tmps = self.call(
            op40([[1, T_B, P]], g=10, m=1))
        self.assertTrue(out["applied"])
        self.assertEqual([out["status"], out["old"], out["new"]],
                         [0, 0, 1])
        self.assertNotEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual(json.loads(after)["v"], 1)
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        # Exact resend: status 1, no write.
        out2, _, after2, tmps2 = self.call(
            op40([[1, T_B, P]], g=10, m=1), pk=pk1)
        self.assertEqual([out2["status"], out2["old"], out2["new"],
                          out2["applied"]], [1, 0, 1, False])
        self.assertEqual(json.loads(after2)["v"], 1)
        self.assertEqual(tmps2, [])
        # Equal-state event: status 0, no write even with G = 0.
        out3, _, after3, _ = self.call(
            op40([[2, T_B, P]], g=0, k=0, j=0, z=0, y=0, x=0, q=0, n=0,
                 m=1, b=1),
            pk=pk1)
        self.assertEqual(out3["status"], 0)
        self.assertEqual(out3["events"], [[2, 1, 1, 1, []]])
        self.assertEqual(json.loads(after3)["v"], 1)

    def test_failed_batch_does_not_commit_in_either_mode(self):
        # Event 1 swings 10 (G = 10 admits); event 2 swings back but
        # W keeps the first record, so the maximum is still 10 - no
        # failure there; instead force the failure with G = 0. Mode 1
        # leaves PACK untouched and stops at once.
        out, before, after, tmps = self.call(
            op40([[1, T_B, P]], g=0, m=1))
        self.assertEqual(out["status"], 2)
        self.assertFalse(out["applied"])
        self.assertEqual(after, before)
        self.assertEqual(tmps, [])
        self.assertEqual([(r[0], r[1]) for r in out["events"]],
                         [(1, 2)])
        # A feasible retry (G = 10) commits from the same base.
        out2, _, after2, _ = self.call(
            op40([[1, T_B, P]], g=10, m=1))
        self.assertEqual(out2["status"], 0)
        self.assertTrue(out2["applied"])
        self.assertEqual(json.loads(after2)["v"], 1)

    def test_stale_base_conflict_code5(self):
        pk1 = pack(T_B, v=1, history=[[0, T_A, P], [1, T_B, P]])
        other = json.loads(json.dumps(T_A))
        other["links"][4]["latency"] = 7
        self.call(op40([[6, other, P]], g=10, m=1, b=1), pk=pk1,
                  expect_rc=5)

    # ----------------------------------------------------------------
    # Determinism / error codes / backward compatibility
    # ----------------------------------------------------------------
    def test_byte_deterministic(self):
        op_obj = op40([[1, T_B, P], [2, T_A, P]], w=100, g=20)
        r1 = self.call_raw(op_obj)
        r2 = self.call_raw(op_obj)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_unreadable_pack_code3(self):
        run = self.call_raw(op40([[1, T_B, P]]),
                            pack_path=os.path.join(tempfile.gettempdir(),
                                                   "no-such-pack-40.json"))
        self.assertEqual(run.returncode, 3)

    def test_unparseable_json_code4(self):
        run = self.call_raw(None, raw_text="{not json")
        self.assertEqual(run.returncode, 4)

    def test_non_finite_number_code4(self):
        run = self.call_raw(None, raw_text=json.dumps(op40([[1, T_B, P]]))
                            .replace("[40,", "[NaN,", 1))
        self.assertEqual(run.returncode, 4)

    def test_shape_and_range_code5(self):
        good = op40([[1, T_B, P]])
        self.assertEqual(len(good), 21)
        tail15 = [1] * 15
        bad = [
            # wrong arity: op 39's 20-element shape and one too many
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 16,
            # op 39 must not accept op 40's 21 elements and vice versa
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 13,
            # G negative / boolean / too large / string / float
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2147483648],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, "1"],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5],
            # op 39's K/J/Z/Y/X ranges still enforced inside op 40
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, True, 1, 1],
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1, 1],
            # bad mode
            [40, 2, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + tail15,
            # empty E / F / S
            [40, 0, 0, [], FLOWS, SCENARIOS] + tail15,
            [40, 0, 0, [[1, T_B, P]], [], SCENARIOS] + tail15,
            [40, 0, 0, [[1, T_B, P]], FLOWS, []] + tail15,
            # clocks decrease
            [40, 0, 0, [[2, T_B, P], [1, T_B, P]], FLOWS,
             SCENARIOS] + tail15,
            # invalid scenario reference at h[b]
            [40, 0, 0, [[1, T_B, P]], FLOWS,
             [["q", ["d"], []]]] + tail15,
            # flow endpoint absent at h[b]
            [40, 0, 0, [[1, T_B, P]],
             [["g", "s", "n9", 1, 1000]], SCENARIOS] + tail15,
        ]
        for op_obj in bad:
            self.call(op_obj, expect_rc=5)
        # G = MAX_COST is accepted.
        self.call(op40([[1, T_B, P]], g=2147483647))

    def test_ops_0_to_39_unchanged_smoke(self):
        out, _, _, _ = self.call([2])
        self.assertEqual(out, {"op": 2, "status": 2, "config": pack()})
        # op 39 keeps its 21-field scenario row and 26-field flow row,
        # with no swing fields.
        out, _, _, _ = self.call(
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS,
             1000000, 1000000, 10, 0, 5, 10, 1000000, 1000000, 1000000,
             10, 10, 10, 10, 10])
        self.assertEqual(out["op"], 39)
        s0 = out["events"][0][4][3][0]
        self.assertEqual(len(s0), 21)
        self.assertEqual(len(s0[19][0]), 26)
        # op 39's 20-arity shape must not parse as op 40 and op 40's
        # 21-arity shape must not parse as op 39.
        self.call(
            [40, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 14,
            expect_rc=5)
        self.call(
            [39, 0, 0, [[1, T_B, P]], FLOWS, SCENARIOS] + [1] * 15,
            expect_rc=5)


if __name__ == "__main__":
    unittest.main()
