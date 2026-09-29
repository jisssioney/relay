"""relay: single-source lowest-cost routing.

Usage: python relay.py route FILE SOURCE
       python relay.py ecmp FILE SOURCE FLOW
       python relay.py metric FILE SOURCE ORDER
       python relay.py wm FILE S W
       python relay.py wmecmp FILE S FLOW W
       python relay.py protect FILE SOURCE DESTINATION DELAY EVENTS
       python relay.py forward FILE SOURCE DESTINATION LIMIT TABLE
       python relay.py queue FILE FROM TO CAP STEP DATA
       python relay.py fragment DATA
       python relay.py reassemble DATA
       python relay.py rewrite R D
       python relay.py reorder FILE FROM TO BASE WINDOW DATA
       python relay.py converge FILE SRC DST D R EVENTS
       python relay.py policy FILE S D P C RULES
       python relay.py policytx FILE STATE OP
       python relay.py policyreplay PACK STATE TV PV DATA
       python relay.py reserve FILE DATA
       python relay.py rebalance FILE DATA LIMIT
       python relay.py loadshift FILE LIMIT FLOWS EVENTS
       python relay.py flowshift FILE LIMIT FLOWS EVENTS
       python relay.py pshift FILE LIMIT FLOWS RULES EVENTS
       python relay.py pshiftcp FILE LIMIT FLOWS RULES I M STATE EVENTS
       python relay.py retune FILE LIMIT DATA
       python relay.py quality FILE A B DATA
       python relay.py replay FILE A B DATA
       python relay.py audit FILE A B DATA
       python relay.py drill FILE A B EVENTS DATA
       python relay.py multidrill FILE A B EVENTS DATA
       python relay.py convstat FILE A B EVENTS DATA
       python relay.py slosum FILE A B W EVENTS DATA
       python relay.py sloeval FILE A B W POLICY EVENTS DATA
       python relay.py slocmp FILE A B W OLD NEW EVENTS DATA
       python relay.py slogate FILE A B W CUR NEW EVENTS DATA
       python relay.py hotload FILE STATE A B W BASE OP EVENTS DATA
       python relay.py snapshot STATE OP
       python relay.py config PACK OP
       python relay.py nfail FILE S D W DATA
       python relay.py lfail FILE S D W DATA
       python relay.py lrepair FILE S D W DATA
       python relay.py nrepair FILE S D W DATA
       python relay.py impair FILE S D DATA
       python relay.py compound FILE S D W DATA
       python relay.py compoundcp FILE S D W AT M STATE DATA
       python relay.py branch FILE S D W DB OP

Exit codes: 2 bad args/subcommand, 3 file unreadable (FILE or STATE,
for policyreplay PACK or STATE, and for policytx op 4 also OUT),
4 JSON syntax
(for forward also duplicate keys or non-finite numbers in FILE/TABLE,
for queue/reorder/converge/policy/reserve/rebalance/retune also those in
FILE/DATA/EVENTS/RULES, and for loadshift/flowshift also those in FILE/FLOWS/EVENTS, and for
pshift also those in FILE/FLOWS/RULES/EVENTS, and for pshiftcp also
those in FILE/FLOWS/RULES/EVENTS/STATE, for fragment/reassemble that in DATA, for rewrite that in R/D, for quality/replay/nfail/lfail/lrepair/nrepair/impair/
compound/audit those in DATA, for compoundcp those in STATE/DATA, for
branch those in DB/OP, for wm/wmecmp those in FILE/W, for drill/multidrill/convstat/slosum
EVENTS/DATA, for sloeval those in POLICY/EVENTS/DATA, for slocmp
those in OLD/NEW/EVENTS/DATA, for slogate those in
CUR/NEW/EVENTS/DATA, for hotload those in STATE/OP/EVENTS/DATA, for
snapshot those in STATE/OP/IN, for config those in PACK/OP/IN, for
policytx those in STATE/OP, for policyreplay those in PACK/STATE/DATA),
5 FLOW/ORDER/DELAY/EVENTS/LIMIT/TABLE/CAP/STEP/BASE/WINDOW/DATA/D/R/
P/C/RULES/A/B/W/POLICY/OLD/CUR/NEW/STATE/OP/schema/topology/
unknown-node/overflow/re-failure error; for hotload code 5 also covers
a STATE whose v/p/h structure, version continuity, or version conflict
is invalid; for snapshot code 5 also covers an invalid OP shape, path,
or BASE, a STATE/IN whose v/p/h structure, key order, or version
continuity is invalid, and a BASE that conflicts with the current v;
for config code 5 also covers an invalid OP shape, path, or BASE, a
PACK/IN whose v/t/p/h structure, key order, topology, version
continuity, or last-entry match is invalid, and a BASE that conflicts
with the current v; for config op 3 code 5 also covers an invalid TS or
Q, a TS version absent from h, a Q endpoint absent from the current t,
and a rollback write whose BASE conflicts with v or whose v is already
MAX_COST; for config op 4 code 5 also covers an invalid LOG shape or
record, a record t/p that is not a valid topology/policy, a BASE absent
from h, a broken seq/pre chain, a gap or duplicate in the appended
versions, an h[seq] conflict on a reused version, and a new version
that would overflow MAX_COST; config op 6 reuses op 4's exact code 5
checks as a read-only preview that never writes; config op 7 reuses
the same checks as a read-only diff audit that never writes;
config op 8 code 5 also covers a mode outside 0/1, an out-of-range
b/e, an invalid event t/p, a b that conflicts with the current v, and
a new version that would overflow MAX_COST; config op 9 code 5 also
covers a mode outside 0/1, an out-of-range b/e/r, an r absent from h,
a b that conflicts with the current v, and a new version that would
overflow MAX_COST; for config op 5 code 5
also covers an invalid F/T or OUT path and an F/T interval outside
0..v; config op 10 code 5 also covers a mode outside 0/1, an
out-of-range B/e/r/o/n, a non-boolean a, an O that is not a non-empty
path (m=0) or not null (m=1), a B absent from h, a decreasing e, a
broken o chain, an r above o, an n/a pair violating the
target-equality rule, a commit reference missing from h or
conflicting with it, and a new version that would overflow MAX_COST;
config op 11 code 5 also covers an invalid G shape or segment, an
out-of-range b/c, a first segment b that is not B, a later segment b
that is not the previous segment's c, a segment c that is not the
chained o after its last item, and a decreasing e across segment
boundaries, plus op 10's per-item checks within every segment;
config op 12 code 5 also covers a mode outside 0/1, an out-of-range
B/I, an I above the segment count, a C that is not a non-empty path,
a checkpoint whose key order, types, or b/i/v/d values conflict with
B/I/G[:I], a prefix commit missing from PACK.h or conflicting with
it, and op 11's segment-chain and per-item checks over the whole G;
for config op 12 code 3 also covers a C read/write error and code 4
a C with invalid UTF-8/JSON syntax, duplicate keys, or non-finite
numbers; config op 13 code 5 also covers a mode outside 0/1, a C that
is not a non-empty path, a manifest whose key order, types, or
b/points values conflict with B/G, a selected point whose prefix
commit is missing from PACK.h or conflicts with it, and op 11's
segment-chain and per-item checks over the whole G; for config op 13
code 3 also covers a C read/write error and code 4 a C with invalid
UTF-8/JSON syntax, duplicate keys, or non-finite numbers; for
compoundcp code 3 also covers a STATE read/write error and code 5
also covers a STATE whose key order, content, or h digest is invalid,
an e/p entry that is not item-by-item what compound emits, e/p times
at or after AT or decreasing, a duplicate checkpoint packet id, a c
that is not [status-0, status-1, status-2 packet counts, completed
install events], a DATA item t on the wrong side of AT, and a packet
id already present in the checkpoint; pshiftcp code 3 covers a STATE
read error (M=1) or write error (M=0), code 4 a STATE with invalid
UTF-8/JSON syntax, duplicate keys, or non-finite numbers, and code 5
a bad I or M or a STATE whose i,r,f,n,l,e key order, recomputed
content, or h digest (FILE bytes plus the compact JSON prefix
envelope) does not match this invocation; for branch code 3 also covers a
DB read/write error (for ops 1/2/3, also a missing DB; only op 0 may
bootstrap an empty one) and code 5 also covers an invalid OP shape,
name, parent, AT, or DATA, a DB whose entries fail the parent-chain
replay or state check, a same-name commit with a different parent, AT,
or DATA, and an op 2 leaf delete whose target still has child branches
(op 3 deletes the target and every descendant instead; an absent
delete target is idempotent and rewrites nothing).
For policytx code 5 also covers an invalid OP shape, a STATE whose v/r
structure, key order, or version range is invalid, an h that is not a
non-empty array of [version, rule set] pairs with continuous versions
ending exactly at [v, r], an R that is not a valid rule set (every
rule is [n,s,d,a,b,c,path] with n in 0..MAX_COST and
0 <= a <= b <= 65535; s/d/path validation matches the policy
subcommand), a load or rollback whose BASE differs from the current v
or whose v is already MAX_COST, a rollback T absent from h, an op 3
audit T that is not a non-boolean integer in 0..MAX_COST or is absent
from h, an op 4 OUT that is not a non-empty path or that names FILE or
STATE, and the
policy-subcommand S/D/P/C checks on a query; the legacy {"v","r"}
STATE is accepted as h=[[v,r]] and is read-only, never rewritten by
an idempotent op and migrated to v,r,h only by a successful op 0/2
write; op 3 is a read-only history audit and op 4 exports the
normalized {v,r,h} history to OUT without modifying STATE or FILE (a
legacy STATE is exported with h=[[v,r]]); on commit STATE is
atomically replaced with key order v,r,h in
the same compact format and a write failure leaves its bytes
untouched and removes only the staging temp file; an op 4 export
writes OUT via the same exclusive-sibling-staging atomic replace in
the canonical compact UTF-8 form with one trailing LF (directly
usable as a STATE), skips the replace when OUT already holds those
exact bytes, and on failure leaves STATE and OUT's bytes untouched and
removes only its own staging temp file.
policyreplay is read-only and never writes PACK, STATE, or any other
file: it replays the pack topology version TV against the policytx
rule-set version PV. TV/PV are non-boolean integers in 0..MAX_COST; TV
must name a topology in PACK.h and PV a rule-set version in STATE's h
(a legacy STATE's h holds only its v), and the selected rule set must be
legal for the selected topology (every endpoint/path node and path edge
exists there). DATA is a JSON array, possibly empty, of [s, d, p, c]
items that may repeat and keep their order: s/d name selected-topology
nodes (they may be equal), p is a non-boolean integer in 0..65535, and
c is a 1..32 codepoint UTF-8 string. Each query follows policytx
matching (rules by ascending n with ties in array order, endpoint,
port interval, and class match, skipping rules whose path holds a down
edge) with the route lowest-cost path as fallback. The result has key
order topologyVersion, policyVersion, results; each result item is
[s, d, p, c, rule, cost, path] with rule the matched rule's array index
(null on fallback) and null, null, [] when no route exists.
retune takes FILE and LIMIT exactly like rebalance and DATA=[C,G]. C is
a JSON array, possibly empty, using rebalance's [id,s,d,b,path] shape
and all of its per-item validation; its ids are unique. G is non-empty
and holds [0,id] deletions and [1,id,s,d,b] additions with s/d/b
validated as in reserve/rebalance; G ids are unique, every deletion id
must occur in C, and every addition id must not. The target flow set
keeps C's surviving flows in C order, then appends the additions in G
order. The joint search assigns every target flow one up simple path
with sum b no greater than each link's bandwidth and at most LIMIT
surviving flows rerouted (additions never count); feasible assignments
rank by peak used/bandwidth, moved count, and the target-order path
vector with rebalance's exact comparisons. The best feasible
assignment commits (status 1) even without improving the peak; only no
feasible assignment rejects (status 0) and reports C unchanged, with
moved 0. Result key order is status,peak,moved,flows,links: peak is
the before/after peaks as six-decimal fixed-point strings ("0.000000"
for an empty flow set), moved is the surviving-flow reroute count,
flows is the final [id,s,d,b,path] list, and links follows FILE order
as [from,to,bandwidth,used]. An invalid DATA shape is code 5.
loadshift takes FILE and LIMIT exactly like rebalance (FLOWS uses
rebalance's DATA argument position and LIMIT its own), FLOWS being
rebalance's [id,s,d,b,path] array with all of its per-item validation,
and EVENTS a non-empty JSON array of [t,u,v,b] items: t is a non-boolean
integer in 0..MAX_COST and non-decreasing, b is a non-boolean integer in
1..MAX_COST, u->v must name an edge in FILE, and the same edge may not
appear in two events with the same t. The events advance an explicit
clock in order. For each event, b equal to the edge's current bandwidth
is idempotent (status 1) and changes nothing; otherwise the edge's
bandwidth is temporarily set to b and the flows jointly receive one up
simple path each so that every link carries at most its bandwidth and at
most LIMIT flows leave their current path, with feasible assignments
ranked by peak used/bandwidth, moved count, and the FLOWS-order path
vector using rebalance's exact comparisons (fractions by integer
cross-multiplication, paths by Unicode code point order). A feasible
assignment commits atomically (status 0, keeping the temporary
bandwidth); no feasible assignment rejects (status 2) and restores the
prior paths, loads, and bandwidth exactly. Result key order is
events,links. Each events item is [t,status,peak,moved,paths]: status 0
committed, 1 idempotent, 2 rejected; peak is the post-processing peak as
the same six-decimal fixed-point string as a rebalance peak; moved is
the rerouted flow count (0 for idempotent and rejected events); paths
lists each flow's path in FLOWS order after the event. links follows
FILE order as [from,to,bandwidth,used] in the final state. An invalid
EVENTS or FLOWS shape is code 5.
flowshift takes FILE, LIMIT, and FLOWS exactly like loadshift, but its
non-empty EVENTS array mixes six kinds in t order (t as in loadshift,
non-decreasing with equal t kept in input order): [t,0,u,v,b] changes
edge u->v's bandwidth exactly like a loadshift event; [t,1,id,s,d,b]
adds a flow (id/s/d/b validated as in reserve/rebalance) and is appended
after every current flow; [t,2,id] deletes the flow with that id;
[t,3,id,b] changes that flow's demand; [t,4,n,up] brings node n up (up
true) or down (up false); [t,5,u,v,up] brings directed edge u->v up or
down. u->v must name an edge in FILE and n a FILE node, and up must be
a JSON boolean; an invalid shape, type, or reference is code 5. Nodes
start up and every link starts in its FILE up state; an edge is usable
only while it is itself up and both its endpoint nodes are up, so every
path runs solely through up objects. The flow order is FLOWS order with
every addition placed at the tail. A bandwidth or demand equal to the
current value, a node/edge up setting equal to its current state, a
deletion of an absent id, and a repeated addition whose id already
carries the same s/d/b are all idempotent (status 1); re-adding an
existing id with different s/d/b, or changing the demand of an absent
id, is code 5. Every real change jointly assigns the resulting flow set
one usable simple path each with loadshift's capacity and ranking rules
(peak used/bandwidth with integer cross-multiplication, then the number
of pre-existing instances leaving their committed path, then the
flow-order path vector in Unicode code point order); an instance added
by the event being processed has no committed path and never counts as
moved on that event, but does count on every later event. LIMIT counts
only original FLOWS *instances* leaving their current path -- an added
flow never counts, on the event that adds it or any later one, and an
original instance that is deleted and re-created under the same id is a
fresh instance and stays exempt forever (the same rule as retune, taken
per instance rather than per id). A feasible assignment commits
atomically (status 0) and no feasible assignment rejects (status 2)
restoring node states, edge states, bandwidths, the flow set, paths,
and loads exactly as they were. Result key order is events,links. Each
events item is [t,k,status,peak,moved,flows]: peak is the post-processing
peak as the same six-decimal fixed-point string, moved is 0 for
idempotent and rejected events and for committed kind 4/5 rows (the
true reroute count still ranks the joint assignment and counts against
LIMIT), and flows lists [id,s,d,b,path] for
every current flow in the current order. links follows FILE order as
[from,to,bandwidth,used] in the final state. An invalid EVENTS or FLOWS
shape is code 5.
pshift takes FILE and LIMIT exactly like flowshift and FLOWS is the
[id,s,d,b,p,c,path] extension of flowshift's flow shape: id/s/d/b and
path keep flowshift's checks (the given path need not satisfy RULES),
and p/c follow the policytx query checks (p a non-boolean integer in
0..65535, c a 1..32 codepoint UTF-8 string). RULES is a policytx rule
set ([n,s,d,a,b,c,path] rules, c null acting as the class wildcard) and
is the initial rule set; every flow starts with no rule binding (rule
null) even when its given path equals a RULES path, and the initial
placement must already fit as in flowshift. The non-empty EVENTS array
is in non-decreasing t order (equal t kept in input order) with kinds
0 and 2..5 exactly like flowshift, kind 1 as [t,1,id,s,d,b,p,c] with
p/c checked as on the flows, and kind 6 as [t,6,R] with R a policytx
rule set that atomically swaps the current set. A kind 1 re-addition
of a live id is idempotent only when s/d/b/p/c are all identical,
otherwise it is code 5; a kind 6 swap with R equal to the current set
is idempotent. After every real change the joint assignment follows
flowshift exactly except that a flow whose (s,d,p,c) has a first usable
matching rule under policytx matching (rules by ascending n with ties in
array order, endpoint, port interval, and class match, usable only when
every path edge is itself up and both endpoint nodes are up) must take
that rule's single path, while a flow with no usable match enumerates
the usable simple paths; the peak/moved/path-vector ranking, the
marked-instance LIMIT tally, additions-at-tail instance semantics, and
atomic commit with full rollback on rejection are flowshift's. Rule
bindings and paths update only on commit, so a rejected kind 6 or any
other rejected event restores the rule set, node states, edge states,
bandwidths, flows, paths, and loads exactly; an idempotent event keeps
every binding. Result key order is events,links; each event item is
[t,k,status,peak,moved,flows] with status 0/1/2 committed/idempotent/
rejected, moved 0 on idempotent and rejected rows and on committed
kind 4/5 rows, and each flow listed as [id,s,d,b,p,c,rule,path] with
rule the array index of the rule that constrained its committed path
(null when no rule matched) in the current order. links follows FILE
order as [from,to,bandwidth,used] in the final state. The matching pass
adds O(KR) per event (K live flows, R rules) and O(R) space; an invalid
FLOWS, RULES, or EVENTS shape is code 5.
pshiftcp takes FILE LIMIT FLOWS RULES I M STATE EVENTS: FILE,
LIMIT, FLOWS, RULES, and the event semantics match pshift exactly; I is a
non-boolean decimal integer in 0..the number of events and M is 0 or 1.
M=0 parses the whole EVENTS argument's JSON syntax, but validates and
executes only the first I events: an invalid structure or semantic in
any remaining event must not affect the archive. The checkpoint is a
JSON object with key order i,r,f,n,l,e,h: i is I; r is the current rule
set; f follows live flow order as
[id,s,d,b,p,c,initial-instance-boolean,rule,path] (the boolean marks an
original FLOWS instance); n follows FILE node order as [node,up]; l
follows FILE link order as [from,to,up,bandwidth,used]; e is the
prefix's output event rows; h is the lowercase hex SHA-256 of FILE's raw
bytes followed by the compact non-ASCII UTF-8 JSON of
[LIMIT,FLOWS,RULES,EVENTS-prefix,i,r,f,n,l,e]. I=0 archives the initial
state. M=0 writes STATE atomically in that key order, compact
separators, non-ASCII UTF-8, with one trailing LF; stdout is byte-for-
byte identical to those bytes and STATE is rewritten only when its
current bytes differ. M=1 validates and executes every event: it only
reads STATE, checks its key order, fields, and digest against the prefix
state recomputed from this invocation's inputs, then validates and
executes the remaining events from that prefix; it never writes STATE
and its stdout must be byte-for-byte identical to a full pshift run
over all events. STATE read/write errors are code 3; STATE JSON syntax
errors, duplicate keys, and non-finite numbers are code 4; a bad I/M,
STATE key order or content, or a digest mismatch is code 5. On failure
stdout stays empty, STATE keeps its bytes, and stderr is {"error":N}
plus LF.
On failure stdout stays empty and stderr is exactly {"error":N} plus a
newline. A hotload rejection (s=1) is not a failure: it exits 0, leaves
STATE untouched, and reports the slogate gate codes in why.
fragment takes DATA only (no FILE), a JSON array [id,ttl,mtus,hex]:
id is a 1..64 codepoint UTF-8 string, ttl a non-boolean integer in
1..MAX_COST, mtus a non-empty array of non-boolean integers in
25..MAX_COST, and hex a non-empty even-length lowercase hexadecimal
string of at most MAX_COST decoded bytes. The packet starts as one
fragment covering the whole payload. Every hop adds 1 to time and
subtracts 1 from ttl: a ttl reaching 0 drops the packet (status 1,
fragments [], payload null); otherwise the existing fragments are
re-split in ascending offset order with c=mtu-24, taking floor(c/8)*8
bytes while the remainder exceeds c and the whole remainder otherwise;
a take of 0 is code 5. On delivery (status 0) fragments are
[offset,more,data,checksum] in offset order with absolute offsets,
more set iff the fragment ends before the payload, and checksum the
lowercase hex SHA-256 of that fragment's decoded data; payload is the
reassembled original hex. Result key order is
id,status,time,ttl,fragments,payload.
reassemble takes DATA only (no FILE), a non-empty JSON array of
[offset,more,data,checksum] fragments: offset is a non-boolean integer
in 0..MAX_COST, more a boolean, data a non-empty even-length lowercase
hexadecimal string of at most MAX_COST decoded bytes, and checksum the
lowercase hex SHA-256 of that fragment's decoded data. The first
fragment must start at offset 0 and each later offset must equal the
previous offset plus the previous fragment's byte count, so reordering,
overlap, and gaps are all code 5; the total payload must not exceed
MAX_COST bytes. more must be true on every fragment but the last. The
result is the reassembled payload with key order length,payload.
rewrite takes R and D, each a JSON array, possibly empty. R items are
[n,ms,md,a,b,mc,ns,nd,np,nc,k]: n is a non-boolean integer in
0..MAX_COST, a/b are non-boolean integers in 0..65535 with a <= b,
ms/md/mc and ns/nd/nc are each null or a 1..64 codepoint UTF-8 string,
np is null or a non-boolean integer in 0..65535, and k is a non-boolean
integer in 0..MAX_COST. D items are [id,s,d,p,c,ttl,x,h]: id/s/d/c are
non-null strings (id unique across D; their codepoint length is
unconstrained), p a non-boolean integer in 0..65535, ttl a non-boolean
integer in 1..MAX_COST, x an even-length lowercase hexadecimal string
of at most MAX_COST decoded bytes, and h the lowercase hex SHA-256 of
the compact non-ASCII-unescaped UTF-8 JSON array [s,d,p,c,ttl,x].
Rules are considered by ascending n with ties in array order and only
the first matching rule fires: p must lie in a..b and each non-null
ms/md/mc must equal s/d/c (null fields are wildcards). An unmatched
packet keeps every field and its ttl. A matched rule subtracts k from
ttl and rewrites s/d/p/c from ns/nd/np/nc, null there meaning keep the
original field; ttl' <= 0 drops the packet. The output has key order
packets, in D order, each item [id,i,z,q,h]: i is the matched rule's R
index or null, z is 0 when kept and 1 when dropped, a kept entry carries
q=[s,d,p,c,ttl,x] with h recomputed over it and a dropped entry has q
and h null.
wmecmp takes FILE, S, and W exactly like wm (FILE parsed strictly, so
duplicate keys or non-finite numbers are code 4) and FLOW exactly like
ecmp (a 1..MAX_FLOW_LEN codepoint UTF-8 string; an invalid FLOW is code
5). It enumerates every directed simple up path from S and keeps, per
destination, every path minimizing wm's q. Each destination's candidate
first hops are the distinct first hops of those minimum-q paths, sorted
by Unicode code point, each represented by its path with the smallest
code point order. The selected first hop is chosen by the SHA-256 of
the compact non-ASCII-unescaped UTF-8 JSON array [FLOW,S,destination]:
the first 8 digest bytes as a big-endian integer modulo the first-hop
count index the sorted first-hop array. A reachable non-source
destination whose minimum q exceeds MAX_TIME is code 5. The result has
key order s,f,w,r; r is sorted by destination and each item is
[destination, nextHops, selectedNextHop, q, h, x, y, z, path] with
h/x/y/z/path those of the selected first hop's representative path.
The source item is [S,[S],S,0,0,0,null,0,[S]] and an unreachable
destination's item is [destination,[],null,null,null,null,null,null,[]].
lrepair takes FILE S D W DATA: FILE/S/D/W follow lfail, and DATA is a
JSON array, possibly empty, of [t,u,v,up] link items only (t a
non-boolean integer in 0..MAX_COST, non-decreasing with equal t kept in
input order, u->v naming a FILE edge, up a boolean). The primary m is
the lowest-cost S->D path in the initial up-graph, ties going to the
node sequence smallest in Unicode code point order (exactly the
shortest_paths tie-break); no primary, or a primary edge whose repair
does not exist, is code 5. The repair routes b follow the primary's
edge order as [u,v,[cost,path]]: for each primary edge (u, v) delete
that edge and the primary nodes strictly before u, take the
lowest-cost u->D path with the same tie-break, and splice the primary
S..u prefix in front; the reported cost is the prefix cost plus the
suffix cost. Every repair is computed once from the initial up-graph
and never recomputed; a link item only flips that link's up state and
a repeated setting is idempotent and leaves the timer alone. After a
real change the target is the usable primary, else the first all-up
repair in primary-edge order with ties by cost then path order, else
nothing (code 5). A target differing from the installed route (re)arms
a changeover timer at t+W (an overflow past MAX_TIME is code 5); an
equal target cancels any pending timer. Items at one tick run in input
order before a timer expiring on it; a timer due before the next
item's tick completes first, and a timer pending after the last item
keeps advancing. Result key order is s,d,m,b,e,r,f; routes are
[cost,path]. e follows processing order with an input row
[t,0,u,v,up,k,old,target,due] per item (k 1 on a real flip else 0, due
the pending completion time or null, old the installed route before
the item and target the route a pending completion would install, else
the installed one) and a completion row [t,1,old,new,elapsed]; r is
the completion count and f the final installed route.
nrepair takes FILE S D W DATA: FILE/S/D/W follow nfail, and DATA is a
JSON array, possibly empty, of [t,n,up] node items only (t a
non-boolean integer in 0..MAX_COST, non-decreasing with equal t kept in
input order, n naming a FILE node, up a boolean). The primary m is the
lowest-cost S->D path in the initial up-graph, ties going to the node
sequence smallest in Unicode code point order (exactly the
shortest_paths tie-break); no primary, or an internal primary node
whose repair does not exist, is code 5. The repair routes b follow the
primary's internal-node order as [v,[cost,path]]: for each internal
primary node v, with predecessor u, delete v and the primary nodes
strictly before u, take the lowest-cost u->D path with the same
tie-break, and splice the primary S..u prefix in front; the reported
cost is the prefix cost plus the suffix cost. Every repair is computed
once from the initial up-graph and never recomputed; a node item only
flips that node's up state and a repeated setting is idempotent and
leaves the timer alone. After a real change the target is the usable
primary, else the all-up repair with the smallest (cost, path), else
nothing (code 5). A target differing from the installed route (re)arms
a changeover timer at t+W (an overflow past 2**63-1 is code 5); an
equal target cancels any pending timer. Items at one tick run in input
order before a timer expiring on it; a timer due before the next
item's tick completes first, and a timer pending after the last item
keeps advancing. Result key order is s,d,m,b,e,r,f; routes are
[cost,path]. e follows processing order with an input row
[t,0,n,up,k,old,target,due] per item (k 1 on a real flip else 0, due
the pending completion time or null, old the installed route before
the item and target the route a pending completion would install, else
the installed one) and a completion row [t,1,old,new,delay]; r is the
completion count and f the final installed route.
"""

import hashlib
import json
import math
import os
import sys
from bisect import bisect_left, bisect_right
from collections import deque

MAX_COST = 2147483647
MAX_FLOW_LEN = 256
MAX_TIME = 9223372036854775807


def fail(code):
    sys.stderr.write('{"error":%d}\n' % code)
    raise SystemExit(code)


def _reject_constant(value):
    # NaN / Infinity / -Infinity are not valid JSON.
    raise ValueError("invalid JSON constant: " + value)


def _finite_float(text):
    # Reject numbers like 1e999 that parse to a non-finite float.
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite number: " + text)
    return value


def _object_no_dup(pairs):
    # object_pairs_hook rejecting duplicate keys, which JSON objects
    # must not contain here even though json.loads would allow them.
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate key: " + key)
        obj[key] = value
    return obj


def load_network(path, metrics=False, strict=False):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        fail(3)
    except UnicodeDecodeError:
        fail(4)

    try:
        if strict:
            data = json.loads(text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        else:
            data = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        fail(4)

    return _validate_topology(data, metrics)


def _validate_topology(data, metrics=False):
    # Structural checks applied to an already-decoded topology, shared
    # by load_network (FILE mode) and the config pack validator (the t
    # member, which follows metric's FILE mode). With metrics=True the
    # links must also carry bandwidth/latency, as in metric's FILE.
    if not isinstance(data, dict) or set(data) != {"nodes", "links"}:
        fail(5)
    nodes = data["nodes"]
    links = data["links"]

    base_keys = {"from", "to", "cost", "up"}
    link_keys = base_keys | {"bandwidth", "latency"} if metrics else base_keys

    if not isinstance(nodes, list):
        fail(5)
    node_set = set()
    for n in nodes:
        if type(n) is not str or n == "" or n in node_set:
            fail(5)
        node_set.add(n)

    if not isinstance(links, list):
        fail(5)
    seen_pairs = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != link_keys:
            fail(5)
        frm = link["from"]
        to = link["to"]
        cost = link["cost"]
        up = link["up"]
        if type(frm) is not str or type(to) is not str:
            fail(5)
        if frm not in node_set or to not in node_set or frm == to:
            fail(5)
        if type(cost) is not int or not 1 <= cost <= MAX_COST:
            fail(5)
        if type(up) is not bool:
            fail(5)
        if metrics:
            bw = link["bandwidth"]
            lat = link["latency"]
            if type(bw) is not int or not 1 <= bw <= MAX_COST:
                fail(5)
            if type(lat) is not int or not 0 <= lat <= MAX_COST:
                fail(5)
        pair = (frm, to)
        if pair in seen_pairs:
            fail(5)
        seen_pairs.add(pair)

    return nodes, links, node_set


def shortest_paths(nodes, links, source):
    # Directed adjacency over up links only.
    adj = {n: [] for n in nodes}
    for link in links:
        if link["up"]:
            adj[link["from"]].append((link["to"], link["cost"]))

    cost_of = {n: None for n in nodes}
    path_of = {n: None for n in nodes}
    cost_of[source] = 0
    path_of[source] = [source]
    settled = set()

    # Dijkstra with O(V^2) selection. All link costs are >= 1, so every
    # predecessor of a lowest-cost path has a strictly smaller cost and is
    # settled before the node itself; hence only costs are compared during
    # selection, and full path sequences only during relaxation ties.
    while True:
        u = None
        ucost = None
        for n in nodes:
            c = cost_of[n]
            if c is not None and n not in settled and (ucost is None or c < ucost):
                u = n
                ucost = c
        if u is None:
            break
        settled.add(u)
        upath = path_of[u]
        for to, w in adj[u]:
            if to in settled:
                continue
            nc = ucost + w
            cc = cost_of[to]
            if cc is None or nc < cc:
                cost_of[to] = nc
                path_of[to] = upath + [to]
            elif nc == cc:
                cand = upath + [to]
                if cand < path_of[to]:
                    path_of[to] = cand
    return cost_of, path_of


def compute_routes(nodes, links, source):
    cost_of, path_of = shortest_paths(nodes, links, source)

    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append({"destination": n, "nextHop": source, "cost": 0,
                           "path": [source]})
        elif cost_of[n] is None:
            routes.append({"destination": n, "nextHop": None, "cost": None,
                           "path": []})
        else:
            p = path_of[n]
            routes.append({"destination": n, "nextHop": p[1],
                           "cost": cost_of[n], "path": p})
    return {"source": source, "routes": routes}


def compute_metric(nodes, links, source, order_names):
    # Directed adjacency over up links only.
    adj = {n: [] for n in nodes}
    for link in links:
        if link["up"]:
            adj[link["from"]].append(
                (link["to"], link["cost"], link["bandwidth"], link["latency"]))

    # Enumerate every directed simple path from the source via DFS and keep
    # the best one per destination under the ORDER metric hierarchy. Ties on
    # every metric go to the path with the smallest Unicode code point order.
    # best[n] = (comparison_key, (hop, cost, bandwidth, latency), path)
    best = {}

    def metric_key(hop_count, cost, bandwidth, latency):
        m = {"hop": hop_count, "cost": cost, "bandwidth": bandwidth,
             "latency": latency}
        # bandwidth prefers the larger value; the others the smaller.
        return tuple(-m[name] if name == "bandwidth" else m[name]
                     for name in order_names)

    def consider(path, hop_count, cost, bandwidth, latency):
        key = metric_key(hop_count, cost, bandwidth, latency)
        dest = path[-1]
        cur = best.get(dest)
        if cur is None or key < cur[0] or (key == cur[0] and path < cur[2]):
            best[dest] = (key, (hop_count, cost, bandwidth, latency),
                          list(path))

    # Iterative DFS with an explicit stack, so the enumeration depth is
    # bounded by heap, not by the Python recursion limit. metrics[d] holds
    # the accumulated (hop, cost, bandwidth, latency) for path[:d+1].
    path = [source]
    visited = {source}
    metrics = [(0, 0, MAX_COST, 0)]
    consider(path, 0, 0, MAX_COST, 0)
    stack = [iter(adj[source])]
    while stack:
        try:
            to, w, bw, lat = next(stack[-1])
        except StopIteration:
            stack.pop()
            if stack:
                metrics.pop()
                visited.remove(path.pop())
            continue
        if to in visited:
            continue
        visited.add(to)
        path.append(to)
        hop_count, cost, bandwidth, latency = metrics[-1]
        entry = (hop_count + 1, cost + w, min(bandwidth, bw), latency + lat)
        metrics.append(entry)
        consider(path, *entry)
        stack.append(iter(adj[to]))

    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append({"destination": n, "nextHop": source, "hopCount": 0,
                           "cost": 0, "bandwidth": None, "latency": 0,
                           "path": [source]})
        elif n not in best:
            routes.append({"destination": n, "nextHop": None, "hopCount": None,
                           "cost": None, "bandwidth": None, "latency": None,
                           "path": []})
        else:
            _, (hop_count, cost, bandwidth, latency), path = best[n]
            routes.append({"destination": n, "nextHop": path[1],
                           "hopCount": hop_count, "cost": cost,
                           "bandwidth": bandwidth, "latency": latency,
                           "path": path})
    return {"source": source, "order": order_names, "routes": routes}


def compute_wm(nodes, links, source, weights):
    # Directed adjacency over up links only.
    adj = {n: [] for n in nodes}
    for link in links:
        if link["up"]:
            adj[link["from"]].append(
                (link["to"], link["cost"], link["bandwidth"], link["latency"]))

    a, b, c, d = weights

    # Enumerate every directed simple path from the source via DFS (same
    # enumeration as compute_metric) and keep, per destination, the path
    # minimizing q = a*h + b*x + c*(M-y) + d*z with exact integer
    # arithmetic, where h/x/y/z are the hop count, cost sum, bottleneck
    # bandwidth, and latency sum. Ties on q go to the path with the
    # smallest Unicode code point order.
    # best[n] = (q, (hop, cost, bandwidth, latency), path)
    best = {}

    def consider(path, hop_count, cost, bandwidth, latency):
        q = (a * hop_count + b * cost + c * (MAX_COST - bandwidth)
             + d * latency)
        dest = path[-1]
        cur = best.get(dest)
        if cur is None or q < cur[0] or (q == cur[0] and path < cur[2]):
            best[dest] = (q, (hop_count, cost, bandwidth, latency),
                          list(path))

    # Iterative DFS with an explicit stack, so the enumeration depth is
    # bounded by heap, not by the Python recursion limit. metrics[d] holds
    # the accumulated (hop, cost, bandwidth, latency) for path[:d+1].
    path = [source]
    visited = {source}
    metrics = [(0, 0, MAX_COST, 0)]
    consider(path, 0, 0, MAX_COST, 0)
    stack = [iter(adj[source])]
    while stack:
        try:
            to, w, bw, lat = next(stack[-1])
        except StopIteration:
            stack.pop()
            if stack:
                metrics.pop()
                visited.remove(path.pop())
            continue
        if to in visited:
            continue
        visited.add(to)
        path.append(to)
        hop_count, cost, bandwidth, latency = metrics[-1]
        entry = (hop_count + 1, cost + w, min(bandwidth, bw), latency + lat)
        metrics.append(entry)
        consider(path, *entry)
        stack.append(iter(adj[to]))

    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append([n, source, 0, 0, 0, None, 0, [source]])
        elif n not in best:
            routes.append([n, None, None, None, None, None, None, []])
        else:
            q, (hop_count, cost, bandwidth, latency), path = best[n]
            if q > MAX_TIME:
                fail(5)
            routes.append([n, path[1], q, hop_count, cost, bandwidth,
                           latency, path])
    return {"s": source, "w": [a, b, c, d], "r": routes}


def compute_wmecmp(nodes, links, source, flow, weights):
    # Directed adjacency over up links only.
    adj = {n: [] for n in nodes}
    for link in links:
        if link["up"]:
            adj[link["from"]].append(
                (link["to"], link["cost"], link["bandwidth"], link["latency"]))

    a, b, c, d = weights

    # Enumerate every directed simple path from the source via DFS (same
    # enumeration as compute_wm) and keep, per destination, every path
    # minimizing q = a*h + b*x + c*(M-y) + d*z with exact integer
    # arithmetic, where h/x/y/z are the hop count, cost sum, bottleneck
    # bandwidth, and latency sum. The minimum-q paths are grouped by
    # first hop; each first hop is represented by its path with the
    # smallest Unicode code point order.
    # best[n] = (q, {first_hop: ((hop, cost, bandwidth, latency), path)})
    best = {}

    def consider(path, hop_count, cost, bandwidth, latency):
        q = (a * hop_count + b * cost + c * (MAX_COST - bandwidth)
             + d * latency)
        dest = path[-1]
        first = path[1]
        entry = ((hop_count, cost, bandwidth, latency), list(path))
        cur = best.get(dest)
        if cur is None or q < cur[0]:
            best[dest] = (q, {first: entry})
        elif q == cur[0]:
            hops = cur[1]
            old = hops.get(first)
            if old is None or path < old[1]:
                hops[first] = entry

    # Iterative DFS with an explicit stack, so the enumeration depth is
    # bounded by heap, not by the Python recursion limit. metrics[d] holds
    # the accumulated (hop, cost, bandwidth, latency) for path[:d+1].
    path = [source]
    visited = {source}
    metrics = [(0, 0, MAX_COST, 0)]
    stack = [iter(adj[source])]
    while stack:
        try:
            to, w, bw, lat = next(stack[-1])
        except StopIteration:
            stack.pop()
            if stack:
                metrics.pop()
                visited.remove(path.pop())
            continue
        if to in visited:
            continue
        visited.add(to)
        path.append(to)
        hop_count, cost, bandwidth, latency = metrics[-1]
        entry = (hop_count + 1, cost + w, min(bandwidth, bw), latency + lat)
        metrics.append(entry)
        consider(path, *entry)
        stack.append(iter(adj[to]))

    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append([n, [source], source, 0, 0, 0, None, 0,
                           [source]])
        elif n not in best:
            routes.append([n, [], None, None, None, None, None, None, []])
        else:
            q, hops = best[n]
            if q > MAX_TIME:
                fail(5)
            # Candidate first hops: deduplicated and sorted by Unicode
            # code point.
            first_hops = sorted(hops)
            key = json.dumps([flow, source, n], ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
            digest = hashlib.sha256(key).digest()
            selected = first_hops[int.from_bytes(digest[:8], "big")
                                  % len(first_hops)]
            (hop_count, cost, bandwidth, latency), rep = hops[selected]
            routes.append([n, first_hops, selected, q, hop_count, cost,
                           bandwidth, latency, rep])
    return {"s": source, "f": flow, "w": [a, b, c, d], "r": routes}


def compute_ecmp(nodes, links, source, flow):
    cost_of, _ = shortest_paths(nodes, links, source)

    # Candidate first hops: targets of up links out of the source.
    first_cost = {}
    for link in links:
        if link["up"] and link["from"] == source:
            first_cost[link["to"]] = link["cost"]

    # Lowest-cost, lexicographically smallest paths from each candidate
    # first hop, so the best equal-cost full path via any of them can be
    # rebuilt as [source] + hop_path.
    hop_cost = {}
    hop_path = {}
    for h in first_cost:
        hop_cost[h], hop_path[h] = shortest_paths(nodes, links, h)

    routes = []
    for n in sorted(nodes):
        if n == source:
            routes.append({"destination": n, "nextHops": [source],
                           "selectedNextHop": source, "cost": 0,
                           "path": [source]})
            continue
        total = cost_of[n]
        if total is None:
            routes.append({"destination": n, "nextHops": [],
                           "selectedNextHop": None, "cost": None, "path": []})
            continue
        # A first hop is usable iff some lowest-cost path to n starts with
        # it; hops are deduplicated and sorted by Unicode code point.
        hops = sorted(
            h for h, w in first_cost.items()
            if hop_cost[h][n] is not None and w + hop_cost[h][n] == total
        )
        key = json.dumps([flow, source, n], ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(key).digest()
        selected = hops[int.from_bytes(digest[:8], "big") % len(hops)]
        routes.append({"destination": n, "nextHops": hops,
                       "selectedNextHop": selected, "cost": total,
                       "path": [source] + hop_path[selected][n]})
    return {"source": source, "flow": flow, "routes": routes}


def compute_protect(nodes, links, source, destination, delay, events):
    # Primary: lowest-cost path in the initial up-graph. Backup: lowest-cost
    # path after removing the primary's directed edges. Both are computed
    # once here and never recomputed; events only flip link states.
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_cost = cost_of[destination]
    primary_path = path_of[destination]
    if primary_path is None:
        backup_cost = None
        backup_path = None
    else:
        removed = set(zip(primary_path, primary_path[1:]))
        backup_links = [link for link in up_links
                        if (link["from"], link["to"]) not in removed]
        bcost_of, bpath_of = shortest_paths(nodes, backup_links, source)
        backup_cost = bcost_of[destination]
        backup_path = bpath_of[destination]

    state = {(link["from"], link["to"]): link["up"] for link in links}

    def usable(path):
        return (path is not None
                and all(state[pair] for pair in zip(path, path[1:])))

    def selected():
        # Prefer an available primary, then the backup, else no path.
        if usable(primary_path):
            return primary_path
        if usable(backup_path):
            return backup_path
        return None

    results = []
    current = selected()
    for event in events:
        before = current if current is not None else []
        pair = (event["from"], event["to"])
        if state[pair] == event["up"]:
            # Repeated setting is idempotent.
            reason = 0
            switch_time = None
            after = before
        else:
            state[pair] = event["up"]
            new = selected()
            after = new if new is not None else []
            if after == before:
                reason = 1
                switch_time = None
            else:
                switch_time = event["time"] + delay
                if new is primary_path:
                    reason = 2
                elif new is None:
                    reason = 5
                elif current is primary_path:
                    reason = 3
                else:
                    reason = 4
            current = new
        results.append({"time": event["time"], "from": event["from"],
                        "to": event["to"], "up": event["up"],
                        "switchTime": switch_time, "reason": reason,
                        "before": before, "after": after})

    return {"source": source, "destination": destination,
            "primary": {"cost": primary_cost, "path": primary_path or []},
            "backup": {"cost": backup_cost, "path": backup_path or []},
            "events": results}


def compute_forward(links, source, destination, limit, table):
    # Hop-by-hop forwarding along the explicit next-hop table, over up
    # links only. seen holds every trace node before the current one, so
    # arriving at a node already departed means the trace has a loop.
    up_pairs = {(link["from"], link["to"]) for link in links if link["up"]}
    trace = [[0, source]]
    seen = set()
    current = source
    time = 0
    hops = 0
    while True:
        if current == destination:
            status = "delivered"
            break
        if current in seen:
            status = "loop"
            break
        if hops == limit:
            status = "hop_limit"
            break
        nxt = table[current]
        if nxt is None or (current, nxt) not in up_pairs:
            status = "unreachable"
            break
        seen.add(current)
        current = nxt
        time += 1
        hops += 1
        trace.append([time, current])
    return {"source": source, "destination": destination, "limit": limit,
            "status": status, "time": time, "trace": trace}


def _bounded_int_arg(text):
    # Decimal command-line integer in [0, MAX_COST]. Leading zeros are
    # stripped before int() so absurdly long digit strings cannot trip
    # Python's integer conversion digit limit.
    if not text or any(c not in "0123456789" for c in text):
        fail(5)
    digits = text.lstrip("0") or "0"
    if len(digits) > 10:
        fail(5)
    value = int(digits)
    if value > MAX_COST:
        fail(5)
    return value


def compute_queue(frm, to, cap, step, packets):
    # Store-and-forward shaper on a single directed link. A packet holds
    # buffer space from its arrival until its departure; starts are never
    # earlier than the previous departure, so departures leave the buffer
    # in FIFO order and a deque gives O(1) amortized release per packet.
    buffer = deque()  # (depart, size) of packets still occupying capacity
    occupancy = 0
    last_depart = 0
    results = []
    for pid, time, size in packets:
        while buffer and buffer[0][0] <= time:
            occupancy -= buffer.popleft()[1]
        if occupancy + size > cap:
            # Dropped packets do not alter the schedule.
            results.append([pid, "drop", None, None, None])
            continue
        start = time if time > last_depart else last_depart
        depart = start + size * step
        if depart > MAX_TIME:
            fail(5)
        last_depart = depart
        occupancy += size
        buffer.append((depart, size))
        results.append([pid, "ok", start, depart, start - time])
    return {"from": frm, "to": to, "cap": cap, "step": step,
            "packets": results}


def compute_fragment(ident, ttl, mtus, payload):
    # Explicit per-hop clock fragmentation with no merging. The packet
    # starts as one fragment covering the whole payload; each link hop
    # adds 1 to time and subtracts 1 from ttl. A ttl that reaches 0
    # drops the packet before that hop refragments anything. Otherwise
    # the current fragments are re-split in ascending offset order with
    # c = mtu - 24: a remainder longer than c yields floor(c/8)*8 bytes,
    # any other remainder is taken whole, and a zero take is an error.
    # Splitting only shrinks pieces, so the fragment list stays sorted
    # and contiguous, offsets stay absolute, and the final fragment
    # bytes concatenate back to the payload exactly.
    pieces = [(0, payload)]
    time = 0
    for mtu in mtus:
        time += 1
        ttl -= 1
        if ttl == 0:
            return {"id": ident, "status": 1, "time": time, "ttl": 0,
                    "fragments": [], "payload": None}
        c = mtu - 24
        next_pieces = []
        for abs_off, blob in pieces:
            pos = 0
            length = len(blob)
            while pos < length:
                remaining = length - pos
                if remaining > c:
                    take = (c // 8) * 8
                else:
                    take = remaining
                if take == 0:
                    fail(5)
                next_pieces.append((abs_off + pos, blob[pos:pos + take]))
                pos += take
        pieces = next_pieces
    fragments = []
    reassembled = bytearray()
    payload_len = len(payload)
    for offset, blob in pieces:
        reassembled.extend(blob)
        fragments.append([offset, offset + len(blob) < payload_len,
                          blob.hex(),
                          hashlib.sha256(blob).hexdigest()])
    return {"id": ident, "status": 0, "time": time, "ttl": ttl,
            "fragments": fragments, "payload": bytes(reassembled).hex()}


def _rewrite_digest(s, d, p, c, ttl, x):
    # Lowercase hex SHA-256 of the compact non-ASCII-unescaped UTF-8
    # JSON array [s,d,p,c,ttl,x], exactly the h contract of rewrite.
    payload = json.dumps([s, d, p, c, ttl, x], ensure_ascii=False,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_rewrite(rules, packets):
    # Stateless rewrite table. Each packet scans R in array order and
    # keeps the matching rule with the smallest n, replacing the holder
    # only on a strictly smaller n, so equal n keeps the earliest rule in
    # array order; the scan is an O(RK) linear search. A rule matches
    # when its a..b port interval contains p and every non-null
    # ms/md/mc equals the packet's s/d/c (null = wildcard). Unmatched
    # packets pass through with index null and untouched ttl. A matched
    # rule subtracts k and rewrites s/d/p/c from ns/nd/np/nc, where null
    # means keep the original field; ttl' <= 0 drops the packet,
    # otherwise h is recomputed over the rewritten fields.
    results = []
    for ident, s, d, p, c, ttl, x, _h in packets:
        best_index = None
        best_n = None
        best_rule = None
        for index, rule in enumerate(rules):
            _n, ms, md, a, b, mc = rule[:6]
            if p < a or p > b:
                continue
            if ms is not None and s != ms:
                continue
            if md is not None and d != md:
                continue
            if mc is not None and c != mc:
                continue
            if best_index is None or _n < best_n:
                best_index, best_n, best_rule = index, _n, rule
        if best_index is None:
            results.append([ident, None, 0, [s, d, p, c, ttl, x],
                            _rewrite_digest(s, d, p, c, ttl, x)])
            continue
        ns, nd, nport, nc, k = best_rule[6], best_rule[7], \
            best_rule[8], best_rule[9], best_rule[10]
        new_ttl = ttl - k
        if new_ttl <= 0:
            results.append([ident, best_index, 1, None, None])
            continue
        s2 = ns if ns is not None else s
        d2 = nd if nd is not None else d
        p2 = nport if nport is not None else p
        c2 = nc if nc is not None else c
        results.append([ident, best_index, 0,
                        [s2, d2, p2, c2, new_ttl, x],
                        _rewrite_digest(s2, d2, p2, c2, new_ttl, x)])
    return {"packets": results}


def compute_reorder(frm, to, base, window, packets):
    # Reorder buffer on a single directed up link. Events are processed in
    # (arrival, seq) order with an explicit clock that jumps to each
    # arrival; a packet too far ahead of the next expected sequence number
    # is dropped, otherwise it is buffered and every contiguous packet
    # from next onward is released at the current clock. Each sequence
    # number arrives once and next never passes an unreleased one, so a
    # dict keyed by seq gives O(1) amortized release per packet.
    events = sorted(packets, key=lambda p: (p[2], p[1]))
    next_seq = 0
    pending = {}  # seq -> index of the packet's entry in results
    results = []
    for pid, seq, arrival in events:
        if seq - next_seq > window:
            # Dropped packets do not alter the buffer.
            results.append([pid, seq, arrival, "over_window", None, None])
            continue
        pending[seq] = len(results)
        results.append([pid, seq, arrival, "buffered", None, None])
        while next_seq in pending:
            entry = results[pending.pop(next_seq)]
            entry[3] = "released"
            entry[4] = arrival
            entry[5] = arrival - entry[2]
            next_seq += 1
    return {"from": frm, "to": to, "base": base, "window": window,
            "packets": results}


def compute_converge(nodes, links, source, destination, delay, run, events):
    # Debounced route recomputation after link changes. The clock starts at
    # 0 with the initial route installed. Events are applied first at each
    # tick; a real change cancels any outstanding cycle and rearms the
    # trigger at t+D and completion at t+D+R. The trigger recomputes the
    # shortest path over the current topology and the completion installs
    # it; a change in between invalidates the pending result and restarts
    # the cycle. Setting a link to its current state changes nothing and
    # leaves the timer untouched.
    state = {(link["from"], link["to"]): link["up"] for link in links}

    def live_links():
        # shortest_paths reads each dict's "up" flag, so mirror the current
        # state there rather than relying on the original link values.
        return [{**link, "up": state[(link["from"], link["to"])]}
                for link in links
                if state[(link["from"], link["to"])]]

    cost_of, path_of = shortest_paths(nodes, live_links(), source)
    installed_cost = cost_of[destination]
    installed_path = path_of[destination]

    def reachable(path):
        return path is not None and all(
            state[pair] for pair in zip(path, path[1:]))

    def entry(now, kind):
        # The last three fields always describe the currently installed
        # route: an installed path keeps its cost and path even while a
        # down edge makes it unreachable; nothing installed means no
        # route at all.
        if installed_path is None:
            return [now, kind, None, [], False]
        return [now, kind, installed_cost, installed_path,
                reachable(installed_path)]

    timeline = [entry(0, 0)]

    trigger_at = None
    complete_at = None
    pending_cost = None
    pending_path = None
    i = 0
    n = len(events)
    while i < n or trigger_at is not None or complete_at is not None:
        wakes = []
        if i < n:
            wakes.append(events[i]["time"])
        if trigger_at is not None:
            wakes.append(trigger_at)
        if complete_at is not None:
            wakes.append(complete_at)
        now = min(wakes)
        # All events at this tick run before either timer, and the trigger
        # at the same tick fires before the completion.
        while i < n and events[i]["time"] == now:
            event = events[i]
            pair = (event["from"], event["to"])
            i += 1
            if state[pair] != event["up"]:
                # Every real change cancels the unfinished cycle (whether
                # or not the trigger has fired) and rearms both timers.
                state[pair] = event["up"]
                trigger_at = now + delay
                complete_at = trigger_at + run
                if complete_at > MAX_TIME:
                    fail(5)
                pending_cost = None
                pending_path = None
            timeline.append(entry(now, 1))
        if trigger_at is not None and trigger_at == now:
            cost_of, path_of = shortest_paths(nodes, live_links(), source)
            pending_cost = cost_of[destination]
            pending_path = path_of[destination]
            trigger_at = None
            timeline.append(entry(now, 2))
        if complete_at is not None and complete_at == now:
            installed_cost = pending_cost
            installed_path = pending_path
            complete_at = None
            pending_cost = None
            pending_path = None
            timeline.append(entry(now, 3))

    return {"timeline": timeline}


def _priority_order(rules):
    # Indices of rules sorted by ascending priority n, ties keeping
    # array order. LSD radix sort over the 32-bit non-negative keys:
    # four stable 256-bucket counting passes give worst-case O(R) time
    # and O(R) space for any rule count R, where a comparison sort
    # would only guarantee O(R log R).
    order = list(range(len(rules)))
    for shift in (0, 8, 16, 24):
        buckets = [[] for _ in range(256)]
        for i in order:
            buckets[(rules[i][0] >> shift) & 0xFF].append(i)
        order = [i for bucket in buckets for i in bucket]
    return order


def compute_policy(nodes, links, source, destination, port, klass, rules):
    # Policy routing with a shortest-path fallback. Rules are considered
    # by ascending priority n (ties keep their array order, which the
    # stable radix sort in _priority_order guarantees); a rule matches when its s/d equal the
    # requested source/destination and its null port/class fields act as
    # wildcards while the rest compare equal. The first matching rule
    # whose path has no down edge supplies the route; with none usable
    # the route falls back to the lowest-cost path over up links.
    up_of = {}
    cost_of_link = {}
    for link in links:
        pair = (link["from"], link["to"])
        up_of[pair] = link["up"]
        cost_of_link[pair] = link["cost"]

    for i in _priority_order(rules):
        _, s, d, p, c, path = rules[i]
        if s != source or d != destination:
            continue
        if p is not None and p != port:
            continue
        if c is not None and c != klass:
            continue
        pairs = list(zip(path, path[1:]))
        if not all(up_of[pair] for pair in pairs):
            # Paths with a down edge are skipped, not fallen back from.
            continue
        return {"source": source, "destination": destination,
                "port": port, "class": klass, "rule": i,
                "cost": sum(cost_of_link[pair] for pair in pairs),
                "path": path}

    cost_of, path_of = shortest_paths(nodes, links, source)
    cost = cost_of[destination]
    path = path_of[destination]
    return {"source": source, "destination": destination,
            "port": port, "class": klass, "rule": None,
            "cost": cost, "path": path if path is not None else []}


def compute_policytx(nodes, links, source, destination, port, klass,
                     rules):
    # Read-only policy transaction query over interval-port rules: each
    # rule is (n, s, d, a, b, c, path) and matches when s/d equal the
    # request, a <= port <= b, c is null (wildcard) or equal, and every
    # path edge is up. Rules are considered by ascending n with ties
    # keeping array order (_priority_order, as in compute_policy); the
    # first match is reported as [index, cost, path]. With no usable
    # rule the route subcommand's lowest-cost up-link path is the
    # fallback, reported as [null, cost, path], or [null, null, []] when
    # the destination is unreachable.
    up_of = {}
    cost_of_link = {}
    for link in links:
        pair = (link["from"], link["to"])
        up_of[pair] = link["up"]
        cost_of_link[pair] = link["cost"]

    for i in _priority_order(rules):
        _, s, d, a, b, c, path = rules[i]
        if s != source or d != destination:
            continue
        if not a <= port <= b:
            continue
        if c is not None and c != klass:
            continue
        pairs = list(zip(path, path[1:]))
        if not all(up_of[pair] for pair in pairs):
            # Paths with a down edge are skipped, not fallen back from.
            continue
        return [i, sum(cost_of_link[pair] for pair in pairs), path]

    cost_of, path_of = shortest_paths(nodes, links, source)
    cost = cost_of[destination]
    path = path_of[destination]
    return [None, cost, path if path is not None else []]


def compute_reserve(nodes, links, requests):
    # Bandwidth reservation over up directed simple paths, processed in
    # request order. residual[i] is the remaining capacity of links[i];
    # each accepted request decrements it along its path and rejections
    # leave it untouched. Candidates are ranked by the post-reservation
    # utilization max((C-r+b)/C) — compared as fractions with integer
    # cross-multiplication, never floats — then cost sum, then the
    # path's Unicode code point order.
    adj = {n: [] for n in nodes}
    index_of = {}
    for index, link in enumerate(links):
        index_of[(link["from"], link["to"])] = index
        if link["up"]:
            adj[link["from"]].append((link["to"], link["cost"], index))
    capacity = [link["bandwidth"] for link in links]
    residual = list(capacity)

    allocations = []
    for rid, source, destination, b in requests:
        # Reachability ignores residual capacity: it distinguishes
        # "unreachable" (no up path at all) from "no_capacity".
        seen = {source}
        stack = [source]
        while stack:
            for to, _, _ in adj[stack.pop()]:
                if to not in seen:
                    seen.add(to)
                    stack.append(to)
        if destination not in seen:
            allocations.append([rid, "unreachable", b, None, []])
            continue

        # Enumerate every up simple path whose edges all have residual
        # >= b via iterative DFS, keeping the best candidate. states[d]
        # holds (util_num, util_den, cost) for path[:d+1]: the running
        # maximum utilization fraction and the cost sum.
        best_num = best_den = best_cost = None
        best_path = None
        path = [source]
        visited = {source}
        states = [(0, 1, 0)]
        iters = [iter(adj[source])]
        while iters:
            try:
                to, w, index = next(iters[-1])
            except StopIteration:
                iters.pop()
                if iters:
                    states.pop()
                    visited.remove(path.pop())
                continue
            if to in visited or residual[index] < b:
                continue
            num, den, cost = states[-1]
            e_num = capacity[index] - residual[index] + b
            e_den = capacity[index]
            if e_num * den > num * e_den:
                num, den = e_num, e_den
            cost += w
            visited.add(to)
            path.append(to)
            if to == destination:
                if (best_path is None
                        or num * best_den < best_num * den
                        or (num * best_den == best_num * den
                            and (cost < best_cost
                                 or (cost == best_cost
                                     and path < best_path)))):
                    best_num, best_den, best_cost = num, den, cost
                    best_path = list(path)
                # A simple path cannot pass through the destination and
                # return to it, so nothing extends past it.
                visited.remove(path.pop())
            else:
                states.append((num, den, cost))
                iters.append(iter(adj[to]))

        if best_path is None:
            allocations.append([rid, "no_capacity", b, None, []])
            continue
        if best_cost > MAX_TIME:
            fail(5)
        for a, c in zip(best_path, best_path[1:]):
            residual[index_of[(a, c)]] -= b
        allocations.append([rid, "accepted", b, best_cost, best_path])

    return {"allocations": allocations,
            "links": [[link["from"], link["to"], capacity[i],
                       capacity[i] - residual[i], residual[i]]
                      for i, link in enumerate(links)]}


def _format_peak(num, den):
    # num/den rounded half up to exactly six decimals, computed in
    # integers so no float rounding can leak into the output.
    scaled = (2 * num * 1000000 + den) // (2 * den)
    return "%d.%06d" % (scaled // 1000000, scaled % 1000000)


def compute_rebalance(nodes, links, demands, limit):
    # Joint path reallocation minimizing the peak link utilization. Every
    # demand keeps exactly one up simple path; an assignment is feasible
    # when no link carries more than its bandwidth and at most `limit`
    # demands leave their original path. Feasible assignments are ranked
    # by peak used/bandwidth (fractions compared with integer cross-
    # multiplication, never floats), then by the number of rerouted
    # demands, then by the DATA-order vector of paths in Unicode code
    # point order. The best assignment is committed atomically only when
    # its peak is strictly below the initial one. The search enumerates
    # the Cartesian product of the per-demand simple-path sets with an
    # explicit stack — O((V!)^K (KV+E)) time, O(KV+E) space — pruning
    # branches that already violate capacity or the reroute limit.
    adj = {n: [] for n in nodes}
    index_of = {}
    for index, link in enumerate(links):
        index_of[(link["from"], link["to"])] = index
        if link["up"]:
            adj[link["from"]].append((link["to"], index))
    capacity = [link["bandwidth"] for link in links]

    initial_used = [0] * len(links)
    for _, _, _, b, path in demands:
        for a, c in zip(path, path[1:]):
            initial_used[index_of[(a, c)]] += b
    for index, used_here in enumerate(initial_used):
        if used_here > capacity[index]:
            # The initial placement must already fit every link.
            fail(5)

    def peak_of(used):
        # max(used[i]/capacity[i]) as an exact fraction.
        num, den = 0, 1
        for u, c in zip(used, capacity):
            if u * den > num * c:
                num, den = u, c
        return num, den

    init_num, init_den = peak_of(initial_used)

    def enum_paths(source, destination):
        # Yield (path, edge_indices) for every up simple path from
        # source to destination via iterative DFS, so the enumeration
        # depth is bounded by heap, not by the Python recursion limit.
        path = [source]
        edges = []
        visited = {source}
        iters = [iter(adj[source])]
        while iters:
            try:
                to, index = next(iters[-1])
            except StopIteration:
                iters.pop()
                if iters:
                    visited.remove(path.pop())
                    edges.pop()
                continue
            if to in visited:
                continue
            visited.add(to)
            path.append(to)
            edges.append(index)
            if to == destination:
                yield list(path), list(edges)
                visited.remove(path.pop())
                edges.pop()
            else:
                iters.append(iter(adj[to]))

    best_num = best_den = best_moved = None
    best_paths = best_used = None
    count = len(demands)
    if count:
        used = [0] * len(links)
        current_paths = [None] * count
        current_edges = [None] * count
        generators = [None] * count
        moved = 0
        depth = 0
        generators[0] = enum_paths(demands[0][1], demands[0][2])
        while depth >= 0:
            item = next(generators[depth], None)
            if item is None:
                # The level's paths are exhausted: backtrack and undo
                # the shallower level's assignment.
                generators[depth] = None
                depth -= 1
                if depth >= 0:
                    b = demands[depth][3]
                    for index in current_edges[depth]:
                        used[index] -= b
                    if current_paths[depth] != demands[depth][4]:
                        moved -= 1
                    current_paths[depth] = None
                    current_edges[depth] = None
                continue
            path, edges = item
            b = demands[depth][3]
            if any(used[index] + b > capacity[index] for index in edges):
                continue
            delta = 1 if path != demands[depth][4] else 0
            if moved + delta > limit:
                continue
            for index in edges:
                used[index] += b
            current_paths[depth] = path
            current_edges[depth] = edges
            moved += delta
            if depth + 1 < count:
                depth += 1
                generators[depth] = enum_paths(demands[depth][1],
                                               demands[depth][2])
            else:
                num, den = peak_of(used)
                if (best_paths is None
                        or num * best_den < best_num * den
                        or (num * best_den == best_num * den
                            and (moved < best_moved
                                 or (moved == best_moved
                                     and current_paths < best_paths)))):
                    best_num, best_den = num, den
                    best_moved = moved
                    best_paths = list(current_paths)
                    best_used = list(used)
                for index in edges:
                    used[index] -= b
                moved -= delta
                current_paths[depth] = None
                current_edges[depth] = None

    if best_paths is not None and best_num * init_den < init_num * best_den:
        status = 1
        final_used = best_used
        new_paths = best_paths
        moved_out = best_moved
        out_num, out_den = best_num, best_den
    else:
        status = 0
        final_used = initial_used
        new_paths = [path for _, _, _, _, path in demands]
        moved_out = 0
        out_num, out_den = init_num, init_den

    return {"status": status,
            "peak": [_format_peak(init_num, init_den),
                     _format_peak(out_num, out_den)],
            "moved": moved_out,
            "flows": [[demands[i][0], demands[i][4], new_paths[i]]
                      for i in range(count)],
            "links": [[link["from"], link["to"], capacity[i],
                       final_used[i]]
                      for i, link in enumerate(links)]}


def compute_retune(nodes, links, current, changes, limit):
    # Joint path reallocation for a changed flow set, generalizing
    # compute_rebalance. `current` holds the committed C flows as
    # (id, s, d, b, path); `changes` holds validated (0, id) deletions
    # and (1, id, s, d, b) additions -- every deletion hits C, every
    # addition id is new to C, and G ids are unique. The target set keeps
    # C's surviving flows in C order, then appends the additions in G
    # order. Every target flow receives one up simple path; an assignment
    # is feasible when no link carries more than its bandwidth and at
    # most `limit` surviving flows leave their original path (additions
    # have no original path and never count as moved). Feasible
    # assignments rank by peak used/bandwidth (fractions compared with
    # integer cross-multiplication), moved count, then the target-order
    # vector of paths in Unicode code point order -- exactly the
    # comparisons in compute_rebalance. Unlike rebalance there is no
    # strict-improvement gate: the flow set changed, so the best feasible
    # assignment commits; only an empty feasible set rejects and reports
    # C unchanged. The Cartesian product enumerates with an explicit
    # stack -- O((V!)^K (KV+E)) time, O(KV+E) space.
    adj = {n: [] for n in nodes}
    index_of = {}
    for index, link in enumerate(links):
        index_of[(link["from"], link["to"])] = index
        if link["up"]:
            adj[link["from"]].append((link["to"], index))
    capacity = [link["bandwidth"] for link in links]

    initial_used = [0] * len(links)
    for _, _, _, b, path in current:
        for a, c in zip(path, path[1:]):
            initial_used[index_of[(a, c)]] += b
    for index, used_here in enumerate(initial_used):
        if used_here > capacity[index]:
            # As in rebalance, the committed placement must fit.
            fail(5)

    def peak_of(used):
        # max(used[i]/capacity[i]) as an exact fraction.
        num, den = 0, 1
        for u, c in zip(used, capacity):
            if u * den > num * c:
                num, den = u, c
        return num, den

    init_num, init_den = peak_of(initial_used)

    deleted = set()
    additions = []
    for change in changes:
        if change[0] == 0:
            deleted.add(change[1])
        else:
            additions.append((change[1], change[2], change[3], change[4]))
    # Surviving C flows first in C order, then additions in G order.
    demands = [flow for flow in current if flow[0] not in deleted]
    demands.extend((rid, s, d, b, None) for rid, s, d, b in additions)
    count = len(demands)

    def enum_paths(source, destination):
        # Yield (path, edge_indices) for every up simple path from
        # source to destination via iterative DFS, so the enumeration
        # depth is bounded by heap, not by the Python recursion limit.
        path = [source]
        edges = []
        visited = {source}
        iters = [iter(adj[source])]
        while iters:
            try:
                to, index = next(iters[-1])
            except StopIteration:
                iters.pop()
                if iters:
                    visited.remove(path.pop())
                    edges.pop()
                continue
            if to in visited:
                continue
            visited.add(to)
            path.append(to)
            edges.append(index)
            if to == destination:
                yield list(path), list(edges)
                visited.remove(path.pop())
                edges.pop()
            else:
                iters.append(iter(adj[to]))

    best_num = best_den = best_moved = None
    best_paths = best_used = None
    used = [0] * len(links)
    current_paths = [None] * count
    current_edges = [None] * count
    generators = [None] * count
    moved = 0
    depth = 0
    if count:
        generators[0] = enum_paths(demands[0][1], demands[0][2])
    while depth >= 0:
        if count == 0:
            # The empty assignment over zero target flows is feasible.
            best_num, best_den = peak_of(used)
            best_moved = 0
            best_paths = []
            best_used = list(used)
            break
        item = next(generators[depth], None)
        if item is None:
            # The level's paths are exhausted: backtrack and undo the
            # shallower level's assignment.
            generators[depth] = None
            depth -= 1
            if depth >= 0:
                b = demands[depth][3]
                for index in current_edges[depth]:
                    used[index] -= b
                original = demands[depth][4]
                if original is not None and current_paths[depth] != original:
                    moved -= 1
                current_paths[depth] = None
                current_edges[depth] = None
            continue
        path, edges = item
        b = demands[depth][3]
        if any(used[index] + b > capacity[index] for index in edges):
            continue
        original = demands[depth][4]
        # Only surviving flows with a committed path count as rerouted;
        # added flows keep the move tally unchanged on every path.
        delta = 1 if original is not None and path != original else 0
        if moved + delta > limit:
            continue
        for index in edges:
            used[index] += b
        current_paths[depth] = path
        current_edges[depth] = edges
        moved += delta
        if depth + 1 < count:
            depth += 1
            generators[depth] = enum_paths(demands[depth][1],
                                           demands[depth][2])
        else:
            num, den = peak_of(used)
            if (best_paths is None
                    or num * best_den < best_num * den
                    or (num * best_den == best_num * den
                        and (moved < best_moved
                             or (moved == best_moved
                                 and current_paths < best_paths)))):
                best_num, best_den = num, den
                best_moved = moved
                best_paths = list(current_paths)
                best_used = list(used)
            for index in edges:
                used[index] -= b
            moved -= delta
            current_paths[depth] = None
            current_edges[depth] = None

    if best_paths is not None:
        status = 1
        final_used = best_used
        moved_out = best_moved
        out_num, out_den = best_num, best_den
        final_flows = [[demands[i][0], demands[i][1], demands[i][2],
                        demands[i][3], best_paths[i]]
                       for i in range(count)]
    else:
        # No feasible assignment: reject and keep C exactly as given.
        status = 0
        final_used = initial_used
        moved_out = 0
        out_num, out_den = init_num, init_den
        final_flows = [[rid, s, d, b, path]
                       for rid, s, d, b, path in current]

    return {"status": status,
            "peak": [_format_peak(init_num, init_den),
                     _format_peak(out_num, out_den)],
            "moved": moved_out,
            "flows": final_flows,
            "links": [[link["from"], link["to"], capacity[i],
                       final_used[i]]
                      for i, link in enumerate(links)]}


def compute_loadshift(nodes, links, flows, limit, events):
    # Explicit-clock replay of bandwidth-change events over a fixed flow
    # set. `flows` holds validated (id, s, d, b, path) tuples in FLOWS
    # order, each path an up simple path that initially fits. Each event
    # is (t, u, v, nb): it advances the clock to t (events are already
    # non-decreasing) and temporarily sets edge (u, v)'s bandwidth to nb.
    # nb equal to the current bandwidth is idempotent (status 1) and
    # changes nothing; otherwise the joint search of compute_rebalance
    # assigns every flow one up simple path so that no link carries more
    # than its (possibly temporarily changed) bandwidth and at most
    # `limit` flows leave their current path. Feasible assignments rank
    # by peak used/bandwidth (integer cross-multiplication), moved count,
    # then the FLOWS-order path vector in Unicode code point order -- the
    # exact comparisons in compute_rebalance. A feasible assignment
    # commits atomically (status 0) with the temporary bandwidth kept; no
    # feasible assignment rejects (status 2), restoring the prior paths,
    # used counts, and bandwidth. The per-event enumeration is
    # O((V!)^K (KV+E)); across Q events and with output size P the whole
    # replay is O(Q (V!)^K (KV+E) + P) time, O(KV+E+Q+P) space.
    index_of = {(link["from"], link["to"]): i
                for i, link in enumerate(links)}
    capacity = [link["bandwidth"] for link in links]

    used = [0] * len(links)
    paths = []
    for _, _, _, b, path in flows:
        paths.append(list(path))
        for a, c in zip(path, path[1:]):
            used[index_of[(a, c)]] += b
    for index, used_here in enumerate(used):
        if used_here > capacity[index]:
            # As in rebalance, the committed placement must already fit.
            fail(5)

    # Link up/down state never changes during the replay (only
    # bandwidths do), so the up adjacency is built once.
    adj = {n: [] for n in nodes}
    for index, link in enumerate(links):
        if link["up"]:
            adj[link["from"]].append((link["to"], index))

    def peak_of(counts):
        # max(counts[i]/capacity[i]) as an exact fraction.
        num, den = 0, 1
        for u, c in zip(counts, capacity):
            if u * den > num * c:
                num, den = u, c
        return num, den

    def enum_paths(source, destination):
        # Every up simple path from source to destination via iterative
        # DFS, so enumeration depth is bounded by heap, not the Python
        # recursion limit.
        path = [source]
        edges = []
        visited = {source}
        stack = [iter(adj[source])]
        while stack:
            try:
                to, eindex = next(stack[-1])
            except StopIteration:
                stack.pop()
                if stack:
                    visited.remove(path.pop())
                    edges.pop()
                continue
            if to in visited:
                continue
            visited.add(to)
            path.append(to)
            edges.append(eindex)
            if to == destination:
                yield list(path), list(edges)
                visited.remove(path.pop())
                edges.pop()
            else:
                stack.append(iter(adj[to]))

    def search(count):
        # Cartesian-product search over the per-flow up simple path sets
        # with an explicit stack, as in compute_rebalance, against the
        # current `capacity`. Returns (num, den, moved, new_paths,
        # new_used) for the best feasible assignment, or None when no
        # assignment satisfies capacity and the reroute limit.
        best_num = best_den = best_moved = None
        best_paths = best_used = None
        trial = [0] * len(links)
        cur_paths = [None] * count
        cur_edges = [None] * count
        gens = [None] * count
        moved = 0
        depth = 0
        if count:
            gens[0] = enum_paths(flows[0][1], flows[0][2])
        while depth >= 0:
            if count == 0:
                # The empty assignment over zero flows is feasible.
                return (0, 1, 0, [], list(trial))
            item = next(gens[depth], None)
            if item is None:
                # Level exhausted: backtrack and undo the assignment
                # made by the shallower level.
                gens[depth] = None
                depth -= 1
                if depth >= 0:
                    b = flows[depth][3]
                    for eindex in cur_edges[depth]:
                        trial[eindex] -= b
                    if cur_paths[depth] != paths[depth]:
                        moved -= 1
                    cur_paths[depth] = None
                    cur_edges[depth] = None
                continue
            path, edges = item
            b = flows[depth][3]
            if any(trial[eindex] + b > capacity[eindex]
                   for eindex in edges):
                continue
            delta = 1 if path != paths[depth] else 0
            if moved + delta > limit:
                continue
            for eindex in edges:
                trial[eindex] += b
            cur_paths[depth] = path
            cur_edges[depth] = edges
            moved += delta
            if depth + 1 < count:
                depth += 1
                gens[depth] = enum_paths(flows[depth][1],
                                         flows[depth][2])
            else:
                num, den = peak_of(trial)
                if (best_paths is None
                        or num * best_den < best_num * den
                        or (num * best_den == best_num * den
                            and (moved < best_moved
                                 or (moved == best_moved
                                     and cur_paths < best_paths)))):
                    best_num, best_den = num, den
                    best_moved = moved
                    best_paths = list(cur_paths)
                    best_used = list(trial)
                for eindex in edges:
                    trial[eindex] -= b
                moved -= delta
                cur_paths[depth] = None
                cur_edges[depth] = None
        if best_paths is None:
            return None
        return best_num, best_den, best_moved, best_paths, best_used

    results = []
    count = len(flows)
    for t, u, v, nb in events:
        eindex = index_of[(u, v)]
        if nb == capacity[eindex]:
            # Idempotent: the bandwidth already equals the request.
            num, den = peak_of(used)
            results.append([t, 1, _format_peak(num, den), 0,
                            [list(path) for path in paths]])
            continue
        old_bw = capacity[eindex]
        capacity[eindex] = nb
        found = search(count)
        if found is None:
            # Reject: restore the prior state exactly.
            capacity[eindex] = old_bw
            num, den = peak_of(used)
            results.append([t, 2, _format_peak(num, den), 0,
                            [list(path) for path in paths]])
        else:
            # Atomic commit of paths, loads, and the temporary bandwidth.
            num, den, moved_count, new_paths, new_used = found
            paths = new_paths
            used = new_used
            results.append([t, 0, _format_peak(num, den), moved_count,
                            [list(path) for path in paths]])

    return {"events": results,
            "links": [[link["from"], link["to"], capacity[i], used[i]]
                      for i, link in enumerate(links)]}


def compute_flowshift(nodes, links, flows, limit, events):
    # Explicit-clock replay of mixed bandwidth/flow-set/topology events.
    # State is a live flow list in FLOWS order with additions appended at
    # the tail; each flow is [id, s, d, b, path], and marked[i] parallels
    # live[i] and is True only for the initial FLOWS instances. Validated
    # events are (kind, t, ...): (0, t, u, v, b) bandwidth change,
    # (1, t, id, s, d, b) addition, (2, t, id) deletion, (3, t, id, b)
    # demand change, (4, t, n, up) node state change, (5, t, u, v, up)
    # link state change. A bandwidth/demand/state value equal to the
    # current value, a deletion of an absent id, and a re-addition whose
    # id already has the same s/d/b are idempotent (status 1); a
    # conflicting addition or a demand change of an absent id fails.
    # Every real change jointly assigns the resulting flow set one path
    # each that uses only edges which are themselves up and whose two
    # endpoint nodes are up, with compute_loadshift's capacity and
    # ranking rules. LIMIT counts only the initial FLOWS *instances*
    # leaving their current path: an added instance never counts on the
    # event that adds it or any later one, and an initial instance that
    # is deleted and recreated under the same id stays exempt forever.
    # The ranking's moved tier (and the reported moved count) instead
    # counts every pre-existing instance that leaves its committed path;
    # an instance added by the event being processed has no committed
    # path and never counts as moved. A feasible assignment commits
    # atomically (status 0); no feasible assignment rejects (status 2)
    # and leaves node states, link states, bandwidths, the flow set,
    # paths, and loads exactly as they were. Per-event enumeration is
    # O((V!)^K (KV+E)); across Q events and output P the whole replay is
    # O(Q (V!)^K (KV+E) + P) time, O(KV+E+Q+P) space.
    index_of = {(link["from"], link["to"]): i
                for i, link in enumerate(links)}
    capacity = [link["bandwidth"] for link in links]
    # Links start in their FILE up state; nodes start up.
    link_up = [link["up"] for link in links]
    node_up = {n: True for n in nodes}

    used = [0] * len(links)
    live = []
    # Only the initial FLOWS instances count against LIMIT when they
    # leave their current path; the flag rides along with the instance,
    # so a deleted id recreated by an addition event is a fresh exempt
    # instance even though its id is an original one.
    marked = []
    for rid, s, d, b, path in flows:
        live.append([rid, s, d, b, list(path)])
        marked.append(True)
        for a, c in zip(path, path[1:]):
            used[index_of[(a, c)]] += b
    for index, used_here in enumerate(used):
        if used_here > capacity[index]:
            # As in loadshift, the committed placement must already fit.
            fail(5)

    def build_adj():
        # An edge is usable only while it is itself up and both of its
        # endpoint nodes are up. Rebuilt on every real topology change.
        current = {n: [] for n in nodes}
        for index, link in enumerate(links):
            if (link_up[index] and node_up[link["from"]]
                    and node_up[link["to"]]):
                current[link["from"]].append((link["to"], index))
        return current

    adj = build_adj()

    def peak_of(counts):
        # max(counts[i]/capacity[i]) as an exact fraction.
        num, den = 0, 1
        for u, c in zip(counts, capacity):
            if u * den > num * c:
                num, den = u, c
        return num, den

    def enum_paths(source, destination):
        # Every usable simple path from source to destination via
        # iterative DFS, so enumeration depth is bounded by heap, not the
        # Python recursion limit.
        path = [source]
        edges = []
        visited = {source}
        stack = [iter(adj[source])]
        while stack:
            try:
                to, eindex = next(stack[-1])
            except StopIteration:
                stack.pop()
                if stack:
                    visited.remove(path.pop())
                    edges.pop()
                continue
            if to in visited:
                continue
            visited.add(to)
            path.append(to)
            edges.append(eindex)
            if to == destination:
                yield list(path), list(edges)
                visited.remove(path.pop())
                edges.pop()
            else:
                stack.append(iter(adj[to]))

    def search(specs, count_flags, base_paths):
        # Cartesian-product search over the candidate flow set with an
        # explicit stack, exactly as in compute_loadshift. specs holds
        # (s, d, b) per candidate; base_paths[i] is the instance's
        # committed path, or None for a newly added candidate. Two tallies
        # run in parallel: `limited` counts only marked (initial FLOWS)
        # instances leaving their committed path and is capped by LIMIT,
        # while `moved` counts every candidate with a committed path that
        # leaves it and is the ranking tier and reported value; newly
        # added candidates (base None) never count in either. Returns
        # (num, den, moved, new_paths, new_used) for the best feasible
        # assignment, or None when no assignment satisfies capacity and
        # the reroute limit.
        count = len(specs)
        best_num = best_den = best_moved = None
        best_paths = best_used = None
        trial = [0] * len(links)
        cur_paths = [None] * count
        cur_edges = [None] * count
        gens = [None] * count
        limited = 0
        moved = 0
        depth = 0
        if count:
            gens[0] = enum_paths(specs[0][0], specs[0][1])
        while depth >= 0:
            if count == 0:
                # The empty assignment over zero flows is feasible.
                return (0, 1, 0, [], list(trial))
            item = next(gens[depth], None)
            if item is None:
                # Level exhausted: backtrack and undo the assignment
                # made by the shallower level.
                gens[depth] = None
                depth -= 1
                if depth >= 0:
                    b = specs[depth][2]
                    for eindex in cur_edges[depth]:
                        trial[eindex] -= b
                    base = base_paths[depth]
                    if base is not None and cur_paths[depth] != base:
                        moved -= 1
                        if count_flags[depth]:
                            limited -= 1
                    cur_paths[depth] = None
                    cur_edges[depth] = None
                continue
            path, edges = item
            b = specs[depth][2]
            if any(trial[eindex] + b > capacity[eindex]
                   for eindex in edges):
                continue
            base = base_paths[depth]
            if base is not None and path != base:
                moved += 1
                delta_limit = 1 if count_flags[depth] else 0
            else:
                delta_limit = 0
            if limited + delta_limit > limit:
                if base is not None and path != base:
                    moved -= 1
                continue
            for eindex in edges:
                trial[eindex] += b
            cur_paths[depth] = path
            cur_edges[depth] = edges
            limited += delta_limit
            if depth + 1 < count:
                depth += 1
                gens[depth] = enum_paths(specs[depth][0],
                                         specs[depth][1])
            else:
                num, den = peak_of(trial)
                if (best_paths is None
                        or num * best_den < best_num * den
                        or (num * best_den == best_num * den
                            and (moved < best_moved
                                 or (moved == best_moved
                                     and cur_paths < best_paths)))):
                    best_num, best_den = num, den
                    best_moved = moved
                    best_paths = list(cur_paths)
                    best_used = list(trial)
                for eindex in edges:
                    trial[eindex] -= b
                limited -= delta_limit
                if base is not None and path != base:
                    moved -= 1
                cur_paths[depth] = None
                cur_edges[depth] = None
        if best_paths is None:
            return None
        return best_num, best_den, best_moved, best_paths, best_used

    def snapshot_flows():
        return [[rid, s, d, b, list(path)]
                for rid, s, d, b, path in live]

    def row(t, kind, status, num, den, moved_count):
        return [t, kind, status, _format_peak(num, den), moved_count,
                snapshot_flows()]

    def reject_row(t, kind):
        # A rejected event reports the peak of the restored committed
        # state, so callers must undo their tentative change first.
        num, den = peak_of(used)
        return row(t, kind, 2, num, den, 0)

    def reroute(t, kind, additions=None, report_zero=False):
        # Rebuild the usable adjacency for the trial topology and jointly
        # assign the current flow set, plus optional event-born instances
        # appended at the tail (additions is a list of (id, s, d, b),
        # each carrying base path None and a False mark). On success
        # commit live/marked/used and return the row; on failure change
        # nothing and return None, leaving the caller's tentative change
        # in place for rollback. The reject row is built only after the
        # caller restores state, so its peak matches the committed
        # topology exactly. report_zero keeps the ranking's moved tally
        # (which still orders feasible assignments) but emits moved=0 on
        # the committed row, as a kind 4/5 event requires.
        nonlocal adj, used
        adj = build_adj()
        specs = [(f[1], f[2], f[3]) for f in live]
        bases = [f[4] for f in live]
        flags = list(marked)
        if additions:
            for _, s, d, b in additions:
                specs.append((s, d, b))
                bases.append(None)
                flags.append(False)
        found = search(specs, flags, bases)
        if found is None:
            return None
        num, den, moved_count, new_paths, new_used = found
        used = new_used
        old_count = len(live)
        for i in range(old_count):
            live[i][4] = new_paths[i]
        if additions:
            for j, (nid, s, d, b) in enumerate(additions):
                live.append([nid, s, d, b, new_paths[old_count + j]])
            marked.extend(False for _ in additions)
        reported_moved = 0 if report_zero else moved_count
        return row(t, kind, 0, num, den, reported_moved)

    results = []
    for event in events:
        kind = event[0]
        t = event[1]
        position = {flow[0]: i for i, flow in enumerate(live)}
        if kind == 0:
            _, _, u, v, nb = event
            eindex = index_of[(u, v)]
            if nb == capacity[eindex]:
                # Idempotent: the bandwidth already equals the request.
                num, den = peak_of(used)
                results.append(row(t, kind, 1, num, den, 0))
                continue
            old_bw = capacity[eindex]
            capacity[eindex] = nb
            outcome = reroute(t, kind)
            if outcome is None:
                # Reject: restore the prior bandwidth; paths and loads
                # were never mutated by the trial search.
                capacity[eindex] = old_bw
                results.append(reject_row(t, kind))
            else:
                # Atomic commit keeping the temporary bandwidth.
                results.append(outcome)
        elif kind == 1:
            _, _, nid, s, d, nb = event
            if nid in position:
                flow = live[position[nid]]
                if (flow[1], flow[2], flow[3]) != (s, d, nb):
                    # The same id may not be re-added with different
                    # s/d/b while it still exists.
                    fail(5)
                # Idempotent re-addition with identical content; the
                # existing instance keeps its mark and path.
                num, den = peak_of(used)
                results.append(row(t, kind, 1, num, den, 0))
                continue
            # The addition is candidate-only until the search commits; a
            # recreated id is a fresh unmarked instance either way.
            outcome = reroute(t, kind, additions=[(nid, s, d, nb)])
            if outcome is None:
                # Reject: the candidate flow was never appended.
                num, den = peak_of(used)
                results.append(row(t, kind, 2, num, den, 0))
            else:
                results.append(outcome)
        elif kind == 2:
            _, _, nid = event
            if nid not in position:
                # Deleting an absent id is idempotent.
                num, den = peak_of(used)
                results.append(row(t, kind, 1, num, den, 0))
                continue
            drop = position[nid]
            survivors = live[:drop] + live[drop + 1:]
            surviving_flags = marked[:drop] + marked[drop + 1:]
            adj = build_adj()
            specs = [(f[1], f[2], f[3]) for f in survivors]
            bases = [f[4] for f in survivors]
            found = search(specs, surviving_flags, bases)
            if found is None:
                # The survivors' committed paths stay feasible after a
                # deletion, so this is defensive: reject without
                # touching the live set.
                num, den = peak_of(used)
                results.append(row(t, kind, 2, num, den, 0))
            else:
                num, den, moved_count, new_paths, new_used = found
                used = new_used
                for i, path in enumerate(new_paths):
                    survivors[i][4] = path
                live = survivors
                marked = surviving_flags
                results.append(row(t, kind, 0, num, den, moved_count))
        elif kind == 3:
            _, _, nid, nb = event
            if nid not in position:
                # A demand change must name a flow that exists.
                fail(5)
            target = live[position[nid]]
            if nb == target[3]:
                # Idempotent: the demand already equals the request.
                num, den = peak_of(used)
                results.append(row(t, kind, 1, num, den, 0))
                continue
            old_b = target[3]
            target[3] = nb
            outcome = reroute(t, kind)
            if outcome is None:
                # Reject: restore the old demand; paths and loads were
                # never mutated by the trial search.
                target[3] = old_b
                results.append(reject_row(t, kind))
            else:
                results.append(outcome)
        elif kind == 4:
            _, _, n, bring_up = event
            if node_up[n] == bring_up:
                # Idempotent: the node already has that state.
                num, den = peak_of(used)
                results.append(row(t, kind, 1, num, den, 0))
                continue
            old_up = node_up[n]
            node_up[n] = bring_up
            outcome = reroute(t, kind, report_zero=True)
            if outcome is None:
                # Reject: the node state change is undone too and the
                # usable adjacency restored for the next event.
                node_up[n] = old_up
                adj = build_adj()
                results.append(reject_row(t, kind))
            else:
                results.append(outcome)
        else:
            _, _, u, v, bring_up = event
            eindex = index_of[(u, v)]
            if link_up[eindex] == bring_up:
                # Idempotent: the link already has that state.
                num, den = peak_of(used)
                results.append(row(t, kind, 1, num, den, 0))
                continue
            old_up = link_up[eindex]
            link_up[eindex] = bring_up
            outcome = reroute(t, kind, report_zero=True)
            if outcome is None:
                # Reject: the link state change is undone too and the
                # usable adjacency restored for the next event.
                link_up[eindex] = old_up
                adj = build_adj()
                results.append(reject_row(t, kind))
            else:
                results.append(outcome)

    return {"events": results,
            "links": [[link["from"], link["to"], capacity[i], used[i]]
                      for i, link in enumerate(links)]}


class _PShiftEngine:
    # Policy-aware variant of compute_flowshift. A live flow is
    # [id, s, d, b, p, c, path] with rules_of[i] holding the array index
    # (in the current rule set) of the rule that constrained its
    # committed path, or None; every initial FLOWS instance starts with
    # no binding (None), and an instance's given path need not satisfy
    # RULES. The rule set starts at RULES and only changes through kind 6
    # events. Validated events are (kind, t, ...): kinds 0..5 keep
    # compute_flowshift's shapes except kind 1 carries p/c too,
    # (1, t, id, s, d, b, p, c), and (6, t, R) atomically swaps the rule
    # set; a kind 1 re-addition is idempotent only when s/d/b/p/c all
    # match and a kind 6 swap is idempotent when R equals the current
    # set. After every real change each flow's candidate paths are
    # exactly the path of its first usable matching rule under
    # policytx matching (ascending n, ties in array order; a rule is
    # usable only when every path edge is itself up and both endpoint
    # nodes are up), or every usable simple path when no rule matches;
    # the joint search is otherwise compute_flowshift's, including the
    # marked-instance LIMIT tally, peak/moved/vector ranking, atomic
    # commit, and full rollback on rejection. rule bindings and paths
    # update only on commit; kind 4/5 commit rows report moved=0 while
    # the true moved tally still ranks assignments and counts against
    # LIMIT. Beyond compute_flowshift's bounds matching costs O(KR) per
    # event (K live flows, R rules) with O(R) additional space for the
    # priority order. The engine is resumable for pshiftcp: events may
    # be fed to run() in two slices and checkpoint_state() snapshots
    # the exact mid-run state.

    def __init__(self, nodes, links, flows, limit, rules):
        self.nodes = nodes
        self.links = links
        self.limit = limit
        self.index_of = {(link["from"], link["to"]): i
                         for i, link in enumerate(links)}
        self.capacity = [link["bandwidth"] for link in links]
        self.link_up = [link["up"] for link in links]
        self.node_up = {n: True for n in nodes}

        self.used = [0] * len(links)
        self.live = []
        self.marked = []
        self.rules_of = []
        for rid, s, d, b, p, c, path in flows:
            self.live.append([rid, s, d, b, p, c, list(path)])
            self.marked.append(True)
            # Initial instances carry no rule binding even when their
            # given path happens to equal a current rule's path.
            self.rules_of.append(None)
            for a, q in zip(path, path[1:]):
                self.used[self.index_of[(a, q)]] += b
        for index, used_here in enumerate(self.used):
            if used_here > self.capacity[index]:
                # As in flowshift, the committed placement must already
                # fit.
                fail(5)

        self.current_rules = [list(rule) for rule in rules]
        self.adj = self.build_adj()
        self.results = []

    def build_adj(self):
        current = {n: [] for n in self.nodes}
        for index, link in enumerate(self.links):
            if (self.link_up[index]
                    and self.node_up[link["from"]]
                    and self.node_up[link["to"]]):
                current[link["from"]].append((link["to"], index))
        return current

    def peak_of(self, counts):
        num, den = 0, 1
        for u, cap in zip(counts, self.capacity):
            if u * den > num * cap:
                num, den = u, cap
        return num, den

    def enum_paths(self, source, destination):
        path = [source]
        edges = []
        visited = {source}
        stack = [iter(self.adj[source])]
        while stack:
            try:
                to, eindex = next(stack[-1])
            except StopIteration:
                stack.pop()
                if stack:
                    visited.remove(path.pop())
                    edges.pop()
                continue
            if to in visited:
                continue
            visited.add(to)
            path.append(to)
            edges.append(eindex)
            if to == destination:
                yield list(path), list(edges)
                visited.remove(path.pop())
                edges.pop()
            else:
                stack.append(iter(self.adj[to]))

    def match_for(self, s, d, p, c, order):
        # First usable policytx match for one flow against the current
        # rule set, or None. Returns (rule index, path, edge indices).
        for i in order:
            _, rs, rd, ra, rb, rc, rpath = self.current_rules[i]
            if rs != s or rd != d:
                continue
            if not ra <= p <= rb:
                continue
            if rc is not None and rc != c:
                continue
            edge_ids = [self.index_of[(x, y)]
                        for x, y in zip(rpath, rpath[1:])]
            if all(self.link_up[e]
                   and self.node_up[self.links[e]["from"]]
                   and self.node_up[self.links[e]["to"]]
                   for e in edge_ids):
                return i, rpath, edge_ids
        return None

    def prepare(self, rows, flags, extra):
        # Build the search inputs for rows (live-style entries, their
        # paths are the committed bases) plus event-born extra tuples
        # (id, s, d, b, p, c) with base None. A spec's force entry is
        # None to enumerate every usable simple path, or the single
        # (path, edges) forced by the first usable matching rule.
        # rule_idx parallels the specs and records the binding the
        # assignment commits.
        order = _priority_order(self.current_rules)
        specs = []
        bases = []
        out_flags = []
        rule_idx = []

        def add(s, d, b, p, c, base, flag):
            match = self.match_for(s, d, p, c, order)
            if match is None:
                force = None
                binding = None
            else:
                force = (match[1], match[2])
                binding = match[0]
            specs.append((s, d, b, force))
            bases.append(base)
            out_flags.append(flag)
            rule_idx.append(binding)

        for i, entry in enumerate(rows):
            _, s, d, b, p, c, path = entry
            add(s, d, b, p, c, path, flags[i])
        for nid, s, d, b, p, c in extra:
            add(s, d, b, p, c, None, False)
        return specs, out_flags, bases, rule_idx

    def search(self, specs, count_flags, base_paths):
        # Same Cartesian-product search as compute_flowshift, except a
        # spec draws its one forced (path, edges) pair when a rule
        # matched instead of enumerating simple paths.
        capacity = self.capacity
        count = len(specs)
        best_num = best_den = best_moved = None
        best_paths = best_used = None
        trial = [0] * len(self.links)
        cur_paths = [None] * count
        cur_edges = [None] * count
        gens = [None] * count
        limited = 0
        moved = 0
        depth = 0
        if count:
            gens[0] = self.enum_paths(specs[0][0], specs[0][1]) \
                if specs[0][3] is None else iter((specs[0][3],))
        while depth >= 0:
            if count == 0:
                return (0, 1, 0, [], list(trial))
            item = next(gens[depth], None)
            if item is None:
                gens[depth] = None
                depth -= 1
                if depth >= 0:
                    b = specs[depth][2]
                    for eindex in cur_edges[depth]:
                        trial[eindex] -= b
                    base = base_paths[depth]
                    if base is not None and cur_paths[depth] != base:
                        moved -= 1
                        if count_flags[depth]:
                            limited -= 1
                    cur_paths[depth] = None
                    cur_edges[depth] = None
                continue
            path, edges = item
            b = specs[depth][2]
            if any(trial[eindex] + b > capacity[eindex]
                   for eindex in edges):
                continue
            base = base_paths[depth]
            if base is not None and path != base:
                moved += 1
                delta_limit = 1 if count_flags[depth] else 0
            else:
                delta_limit = 0
            if limited + delta_limit > self.limit:
                if base is not None and path != base:
                    moved -= 1
                continue
            for eindex in edges:
                trial[eindex] += b
            cur_paths[depth] = path
            cur_edges[depth] = edges
            limited += delta_limit
            if depth + 1 < count:
                depth += 1
                gens[depth] = self.enum_paths(specs[depth][0],
                                              specs[depth][1]) \
                    if specs[depth][3] is None \
                    else iter((specs[depth][3],))
            else:
                num, den = self.peak_of(trial)
                if (best_paths is None
                        or num * best_den < best_num * den
                        or (num * best_den == best_num * den
                            and (moved < best_moved
                                 or (moved == best_moved
                                     and cur_paths < best_paths)))):
                    best_num, best_den = num, den
                    best_moved = moved
                    best_paths = list(cur_paths)
                    best_used = list(trial)
                for eindex in edges:
                    trial[eindex] -= b
                limited -= delta_limit
                if base is not None and path != base:
                    moved -= 1
                cur_paths[depth] = None
                cur_edges[depth] = None
        if best_paths is None:
            return None
        return best_num, best_den, best_moved, best_paths, best_used

    def snapshot_flows(self):
        return [[rid, s, d, b, p, c, self.rules_of[i], list(path)]
                for i, (rid, s, d, b, p, c, path)
                in enumerate(self.live)]

    def row(self, t, kind, status, num, den, moved_count):
        return [t, kind, status, _format_peak(num, den), moved_count,
                self.snapshot_flows()]

    def reject_row(self, t, kind):
        num, den = self.peak_of(self.used)
        return self.row(t, kind, 2, num, den, 0)

    def idempotent_row(self, t, kind):
        num, den = self.peak_of(self.used)
        return self.row(t, kind, 1, num, den, 0)

    def reroute(self, t, kind, additions=None, report_zero=False):
        # Jointly assign the current flow set plus optional event-born
        # tuples appended at the tail. On success commit live/marked/
        # rules_of/used and return the row; on failure change nothing
        # and return None. report_zero emits moved=0 (kind 4/5) while
        # the ranking's moved tally is unaffected.
        self.adj = self.build_adj()
        specs, flags, bases, match_idx = self.prepare(
            self.live, self.marked, additions or [])
        found = self.search(specs, flags, bases)
        if found is None:
            return None
        num, den, moved_count, new_paths, new_used = found
        self.used = new_used
        old_count = len(self.live)
        for i in range(old_count):
            self.live[i][6] = new_paths[i]
            self.rules_of[i] = match_idx[i]
        if additions:
            for j, (nid, s, d, b, p, c) in enumerate(additions):
                self.live.append([nid, s, d, b, p, c,
                                  new_paths[old_count + j]])
                self.rules_of.append(match_idx[old_count + j])
            self.marked.extend(False for _ in additions)
        reported_moved = 0 if report_zero else moved_count
        return self.row(t, kind, 0, num, den, reported_moved)

    def process_event(self, event):
        kind = event[0]
        t = event[1]
        position = {flow[0]: i for i, flow in enumerate(self.live)}
        if kind == 0:
            _, _, u, v, nb = event
            eindex = self.index_of[(u, v)]
            if nb == self.capacity[eindex]:
                self.results.append(self.idempotent_row(t, kind))
                return
            old_bw = self.capacity[eindex]
            self.capacity[eindex] = nb
            outcome = self.reroute(t, kind)
            if outcome is None:
                self.capacity[eindex] = old_bw
                self.results.append(self.reject_row(t, kind))
            else:
                self.results.append(outcome)
        elif kind == 1:
            _, _, nid, s, d, nb, p, c = event
            if nid in position:
                flow = self.live[position[nid]]
                if (flow[1], flow[2], flow[3], flow[4], flow[5]) \
                        != (s, d, nb, p, c):
                    # Re-adding a live id is idempotent only when
                    # s/d/b/p/c are all identical.
                    fail(5)
                self.results.append(self.idempotent_row(t, kind))
                return
            outcome = self.reroute(
                t, kind, additions=[(nid, s, d, nb, p, c)])
            if outcome is None:
                self.results.append(self.reject_row(t, kind))
            else:
                self.results.append(outcome)
        elif kind == 2:
            _, _, nid = event
            if nid not in position:
                self.results.append(self.idempotent_row(t, kind))
                return
            drop = position[nid]
            survivors = self.live[:drop] + self.live[drop + 1:]
            surviving_flags = self.marked[:drop] + self.marked[drop + 1:]
            surviving_bindings = (self.rules_of[:drop]
                                  + self.rules_of[drop + 1:])
            self.adj = self.build_adj()
            specs, flags, bases, match_idx = self.prepare(
                survivors, surviving_flags, [])
            found = self.search(specs, flags, bases)
            if found is None:
                # Defensive, as in flowshift: the survivors' committed
                # paths stay feasible after a deletion.
                self.results.append(self.reject_row(t, kind))
            else:
                num, den, moved_count, new_paths, new_used = found
                self.used = new_used
                for i, path in enumerate(new_paths):
                    survivors[i][6] = path
                    surviving_bindings[i] = match_idx[i]
                self.live = survivors
                self.marked = surviving_flags
                self.rules_of = surviving_bindings
                self.results.append(
                    self.row(t, kind, 0, num, den, moved_count))
        elif kind == 3:
            _, _, nid, nb = event
            if nid not in position:
                fail(5)
            target = self.live[position[nid]]
            if nb == target[3]:
                self.results.append(self.idempotent_row(t, kind))
                return
            old_b = target[3]
            target[3] = nb
            outcome = self.reroute(t, kind)
            if outcome is None:
                target[3] = old_b
                self.results.append(self.reject_row(t, kind))
            else:
                self.results.append(outcome)
        elif kind == 4:
            _, _, n, bring_up = event
            if self.node_up[n] == bring_up:
                self.results.append(self.idempotent_row(t, kind))
                return
            old_up = self.node_up[n]
            self.node_up[n] = bring_up
            outcome = self.reroute(t, kind, report_zero=True)
            if outcome is None:
                self.node_up[n] = old_up
                self.adj = self.build_adj()
                self.results.append(self.reject_row(t, kind))
            else:
                self.results.append(outcome)
        elif kind == 5:
            _, _, u, v, bring_up = event
            eindex = self.index_of[(u, v)]
            if self.link_up[eindex] == bring_up:
                self.results.append(self.idempotent_row(t, kind))
                return
            old_up = self.link_up[eindex]
            self.link_up[eindex] = bring_up
            outcome = self.reroute(t, kind, report_zero=True)
            if outcome is None:
                self.link_up[eindex] = old_up
                self.adj = self.build_adj()
                self.results.append(self.reject_row(t, kind))
            else:
                self.results.append(outcome)
        else:
            _, _, new_rules = event
            if [list(rule) for rule in new_rules] == self.current_rules:
                # Loading the rule set already current is idempotent.
                self.results.append(self.idempotent_row(t, kind))
                return
            old_rules = self.current_rules
            self.current_rules = [list(rule) for rule in new_rules]
            outcome = self.reroute(t, kind)
            if outcome is None:
                # Reject: restore the old rule set; paths and loads
                # were never mutated by the trial search and the usable
                # adjacency does not depend on the rule set.
                self.current_rules = old_rules
                self.results.append(self.reject_row(t, kind))
            else:
                self.results.append(outcome)

    def run(self, events):
        for event in events:
            self.process_event(event)
        return self.result()

    def result(self):
        return {"events": self.results,
                "links": [[link["from"], link["to"],
                           self.capacity[i], self.used[i]]
                          for i, link in enumerate(self.links)]}


def compute_pshift(nodes, links, flows, limit, rules, events):
    return _PShiftEngine(nodes, links, flows, limit, rules).run(events)


def _pshiftcp_state(engine, cut, limit, raw_flows, raw_rules,
                    raw_events, file_bytes):
    # Build the pshiftcp checkpoint after the first cut events from an
    # engine run: keys i,r,f,n,l,e,h in this order. r is the current
    # rule set; f follows live flow order as
    # [id,s,d,b,p,c,initial-instance-bool,rule,path]; n follows FILE
    # node order as [node,up]; l follows FILE link order as
    # [from,to,up,bandwidth,used]; e is the prefix output event rows.
    # h is the SHA-256, lowercase hex, of FILE's raw bytes followed by
    # the compact non-ASCII UTF-8 JSON of
    # [LIMIT,FLOWS,RULES,EVENTS-prefix,i,r,f,n,l,e].
    r_arr = [list(rule) for rule in engine.current_rules]
    f_arr = [[rid, s, d, b, p, c, bool(engine.marked[idx]),
              engine.rules_of[idx], list(path)]
             for idx, (rid, s, d, b, p, c, path)
             in enumerate(engine.live)]
    n_arr = [[node, engine.node_up[node]] for node in engine.nodes]
    l_arr = [[link["from"], link["to"], engine.link_up[idx],
              engine.capacity[idx], engine.used[idx]]
             for idx, link in enumerate(engine.links)]
    e_arr = engine.results
    envelope = [limit, raw_flows, raw_rules, raw_events[:cut], cut,
                r_arr, f_arr, n_arr, l_arr, e_arr]
    payload = json.dumps(envelope, ensure_ascii=False,
                         separators=(",", ":"))
    digest = hashlib.sha256(
        file_bytes + payload.encode("utf-8")).hexdigest()
    return {"i": cut, "r": r_arr, "f": f_arr, "n": n_arr,
            "l": l_arr, "e": e_arr, "h": digest}


def _json_strict_equal(a, b):
    # Structural JSON equality without Python's bool/int coercion:
    # True never equals 1, a float never equals an int, dict key order
    # is irrelevant (arrays carry the required order), and every
    # nested value must match exactly. The recomputed checkpoint only
    # ever contains None/bool/int/str/list, so any other stored type
    # mismatches by construction.
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(_json_strict_equal(a[key], b[key]) for key in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(
            _json_strict_equal(x, y) for x, y in zip(a, b))
    return a == b


def _validate_pshiftcp_state(data, engine, cut, limit, raw_flows,
                             raw_rules, raw_events, file_bytes):
    # Verify a pshiftcp checkpoint against this invocation: key order
    # i,r,f,n,l,e,h first, then the h digest over FILE's raw bytes plus
    # the compact UTF-8 JSON of
    # [LIMIT,FLOWS,RULES,EVENTS-prefix,i,r,f,n,l,e], then every field
    # recomputed by replaying the prefix from scratch. cut must equal
    # the stored i; comparison is strict JSON equality (no bool/int or
    # int/float coercion). Any mismatch is code 5.
    keys = ["i", "r", "f", "n", "l", "e", "h"]
    if not isinstance(data, dict) or list(data.keys()) != keys:
        fail(5)
    stored_i = data["i"]
    r_arr = data["r"]
    f_arr = data["f"]
    n_arr = data["n"]
    l_arr = data["l"]
    e_arr = data["e"]
    digest = data["h"]
    if type(stored_i) is not int or type(stored_i) is bool \
            or stored_i != cut:
        fail(5)
    if type(digest) is not str:
        fail(5)
    envelope = [limit, raw_flows, raw_rules, raw_events[:cut], cut,
                r_arr, f_arr, n_arr, l_arr, e_arr]
    payload = json.dumps(envelope, ensure_ascii=False,
                         separators=(",", ":"))
    expected = hashlib.sha256(
        file_bytes + payload.encode("utf-8")).hexdigest()
    if digest != expected:
        fail(5)
    recomputed = _pshiftcp_state(engine, cut, limit, raw_flows,
                                 raw_rules, raw_events, file_bytes)
    if not all(_json_strict_equal(data[key], recomputed[key])
               for key in ("r", "f", "n", "l", "e")):
        fail(5)


def compute_quality(a, b, items):
    # Per-flow delivery quality over the items with a <= t <= b, kept in
    # input order (t is non-decreasing and equal t keeps input order).
    # items hold validated (id, f, t, d, path) tuples with d None for a
    # lost packet. _format_peak is exactly F: q = (2x*10^6 + y)//(2y)
    # rendered as q*10^-6 with six fixed decimals, all in integers.
    total = 0
    delays = []
    flow_paths = {}  # f -> paths of its delivered packets, in order
    for _, f, t, d, path in items:
        if not a <= t <= b:
            continue
        total += 1
        if d is None:
            # A flow seen only through losses is still listed, with c=0.
            flow_paths.setdefault(f, [])
            continue
        delays.append(d)
        flow_paths.setdefault(f, []).append(path)

    delivered = len(delays)
    lost = total - delivered
    stats = [total, delivered, lost,
             _format_peak(lost, total) if total else "0.000000"]

    n = delivered
    if n:
        delays.sort()
        # p95 is the ceil(0.95*n)-th smallest, as a 1-based index.
        delay = [n, delays[0], delays[-1],
                 _format_peak(sum(delays), n),
                 delays[(95 * n + 99) // 100 - 1]]
    else:
        delay = [0, None, None, None, None]

    changes = [[f, sum(1 for x, y in zip(paths, paths[1:]) if x != y)]
               for f, paths in sorted(flow_paths.items())]

    return {"start": a, "end": b, "stats": stats, "delay": delay,
            "changes": changes}


def compute_audit(links, a, b, items):
    # Replay audit over the items with a <= t <= b, kept in input order
    # (t is non-decreasing and equal t keeps input order). items hold
    # validated (id, f, t, s, d, path) tuples: s=0 is a delivery with
    # delay d, s=1 is a loss attributed to the path's last edge, s=2 is
    # a no-route loss carrying no delay and no path. Every edge of an
    # s=0/s=1 path counts one traversal on its link. Rates use exactly
    # _format_peak: q = (2x*10^6 + y)//(2y) rendered as q*10^-6 with six
    # fixed decimals, all in integers; a zero denominator is 0.000000.
    index_of = {(link["from"], link["to"]): index
                for index, link in enumerate(links)}
    traversals = [0] * len(links)
    attributed = [0] * len(links)
    total = 0
    delivered = 0
    lost = 0
    noroute = 0
    delays = []
    flow_paths = {}  # f -> paths of its delivered packets, in order
    for _, f, t, s, d, path in items:
        if not a <= t <= b:
            continue
        total += 1
        # A flow seen only through losses is still listed, with c=0.
        flow_paths.setdefault(f, [])
        if s == 0:
            delivered += 1
            delays.append(d)
            flow_paths[f].append(path)
            for x, y in zip(path, path[1:]):
                traversals[index_of[(x, y)]] += 1
        elif s == 1:
            lost += 1
            for x, y in zip(path, path[1:]):
                traversals[index_of[(x, y)]] += 1
            attributed[index_of[(path[-2], path[-1])]] += 1
        else:
            noroute += 1

    rate_den = delivered + lost
    summary = [total, delivered, lost, noroute,
               _format_peak(lost, rate_den) if rate_den else "0.000000"]

    n = delivered
    if n:
        delays.sort()
        # p95 is the ceil(0.95*n)-th smallest, as a 1-based index.
        delay = [n, _format_peak(sum(delays), n),
                 delays[(95 * n + 99) // 100 - 1]]
    else:
        delay = [0, None, None]

    link_rows = [[link["from"], link["to"], traversals[i], attributed[i],
                  _format_peak(attributed[i], traversals[i])
                  if traversals[i] else "0.000000"]
                 for i, link in enumerate(links)]

    reroutes = [[f, sum(1 for x, y in zip(paths, paths[1:]) if x != y)]
                for f, paths in sorted(flow_paths.items())]

    return {"start": a, "end": b, "summary": summary, "delay": delay,
            "links": link_rows, "reroutes": reroutes}


def compute_drill(links, a, b, events, items):
    # Failure-window drill. Nodes start up and every link takes FILE's up
    # flag; events are applied in order (t non-decreasing, equal t kept in
    # order) and atomically, with repeated setting idempotent. The first
    # real down opens one failure period; it closes at the tick on which
    # every object that was ever down is back up. Any real down after the
    # close is a second failure and exits 5. Records with a <= t <= b are
    # bucketed before/during/after relative to that one period: equal-tick
    # events are all applied before a record at the same tick, so the
    # start tick is "during" and the end tick is "after". With no failure
    # every record is "before"; an unrecovered period leaves "after" empty.
    node_up = {}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}
    down_nodes = set()       # nodes down right now
    down_links = set()       # links down right now
    ever_nodes = set()       # nodes down at least once during the period
    ever_links = set()       # links down at least once during the period
    failure_start = None
    failure_end = None

    for t, kind, *rest in events:
        if kind == 0:
            node, up = rest
            current = node_up.get(node, True)
            if current == up:
                continue
            node_up[node] = up
            if up:
                down_nodes.discard(node)
            else:
                if failure_end is not None:
                    fail(5)
                if failure_start is None:
                    failure_start = t
                down_nodes.add(node)
                ever_nodes.add(node)
        else:
            u, v, up = rest
            pair = (u, v)
            current = link_up[pair]
            if current == up:
                continue
            link_up[pair] = up
            if up:
                down_links.discard(pair)
            else:
                if failure_end is not None:
                    fail(5)
                if failure_start is None:
                    failure_start = t
                down_links.add(pair)
                ever_links.add(pair)
        # An event batch closes the period at its own tick once every
        # object ever down is back up; events share the tick in order.
        if (failure_start is not None and failure_end is None
                and not down_nodes and not down_links):
            failure_end = t

    buckets = [[], [], []]
    for item in items:
        t = item[2]
        if not a <= t <= b:
            continue
        if failure_start is None or t < failure_start:
            phase = 0
        elif failure_end is None or t < failure_end:
            phase = 1
        else:
            phase = 2
        buckets[phase].append(item)

    def phase_stats(records):
        # [N, D, X, F(D,N), F(X,N), p95]: D is the audit status-0 count
        # and X the status-1/2 count; both rates use _format_peak with N
        # as the denominator, and N == 0 gives 0.000000. p95 is the
        # ceil(0.95*D)-th smallest delivered delay (1-based), null at 0.
        delivered = 0
        other = 0
        delays = []
        for _, _, _, s, d, _ in records:
            if s == 0:
                delivered += 1
                delays.append(d)
            else:
                other += 1
        total = delivered + other
        if total:
            f_delivered = _format_peak(delivered, total)
            f_other = _format_peak(other, total)
        else:
            f_delivered = f_other = "0.000000"
        if delivered:
            delays.sort()
            p95 = delays[(95 * delivered + 99) // 100 - 1]
        else:
            p95 = None
        return [total, delivered, other, f_delivered, f_other, p95]

    p = [phase_stats(buckets[0]), phase_stats(buckets[1]),
         phase_stats(buckets[2])]

    # An affected edge started up in FILE and was itself down or has at
    # least one endpoint that was ever down, listed in FILE order.
    affected = []
    for link in links:
        pair = (link["from"], link["to"])
        if (link["up"]
                and (pair in ever_links
                     or link["from"] in ever_nodes
                     or link["to"] in ever_nodes)):
            affected.append([link["from"], link["to"]])

    if failure_start is None:
        f = None
        r = [None, None]
    elif failure_end is None:
        f = failure_start
        r = [None, None]
    else:
        f = failure_start
        r = [failure_end, failure_end - failure_start]

    return {"a": a, "b": b, "f": f, "r": r, "p": p, "l": affected}


def compute_multidrill(links, a, b, events, items):
    # Multi-period failure drill, generalising compute_drill. Nodes start
    # up and every link takes FILE's up flag; events apply in order (t
    # non-decreasing, equal t kept in order), repeated setting idempotent.
    # The first real down opens a period; the period closes on the tick at
    # which the nodes and links currently down are all back up (only down
    # objects still outstanding matter, so an object recovered early never
    # delays the close). A real down after a close opens another period; a
    # close and a reopen may share a tick, objects may recur across
    # periods, and the last period may stay open.
    node_up = {}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}
    periods = []
    current = None  # [start, end, down_nodes, down_links,
                    #  ever_nodes, ever_links] while open

    for t, kind, *rest in events:
        if kind == 0:
            node, up = rest
            current_before = node_up.get(node, True)
            if current_before == up:
                continue
            node_up[node] = up
            if up:
                if current is not None:
                    current[2].discard(node)
            else:
                if current is None:
                    current = [t, None, set(), set(), set(), set()]
                    periods.append(current)
                current[2].add(node)
                current[4].add(node)
        else:
            u, v, up = rest
            pair = (u, v)
            current_before = link_up[pair]
            if current_before == up:
                continue
            link_up[pair] = up
            if up:
                if current is not None:
                    current[3].discard(pair)
            else:
                if current is None:
                    current = [t, None, set(), set(), set(), set()]
                    periods.append(current)
                current[3].add(pair)
                current[5].add(pair)
        # The period closes on the tick its current down set empties; a
        # later event at the same tick may reopen a fresh period.
        if current is not None and not current[2] and not current[3]:
            current[1] = t
            current = None

    if not periods:
        return {"a": a, "b": b, "periods": []}

    def phase_stats(records):
        # [N, D, X, F(D,N), F(X,N), p95], exactly drill's per-phase stats:
        # D is the audit status-0 count and X the status-1/2 count; both
        # rates use _format_peak with N as the denominator, and N == 0
        # gives 0.000000. p95 is the ceil(0.95*D)-th smallest delivered
        # delay (1-based), null at 0.
        delivered = 0
        other = 0
        delays = []
        for _, _, _, s, d, _ in records:
            if s == 0:
                delivered += 1
                delays.append(d)
            else:
                other += 1
        total = delivered + other
        if total:
            f_delivered = _format_peak(delivered, total)
            f_other = _format_peak(other, total)
        else:
            f_delivered = f_other = "0.000000"
        if delivered:
            delays.sort()
            p95 = delays[(95 * delivered + 99) // 100 - 1]
        else:
            p95 = None
        return [total, delivered, other, f_delivered, f_other, p95]

    out_periods = []
    for start, end, _down_nodes, _down_links, ever_nodes, ever_links \
            in periods:
        # Records bucket t < start (before), start <= t < end (during),
        # t >= end (after); equal-tick events precede a record at that
        # tick, so the start tick is "during" and the end tick is "after".
        # An open period has an empty after phase.
        buckets = [[], [], []]
        for item in items:
            t = item[2]
            if not a <= t <= b:
                continue
            if t < start:
                phase = 0
            elif end is None or t < end:
                phase = 1
            else:
                phase = 2
            buckets[phase].append(item)
        stats = [phase_stats(buckets[0]), phase_stats(buckets[1]),
                 phase_stats(buckets[2])]

        # An affected edge started up in FILE and, during this period, was
        # itself down or had at least one endpoint ever down, in FILE
        # order.
        affected = []
        for link in links:
            if (link["up"]
                    and ((link["from"], link["to"]) in ever_links
                         or link["from"] in ever_nodes
                         or link["to"] in ever_nodes)):
                affected.append([link["from"], link["to"]])

        out_periods.append([start,
                            None if end is None else end,
                            None if end is None else end - start,
                            stats, affected])

    return {"a": a, "b": b, "periods": out_periods}


def compute_convstat(links, node_set, pair_set, a, b, events, data):
    # Convergence correlation over multidrill failure periods. Periods
    # open and close exactly as in compute_multidrill: nodes start up,
    # links take FILE's up flag, events apply in order (t non-decreasing,
    # equal t kept in order) with repeated setting idempotent, a period
    # closes on the tick its current down set empties, and a close and a
    # reopen may share a tick. Each record (t, f, path) reports flow f's
    # path at tick t, [] meaning unreachable. A record inside a period's
    # [start, end) window ([start, b] while the period is still open)
    # affects its flow when the path is empty or differs from the flow's
    # previous record, except that a flow's first non-empty path never
    # affects. For a closed period, r is the earliest moment in
    # [end, U) — U the next period's start, b + 1 for the last one — at
    # which every affected flow's latest path is non-empty, r = end when
    # that already holds at end; r and d stay null with no affected
    # flows, an open period, or no timely recovery, else d = r - start.
    # c counts adjacent path changes of the affected flows within
    # [start, r], or within [start, U) when r is null.
    node_up = {}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}
    periods = []  # [start, end_or_None] in opening order
    down_nodes = set()
    down_links = set()
    for t, kind, *rest in events:
        if kind == 0:
            node, up = rest
            if node_up.get(node, True) == up:
                continue
            node_up[node] = up
            if up:
                down_nodes.discard(node)
            else:
                if not periods or periods[-1][1] is not None:
                    periods.append([t, None])
                down_nodes.add(node)
        else:
            u, v, up = rest
            pair = (u, v)
            if link_up[pair] == up:
                continue
            link_up[pair] = up
            if up:
                down_links.discard(pair)
            else:
                if not periods or periods[-1][1] is not None:
                    periods.append([t, None])
                down_links.add(pair)
        # The period closes on the tick its current down set empties; a
        # later event at the same tick may reopen a fresh period.
        if (periods and periods[-1][1] is None
                and not down_nodes and not down_links):
            periods[-1][1] = t

    # Record validation: t is a bounded integer inside [a, b] and
    # non-decreasing, f a 1..64 code point UTF-8 string with at most one
    # record per (t, f), and a non-empty path must be a known simple path
    # whose nodes and links are all up once every event has been applied.
    records = []
    seen_marks = set()
    previous_time = None
    for item in data:
        if not isinstance(item, list) or len(item) != 3:
            fail(5)
        t, f, path = item
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if not a <= t <= b:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(f) is not str or not 1 <= len(f) <= 64:
            fail(5)
        try:
            f.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if (t, f) in seen_marks:
            fail(5)
        seen_marks.add((t, f))
        if not isinstance(path, list):
            fail(5)
        if path:
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
                if not node_up.get(node, True):
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for x, y in zip(path, path[1:]):
                if (x, y) not in pair_set:
                    fail(5)
                if not link_up[(x, y)]:
                    fail(5)
        records.append((t, f, path))

    # Per-flow history in input (non-decreasing t) order; same-flow
    # same-tick uniqueness makes each flow's ticks strictly increasing.
    flow_times = {}
    flow_paths = {}
    first_nonempty = {}
    for g, (t, f, path) in enumerate(records):
        if f not in flow_times:
            flow_times[f] = []
            flow_paths[f] = []
        flow_times[f].append(t)
        flow_paths[f].append(path)
        if path and f not in first_nonempty:
            first_nonempty[f] = g

    # Single pass over the records marking affected flows. Affecting
    # windows of distinct periods are disjoint, so a period pointer
    # suffices; last_index keeps each flow's previous record globally,
    # including records before the window.
    n_periods = len(periods)
    affected = [set() for _ in periods]
    window_end = [p[1] if p[1] is not None else b + 1 for p in periods]
    last_index = {}
    pidx = 0
    for g, (t, f, path) in enumerate(records):
        while pidx < n_periods and t >= window_end[pidx]:
            pidx += 1
        if pidx < n_periods and periods[pidx][0] <= t:
            prev = last_index.get(f)
            if not path:
                affected[pidx].add(f)
            elif (prev is not None and g != first_nonempty[f]
                    and path != records[prev][2]):
                affected[pidx].add(f)
        last_index[f] = g

    gt = [t for t, _, _ in records]
    out_periods = []
    for i, (start, end) in enumerate(periods):
        flows = affected[i]
        next_u = periods[i + 1][0] if i + 1 < n_periods else b + 1
        r = None
        if end is not None and flows:
            # Latest path per affected flow at the closing tick (records
            # at t == end included); r = end when already all non-empty.
            latest = {}
            empty = 0
            for f in flows:
                j = bisect_right(flow_times[f], end) - 1
                path = flow_paths[f][j] if j >= 0 else []
                latest[f] = path
                if not path:
                    empty += 1
            if empty == 0:
                r = end
            else:
                # Sweep recovery records in (end, U) tick by tick. Only
                # the count of empty-latest affected flows matters and a
                # record changes it by at most one, so the sweep is
                # linear in the records inside the window; recovery
                # windows of distinct periods are disjoint.
                g = bisect_right(gt, end)
                hi = bisect_left(gt, next_u)
                while g < hi and empty:
                    tick = gt[g]
                    while g < hi and gt[g] == tick:
                        _, f, path = records[g]
                        if f in latest:
                            if not latest[f] and path:
                                empty -= 1
                            elif latest[f] and not path:
                                empty += 1
                            latest[f] = path
                        g += 1
                    if empty == 0:
                        r = tick

        # Adjacent path changes of affected flows, both records inside
        # [start, r] when recovered and inside [start, U) otherwise.
        c = 0
        for f in flows:
            ft = flow_times[f]
            lo = bisect_left(ft, start)
            if r is not None:
                hi = bisect_right(ft, r)
            else:
                hi = bisect_left(ft, next_u)
            fp = flow_paths[f]
            for k in range(lo + 1, hi):
                if fp[k] != fp[k - 1]:
                    c += 1

        out_periods.append([start,
                            None if end is None else end,
                            None if r is None else r,
                            None if r is None else r - start,
                            c, sorted(flows)])

    return {"a": a, "b": b, "p": out_periods}


def compute_slosum(links, node_set, pair_set, a, b, width, events, data):
    # Windowed convergence-SLO summary. Periods open and close, records
    # validate, and each period's [start, end, r, d, c, flows] is computed
    # exactly as in compute_convstat (a recovery crossing a window edge
    # still uses every DATA record up to the next period's start or b+1).
    # The closed windows [x, min(b, x+width-1)] tile [a, b] from x = a in
    # steps of width, and each period joins the window its start falls in.
    # Per window: C counts periods with a non-null end, U those of them
    # with r null, O the still-open periods, F the total affected-flow
    # count, S the c sum, and ds summarizes the non-null d values with
    # p50/p95 the ceil(0.50*n)-th / ceil(0.95*n)-th smallest (1-based).
    periods = compute_convstat(links, node_set, pair_set, a, b, events,
                               data)["p"]
    count = (b - a) // width + 1
    buckets = [[] for _ in range(count)]
    for period in periods:
        buckets[(period[0] - a) // width].append(period)
    windows = []
    for i, bucket in enumerate(buckets):
        x = a + i * width
        y = b if x + width - 1 > b else x + width - 1
        closed = 0
        unrecovered = 0
        open_count = 0
        flows_total = 0
        c_total = 0
        delays = []
        for _start, end, r, d, c, flows in bucket:
            if end is None:
                open_count += 1
            else:
                closed += 1
                if r is None:
                    unrecovered += 1
            if d is not None:
                delays.append(d)
            flows_total += len(flows)
            c_total += c
        n = len(delays)
        if n:
            delays.sort()
            ds = [n, delays[0], delays[-1],
                  delays[(n + 1) // 2 - 1],
                  delays[(95 * n + 99) // 100 - 1]]
        else:
            ds = [0, None, None, None, None]
        windows.append([x, y, closed, unrecovered, open_count, ds,
                        flows_total, c_total])
    return {"a": a, "b": b, "width": width, "windows": windows}


def _sloeval_result(summary, policy):
    # Evaluate one policy [u, o, d, f, s, g] against compute_slosum
    # windows: u caps the unrecovered count U, o the still-open count O,
    # d the recovery p95 ds[4], f the affected-flow total F, s the change
    # total S, and g the number of violating windows the budget still
    # tolerates. A window is compliant when every reason list is empty;
    # thresholds are inclusive, so equality never violates. Reason codes,
    # in order: 0 for U > u, 1 for O > o, 2 for a window with periods
    # (C + O > 0) but no recovery delay sample (ds[0] = 0), 3 for
    # ds[0] > 0 with p95 > d, 4 for F > f, 5 for S > s. The excess vector
    # reports q(z) = max(z, 0) of each overshoot, with the p95 slot null
    # when ds[0] = 0. Returns (windows, runs, budget).
    u_lim, o_lim, d_lim, f_lim, s_lim, g = policy
    windows = []
    for x, y, closed, unrecovered, open_count, ds, flows_total, c_total \
            in summary["windows"]:
        reasons = []
        if unrecovered > u_lim:
            reasons.append(0)
        if open_count > o_lim:
            reasons.append(1)
        if closed + open_count > 0 and ds[0] == 0:
            reasons.append(2)
        if ds[0] > 0 and ds[4] > d_lim:
            reasons.append(3)
        if flows_total > f_lim:
            reasons.append(4)
        if c_total > s_lim:
            reasons.append(5)
        excess = [max(unrecovered - u_lim, 0),
                  max(open_count - o_lim, 0),
                  max(ds[4] - d_lim, 0) if ds[0] > 0 else None,
                  max(flows_total - f_lim, 0),
                  max(c_total - s_lim, 0)]
        windows.append([x, y, not reasons, reasons, excess])

    # Maximal runs of adjacent violating windows; the windows tile [a, b]
    # in order, so adjacency is consecutive index.
    runs = []
    violations = 0
    i = 0
    count = len(windows)
    while i < count:
        if windows[i][2]:
            i += 1
            continue
        j = i
        while j + 1 < count and not windows[j + 1][2]:
            j += 1
        runs.append([windows[i][0], windows[j][1], j - i + 1])
        violations += j - i + 1
        i = j + 1

    budget = [g, violations, max(g - violations, 0),
              max(violations - g, 0)]
    return windows, runs, budget


def compute_sloeval(links, node_set, pair_set, a, b, width, policy,
                    events, data):
    # Windowed convergence-SLO evaluation: windows come from
    # compute_slosum and each is checked against the policy exactly as in
    # _sloeval_result.
    summary = compute_slosum(links, node_set, pair_set, a, b, width,
                             events, data)
    windows, runs, budget = _sloeval_result(summary, policy)
    return {"a": a, "b": b, "width": width, "policy": policy,
            "windows": windows, "runs": runs, "budget": budget}


def compute_slocmp(links, node_set, pair_set, a, b, width, old, new,
                   events, data):
    # Side-by-side comparison of two SLO policies over one shared window
    # summary. OLD and NEW each follow sloeval's [u, o, d, f, s, g]
    # contract and are evaluated exactly as in _sloeval_result; every
    # window then reports both verdicts, a transition code t (0 when the
    # ok flags agree, 1 for a true-to-false regression, 2 for a
    # false-to-true improvement), the reason codes NEW adds and removes
    # (ascending), and the per-slot excess delta NEW minus OLD (null when
    # either side is null). runs pairs both maximal violation-run lists
    # with the NEW-minus-OLD differences in run count and violating
    # window count; budget pairs both four-integer budgets with the
    # elementwise difference.
    summary = compute_slosum(links, node_set, pair_set, a, b, width,
                             events, data)
    old_windows, old_runs, old_budget = _sloeval_result(summary, old)
    new_windows, new_runs, new_budget = _sloeval_result(summary, new)

    windows = []
    for old_w, new_w in zip(old_windows, new_windows):
        x, y, old_ok, old_reasons, old_excess = old_w
        _, _, new_ok, new_reasons, new_excess = new_w
        if old_ok == new_ok:
            t = 0
        elif old_ok:
            t = 1
        else:
            t = 2
        add = sorted(set(new_reasons) - set(old_reasons))
        remove = sorted(set(old_reasons) - set(new_reasons))
        delta = [None if o is None or n is None else n - o
                 for o, n in zip(old_excess, new_excess)]
        windows.append([x, y, [old_ok, old_reasons, old_excess],
                        [new_ok, new_reasons, new_excess], t,
                        [add, remove], delta])

    runs = [old_runs, new_runs,
            [len(new_runs) - len(old_runs),
             new_budget[1] - old_budget[1]]]
    budget = [old_budget, new_budget,
              [n - o for o, n in zip(old_budget, new_budget)]]
    return {"a": a, "b": b, "width": width, "old": old, "new": new,
            "windows": windows, "runs": runs, "budget": budget}


def compute_slogate(links, node_set, pair_set, a, b, width, cur, new,
                    events, data):
    # Deterministic atomic gate for an SLO policy change from CUR to NEW.
    # CUR and NEW each follow sloeval's [u, o, d, f, s, g] contract; the
    # windows and budget are byte-for-byte compute_slocmp's under the same
    # inputs, including the per-window add lists and NEW-minus-CUR excess
    # deltas. The change collects ascending, deduplicated rejection codes:
    # 0 when any window's add list is non-empty (NEW violates a window for
    # a reason CUR did not), 1 when any window has a non-null positive
    # excess delta, and 2 when the budget difference's fourth element (the
    # un-tolerated-violating-window overshoot) is positive. Only positive
    # differences reject: a window whose mixed metrics improve somewhere
    # and worsen nowhere passes, and null excess slots never take part in
    # the comparison. An empty code list allows the change, so FINAL is
    # NEW; otherwise FINAL stays CUR. PD is the six-element NEW-minus-CUR
    # policy difference. The gate reports its verdict and changes nothing
    # else; even a rejection exits 0.
    comparison = compute_slocmp(links, node_set, pair_set, a, b, width,
                                cur, new, events, data)
    windows = comparison["windows"]
    budget = comparison["budget"]

    why = set()
    for window in windows:
        # window = [x, y, [CUR...], [NEW...], t, [add, remove], delta].
        if window[5][0]:
            why.add(0)
        if any(d is not None and d > 0 for d in window[6]):
            why.add(1)
    if budget[2][3] > 0:
        why.add(2)
    reasons = sorted(why)

    policy_diff = [n - c for c, n in zip(cur, new)]
    final = new if not reasons else cur
    return {"ok": not reasons, "why": reasons,
            "policy": [cur, new, policy_diff, final],
            "windows": windows, "budget": budget}


def compute_replay(nodes, links, a, b, events):
    # Event-driven replay over a mutable up-graph. The clock jumps to each
    # event's t and processes it atomically; equal t keeps input order, so
    # a link item at the same tick before a packet already affects it.
    # Link items only flip their link's "up" flag in place (repeated
    # setting is idempotent); every packet item is routed on the current
    # up-graph over the lowest-cost path, ties going to the complete node
    # sequence smallest in Unicode code point order (exactly the
    # shortest_paths tie-break), and its delay is the latency sum along
    # that path. Only packets with a <= t <= b are collected, in event
    # order; stats/delay/changes reuse compute_quality on those packets.
    index_of = {}
    latency_of = {}
    for index, link in enumerate(links):
        pair = (link["from"], link["to"])
        index_of[pair] = index
        latency_of[pair] = link["latency"]

    packets = []
    items = []
    for event in events:
        if event[0] == 0:
            _, _, u, v, up = event
            links[index_of[(u, v)]]["up"] = up
            continue
        _, t, pid, f, s, d = event
        _, path_of = shortest_paths(nodes, links, s)
        path = path_of[d]
        if path is None:
            delay = None
            out_path = []
        else:
            delay = 0
            for x, y in zip(path, path[1:]):
                delay += latency_of[(x, y)]
            if delay > MAX_TIME:
                fail(5)
            out_path = path
        if a <= t <= b:
            packets.append([pid, f, t, delay, out_path])
            items.append((pid, f, t, delay, out_path))

    summary = compute_quality(a, b, items)
    return {"start": a, "end": b, "packets": packets,
            "stats": summary["stats"], "delay": summary["delay"],
            "changes": summary["changes"]}


def compute_nfail(nodes, links, source, destination, wait, items):
    # Node-failure protection switching with a debounced changeover delay.
    # Primary: lowest-cost path in the initial up-graph (every node starts
    # up, up links only), ties going to the node sequence smallest in
    # Unicode code point order (exactly the shortest_paths tie-break).
    # Backup: the same computation after deleting the primary's internal
    # nodes and its directed edges; no primary means no backup. Both are
    # computed once here and never recomputed; node items only flip node
    # up states (repeated setting is idempotent).
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_path = path_of[destination]
    primary = ((cost_of[destination], primary_path)
               if primary_path is not None else None)
    backup = None
    if primary_path is not None:
        internal = set(primary_path[1:-1])
        removed = set(zip(primary_path, primary_path[1:]))
        bnodes = [n for n in nodes if n not in internal]
        blinks = [link for link in up_links
                  if link["from"] not in internal
                  and link["to"] not in internal
                  and (link["from"], link["to"]) not in removed]
        bcost_of, bpath_of = shortest_paths(bnodes, blinks, source)
        if bpath_of[destination] is not None:
            backup = (bcost_of[destination], bpath_of[destination])

    up_of = {n: True for n in nodes}
    # Down-node counts on each candidate path, kept incrementally so a
    # node flip and the target selection are both O(1).
    primary_nodes = set(primary[1]) if primary is not None else set()
    backup_nodes = set(backup[1]) if backup is not None else set()
    primary_down = 0
    backup_down = 0

    def target():
        # The first all-up of the primary and the backup, else no path.
        if primary is not None and primary_down == 0:
            return primary
        if backup is not None and backup_down == 0:
            return backup
        return None

    active = primary
    timer_start = None
    timer_at = None
    timer_target = None
    switches = []
    packets = []
    i = 0
    n = len(items)
    while i < n or timer_at is not None:
        wakes = []
        if i < n:
            wakes.append(items[i][0])
        if timer_at is not None:
            wakes.append(timer_at)
        now = min(wakes)
        # All items at this tick run in input order before a timer
        # completing on it; a timer due before the next item's tick
        # completes first.
        while i < n and items[i][0] == now:
            item = items[i]
            i += 1
            if len(item) == 3:
                _, node, up = item
                if up_of[node] == up:
                    continue
                up_of[node] = up
                delta = -1 if up else 1
                if node in primary_nodes:
                    primary_down += delta
                if node in backup_nodes:
                    backup_down += delta
                new = target()
                if new != active:
                    # (Re)arm the changeover timer at t+W.
                    timer_start = now
                    timer_at = now + wait
                    timer_target = new
                else:
                    # The active path is already the target: cancel.
                    timer_start = timer_at = timer_target = None
            else:
                _, pid = item
                if not (up_of[source] and up_of[destination]):
                    # An endpoint is down.
                    packets.append([pid, now, 1, None, []])
                elif active is not None and (
                        primary_down if active is primary
                        else backup_down) == 0:
                    packets.append([pid, now, 0, active[0], active[1]])
                else:
                    packets.append([pid, now, 2, None, []])
        if timer_at is not None and timer_at == now:
            active = timer_target
            switches.append([timer_start, now,
                             active[1] if active is not None else []])
            timer_start = timer_at = timer_target = None

    return {"m": [primary[0], primary[1]] if primary is not None
            else [None, []],
            "b": [backup[0], backup[1]] if backup is not None
            else [None, []],
            "s": switches,
            "p": packets}


def compute_lfail(nodes, links, source, destination, wait, items):
    # Link-failure protection switching with a debounced changeover delay.
    # Primary: lowest-cost path in the initial up-graph, ties going to the
    # node sequence smallest in Unicode code point order (exactly the
    # shortest_paths tie-break). Backup: the same computation after
    # deleting the primary's directed edges; no primary means no backup.
    # Both are computed once here and never recomputed; link items only
    # flip link up states (repeated setting is idempotent).
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_path = path_of[destination]
    primary = ((cost_of[destination], primary_path)
               if primary_path is not None else None)
    backup = None
    if primary_path is not None:
        removed = set(zip(primary_path, primary_path[1:]))
        blinks = [link for link in up_links
                  if (link["from"], link["to"]) not in removed]
        bcost_of, bpath_of = shortest_paths(nodes, blinks, source)
        if bpath_of[destination] is not None:
            backup = (bcost_of[destination], bpath_of[destination])

    state = {(link["from"], link["to"]): link["up"] for link in links}
    # Down-edge counts on each candidate path, kept incrementally so a
    # link flip and the target selection are both O(1). Both paths were
    # computed over up links only, so every edge on them starts up.
    primary_edges = (set(zip(primary[1], primary[1][1:]))
                     if primary is not None else set())
    backup_edges = (set(zip(backup[1], backup[1][1:]))
                    if backup is not None else set())
    primary_down = 0
    backup_down = 0

    def target():
        # The first all-up of the primary and the backup, else no path.
        if primary is not None and primary_down == 0:
            return primary
        if backup is not None and backup_down == 0:
            return backup
        return None

    active = primary
    timer_start = None
    timer_at = None
    timer_target = None
    switches = []
    packets = []
    i = 0
    n = len(items)
    while i < n or timer_at is not None:
        wakes = []
        if i < n:
            wakes.append(items[i][0])
        if timer_at is not None:
            wakes.append(timer_at)
        now = min(wakes)
        # All items at this tick run in input order before a timer
        # completing on it; a timer due before the next item's tick
        # completes first.
        while i < n and items[i][0] == now:
            item = items[i]
            i += 1
            if len(item) == 4:
                _, u, v, up = item
                pair = (u, v)
                if state[pair] == up:
                    continue
                state[pair] = up
                delta = -1 if up else 1
                if pair in primary_edges:
                    primary_down += delta
                if pair in backup_edges:
                    backup_down += delta
                new = target()
                if new != active:
                    # (Re)arm the changeover timer at t+W.
                    timer_start = now
                    timer_at = now + wait
                    timer_target = new
                else:
                    # The active path is already the target: cancel.
                    timer_start = timer_at = timer_target = None
            else:
                _, pid = item
                if active is not None and (
                        primary_down if active is primary
                        else backup_down) == 0:
                    packets.append([pid, now, 0, active[0], active[1]])
                else:
                    packets.append([pid, now, 1, None, []])
        if timer_at is not None and timer_at == now:
            active = timer_target
            switches.append([timer_start, now,
                             active[1] if active is not None else []])
            timer_start = timer_at = timer_target = None

    return {"m": [primary[0], primary[1]] if primary is not None
            else [None, []],
            "b": [backup[0], backup[1]] if backup is not None
            else [None, []],
            "s": switches,
            "p": packets}


def compute_lrepair(nodes, links, source, destination, wait, items):
    # Link-failure local repair with a debounced changeover delay. The
    # primary is the lowest-cost path in the initial up-graph, ties going
    # to the node sequence smallest in Unicode code point order (exactly
    # the shortest_paths tie-break). One repair path is precomputed per
    # primary edge (u, v): delete that edge together with the primary
    # nodes strictly before u, then take the lowest-cost u->D path under
    # the same tie-break and splice the primary prefix S..u in front of
    # it; no primary, or any edge with no such u->D path, is an error.
    # The repairs are computed once here and never recomputed; link
    # items only flip link up states (repeated setting is idempotent).
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_path = path_of[destination]
    if primary_path is None:
        fail(5)
    primary = (cost_of[destination], primary_path)

    # repairs follows the primary's edge order; entry j covers
    # primary_path[j] -> primary_path[j+1] as (cost, full path).
    repairs = []
    for j in range(len(primary_path) - 1):
        u = primary_path[j]
        edge = (u, primary_path[j + 1])
        prefix = set(primary_path[:j])
        rlinks = [link for link in up_links
                  if link["from"] not in prefix
                  and link["to"] not in prefix
                  and (link["from"], link["to"]) != edge]
        rcost_of, rpath_of = shortest_paths(nodes, rlinks, u)
        suffix = rpath_of[destination]
        if suffix is None:
            fail(5)
        # u sits on the primary shortest path, so cost_of[u] is the
        # primary prefix's cost; the repair route's cost is the prefix
        # plus the u->D suffix cost.
        repairs.append((cost_of[u] + rcost_of[destination],
                        primary_path[:j + 1] + suffix[1:]))

    state = {(link["from"], link["to"]): link["up"] for link in links}
    repair_edges = [set(zip(route[1], route[1][1:]))
                    for route in repairs]
    primary_edges = set(zip(primary_path, primary_path[1:]))
    primary_down = 0
    repair_down = [0] * len(repairs)

    def route_of(target):
        return [target[0], target[1]] if target is not None else [None, []]

    def target():
        # The usable primary first; otherwise the first all-up repair in
        # primary-edge order, ties broken by cost then path order;
        # otherwise no path.
        if primary_down == 0:
            return primary
        choice = None
        choice_key = None
        for j, route in enumerate(repairs):
            if repair_down[j] == 0:
                key = (route[0], route[1])
                if choice_key is None or key < choice_key:
                    choice_key = key
                    choice = route
        return choice

    installed = primary
    timer_start = None
    timer_at = None
    timer_target = None
    events = []
    completed = 0
    i = 0
    n = len(items)
    while i < n or timer_at is not None:
        wakes = []
        if i < n:
            wakes.append(items[i][0])
        if timer_at is not None:
            wakes.append(timer_at)
        now = min(wakes)
        # All items at this tick run in input order before a timer
        # completing on it; a timer due before the next item's tick
        # completes first.
        while i < n and items[i][0] == now:
            _, u, v, up = items[i]
            i += 1
            pair = (u, v)
            real = 0
            old = route_of(installed)
            if state[pair] != up:
                state[pair] = up
                real = 1
                delta = -1 if up else 1
                if pair in primary_edges:
                    primary_down += delta
                for j, edges in enumerate(repair_edges):
                    if pair in edges:
                        repair_down[j] += delta
            new_target = target()
            if real:
                if new_target is None:
                    # Neither the primary nor any repair is usable.
                    fail(5)
                if new_target != installed:
                    # (Re)arm the changeover timer at t+W.
                    timer_start = now
                    timer_at = now + wait
                    if timer_at > MAX_TIME:
                        fail(5)
                    timer_target = new_target
                else:
                    # The installed route is already the target: cancel.
                    timer_start = timer_at = timer_target = None
            due = timer_at
            events.append([now, 0, u, v, up, real, old,
                           route_of(timer_target if timer_at is not None
                                    else installed),
                           due])
        if timer_at is not None and timer_at == now:
            old = installed
            installed = timer_target
            events.append([now, 1, route_of(old), route_of(installed),
                           now - timer_start])
            completed += 1
            timer_start = timer_at = timer_target = None

    return {"s": source, "d": destination,
            "m": route_of(primary),
            "b": [[primary_path[j], primary_path[j + 1],
                   route_of(repairs[j])]
                  for j in range(len(repairs))],
            "e": events, "r": completed, "f": route_of(installed)}


def compute_nrepair(nodes, links, source, destination, wait, items):
    # Node-failure local repair with a debounced changeover delay. The
    # primary is the lowest-cost path in the initial up-graph, ties going
    # to the node sequence smallest in Unicode code point order (exactly
    # the shortest_paths tie-break). One repair route is precomputed per
    # primary internal node v with predecessor u: delete v together with
    # the primary nodes strictly before u, then take the lowest-cost
    # u->D path under the same tie-break and splice the primary prefix
    # S..u in front of it; no primary, or any internal node with no such
    # u->D path, is an error. The repairs are computed once here and
    # never recomputed; node items only flip node up states (a repeated
    # setting is idempotent and leaves the timer alone).
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    primary_path = path_of[destination]
    if primary_path is None:
        fail(5)
    primary = (cost_of[destination], primary_path)

    # repairs follows the primary's internal-node order; entry j covers
    # internal primary node v=primary_path[j] (u=primary_path[j-1]) as
    # (cost, full path).
    repairs = []
    repair_nodes_list = []
    for j in range(1, len(primary_path) - 1):
        v = primary_path[j]
        u = primary_path[j - 1]
        removed = set(primary_path[:j - 1])
        removed.add(v)
        rlinks = [link for link in up_links
                  if link["from"] not in removed and link["to"] not in removed]
        rcost_of, rpath_of = shortest_paths(nodes, rlinks, u)
        suffix = rpath_of[destination]
        if suffix is None:
            fail(5)
        # u sits on the primary shortest path, so cost_of[u] is the
        # primary prefix's cost; the repair route's cost is the prefix
        # plus the u->D suffix cost.
        route = (cost_of[u] + rcost_of[destination],
                 primary_path[:j] + suffix[1:])
        repairs.append(route)
        repair_nodes_list.append(set(route[1]))

    up_of = {n: True for n in nodes}
    primary_nodes = set(primary_path)
    primary_down = 0
    repair_down = [0] * len(repairs)

    def route_of(target):
        return [target[0], target[1]] if target is not None else [None, []]

    def target():
        # The usable primary first; otherwise the all-up repair with the
        # smallest (cost, path); otherwise no path.
        if primary_down == 0:
            return primary
        choice = None
        choice_key = None
        for k, route in enumerate(repairs):
            if repair_down[k] == 0:
                key = (route[0], route[1])
                if choice_key is None or key < choice_key:
                    choice_key = key
                    choice = route
        return choice

    installed = primary
    timer_start = None
    timer_at = None
    timer_target = None
    events = []
    completed = 0
    i = 0
    n = len(items)
    while i < n or timer_at is not None:
        wakes = []
        if i < n:
            wakes.append(items[i][0])
        if timer_at is not None:
            wakes.append(timer_at)
        now = min(wakes)
        # All items at this tick run in input order before a timer
        # completing on it; a timer due before the next item's tick
        # completes first.
        while i < n and items[i][0] == now:
            _, node, up = items[i]
            i += 1
            real = 0
            old = route_of(installed)
            if up_of[node] != up:
                up_of[node] = up
                real = 1
                delta = -1 if up else 1
                if node in primary_nodes:
                    primary_down += delta
                for k, route_nodes in enumerate(repair_nodes_list):
                    if node in route_nodes:
                        repair_down[k] += delta
            new_target = target()
            if real:
                if new_target is None:
                    # Neither the primary nor any repair is usable.
                    fail(5)
                if new_target != installed:
                    # (Re)arm the changeover timer at t+W.
                    timer_start = now
                    timer_at = now + wait
                    if timer_at > MAX_TIME:
                        fail(5)
                    timer_target = new_target
                else:
                    # The installed route is already the target: cancel.
                    timer_start = timer_at = timer_target = None
            due = timer_at
            events.append([now, 0, node, up, real, old,
                           route_of(timer_target if timer_at is not None
                                    else installed),
                           due])
        if timer_at is not None and timer_at == now:
            old = installed
            installed = timer_target
            events.append([now, 1, route_of(old), route_of(installed),
                           now - timer_start])
            completed += 1
            timer_start = timer_at = timer_target = None

    return {"s": source, "d": destination,
            "m": route_of(primary),
            "b": [[primary_path[j], route_of(repairs[j - 1])]
                  for j in range(1, len(primary_path) - 1)],
            "e": events, "r": completed, "f": route_of(installed)}


def compute_fault(nodes, links, source, destination, wait, batches):
    # Node/link failure drill with a debounced recompute-and-install
    # delay. The installed route starts as the lowest-cost path in the
    # initial up-graph (every node starts up, links take their FILE
    # state), ties going to the node sequence smallest in Unicode code
    # point order (exactly the shortest_paths tie-break) — lfail's
    # primary. Each batch applies its node/link up-state settings
    # atomically; a setting that changes nothing is idempotent and
    # leaves the timer alone. A batch with at least one real change
    # cancels any pending timer, recomputes the lowest-cost target on
    # the current graph (up nodes and up links joining them, same
    # tie-break), and, when the target differs from the installed
    # route, arms a timer to install it at t+W; otherwise no timer
    # runs. At one tick the batch runs before a timer expiring on it; a
    # timer due before the next batch's tick expires first, and timers
    # still pending after the last batch keep advancing.
    up_links = [link for link in links if link["up"]]
    cost_of, path_of = shortest_paths(nodes, up_links, source)
    initial_path = path_of[destination]
    installed = ((cost_of[destination], initial_path)
                 if initial_path is not None else None)
    initial = installed

    node_up = {n: True for n in nodes}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}

    def recompute():
        # Lowest-cost path over up nodes and up links joining them.
        if not (node_up[source] and node_up[destination]):
            return None
        live_nodes = [n for n in nodes if node_up[n]]
        live_links = [{"from": link["from"], "to": link["to"],
                       "cost": link["cost"], "up": True}
                      for link in links
                      if link_up[(link["from"], link["to"])]
                      and node_up[link["from"]] and node_up[link["to"]]]
        live_cost_of, live_path_of = shortest_paths(live_nodes,
                                                    live_links, source)
        path = live_path_of[destination]
        return ((live_cost_of[destination], path)
                if path is not None else None)

    def route_of(target):
        return [target[0], target[1]] if target is not None else [None, []]

    timer_start = None
    timer_at = None
    timer_target = None
    events = []
    reroutes = 0
    i = 0
    n = len(batches)
    while i < n or timer_at is not None:
        wakes = []
        if i < n:
            wakes.append(batches[i][0])
        if timer_at is not None:
            wakes.append(timer_at)
        now = min(wakes)
        # The batch at this tick runs before a timer expiring on it; a
        # timer due before the next batch's tick expires first.
        if i < n and batches[i][0] == now:
            _, changes = batches[i]
            i += 1
            real = 0
            for change in changes:
                if change[0] == 0:
                    _, node, up = change
                    if node_up[node] != up:
                        node_up[node] = up
                        real += 1
                else:
                    _, u, v, up = change
                    pair = (u, v)
                    if link_up[pair] != up:
                        link_up[pair] = up
                        real += 1
            if real:
                # Cancel the old timer and re-target on the new graph.
                timer_start = timer_at = timer_target = None
                target = recompute()
                if target != installed:
                    # Arm the install timer at t+W.
                    timer_start = now
                    timer_at = now + wait
                    timer_target = target
            events.append([now, 0, real, route_of(installed),
                           route_of(timer_target if timer_at is not None
                                    else installed),
                           timer_at])
        if timer_at is not None and timer_at == now:
            old = installed
            installed = timer_target
            events.append([now, 1, route_of(old), route_of(installed),
                           now - timer_start])
            reroutes += 1
            timer_start = timer_at = timer_target = None

    return {"s": source, "d": destination, "i": route_of(initial),
            "e": events, "r": reroutes}


def compute_impair(nodes, links, source, destination, items):
    # Impairment replay on a static up-graph. Config items (0, t, u, v,
    # n, j) set the drop modulus n and latency jitter j of the directed
    # link u->v; they never touch its traversal counter, and repeated
    # identical settings are idempotent. Packet items (1, t, pid) are
    # routed at their t over the lowest-cost path in the up-graph, ties
    # going to the node sequence smallest in Unicode code point order
    # (exactly the shortest_paths tie-break). Config items never flip
    # link states, so the up-graph is static and the path is computed
    # once here; each packet then walks it edge by edge, incrementing
    # the edge's counter and accumulating latency+j before judging the
    # drop: a nonzero n drops the packet when the fresh counter value
    # is a multiple of n, and the walk stops at the first such edge.
    _, path_of = shortest_paths(nodes, links, source)
    path = path_of[destination]

    latency_of = {}
    n_of = {}
    j_of = {}
    count_of = {}
    for link in links:
        pair = (link["from"], link["to"])
        latency_of[pair] = link["latency"]
        n_of[pair] = 0
        j_of[pair] = 0
        count_of[pair] = 0

    packets = []
    delivered = 0
    lost = 0
    unreachable = 0
    delay_sum = 0
    for item in items:
        if item[0] == 0:
            _, _, u, v, n, j = item
            pair = (u, v)
            n_of[pair] = n
            j_of[pair] = j
            continue
        _, t, pid = item
        if path is None:
            unreachable += 1
            packets.append([pid, t, 2, None, None, []])
            continue
        delay = 0
        status = 0
        used = path
        for i in range(len(path) - 1):
            pair = (path[i], path[i + 1])
            count_of[pair] += 1
            delay += latency_of[pair] + j_of[pair]
            if t + delay > MAX_TIME:
                fail(5)
            n = n_of[pair]
            if n and count_of[pair] % n == 0:
                # The packet is lost on this edge; later edges are
                # neither counted nor timed.
                status = 1
                used = path[:i + 2]
                break
        if status == 0:
            delivered += 1
            delay_sum += delay
        else:
            lost += 1
        packets.append([pid, t, status, t + delay, delay, used])

    stats = [delivered, lost, unreachable,
             _format_peak(lost, delivered + lost)
             if delivered + lost else "0.000000",
             _format_peak(delay_sum, delivered)
             if delivered else "0.000000"]
    return {"source": source, "destination": destination,
            "packets": packets, "stats": stats}


def _compound_run(nodes, links, source, destination, wait, items,
                  state=None, cutoff=None):
    # Fault's debounced recompute-and-install driven by a mixed stream
    # of topology/impairment batches and packets. The installed route
    # starts as the lowest-cost path in the initial up-graph (every node
    # starts up, links take their FILE state), ties going to the node
    # sequence smallest in Unicode code point order (exactly the
    # shortest_paths tie-break). Each batch applies its node/link
    # up-state and link impairment settings atomically; a setting that
    # changes nothing is idempotent and leaves the timer alone, and
    # impairment settings never touch the traversal counters. A batch
    # with at least one real change cancels any pending timer,
    # recomputes the lowest-cost target on the current graph (up nodes
    # and up links joining them, same tie-break), and, when the target
    # differs from the installed route, arms a timer to install it at
    # t+W; otherwise no timer runs. Items at one tick run in input order
    # before a timer expiring on it; a timer due before the next item's
    # tick expires first, and timers still pending after the last item
    # keep advancing. A packet walks the installed route when every node
    # and link on it is currently up, edge by edge with impair's
    # count/latency/drop rules; otherwise it is a no-route loss.
    #
    # With state not None the run resumes from a checkpoint tuple
    # (installed, node_up, link_up, n_of, j_of, count_of, timer_start,
    # timer_at, timer_target, events, packets, counters) as returned by
    # an earlier _compound_run call, instead of from the initial
    # up-graph. With cutoff not None the clock stops before any wake at
    # or after it, leaving a timer due at or after the cutoff pending.
    # Returns (result, checkpoint) with checkpoint the same tuple shape,
    # so a cut run resumed from its checkpoint matches one uncut run
    # exactly.
    if state is None:
        up_links = [link for link in links if link["up"]]
        cost_of, path_of = shortest_paths(nodes, up_links, source)
        initial_path = path_of[destination]
        installed = ((cost_of[destination], initial_path)
                     if initial_path is not None else None)
        node_up = {n: True for n in nodes}
        link_up = {(link["from"], link["to"]): link["up"]
                   for link in links}
        n_of = {}
        j_of = {}
        count_of = {}
        for link in links:
            pair = (link["from"], link["to"])
            n_of[pair] = 0
            j_of[pair] = 0
            count_of[pair] = 0
        timer_start = None
        timer_at = None
        timer_target = None
        events = []
        packets = []
        delivered = 0
        lost = 0
        unreachable = 0
        reroutes = 0
    else:
        (installed, node_up, link_up, n_of, j_of, count_of,
         timer_start, timer_at, timer_target, events, packets,
         counters) = state
        delivered, lost, unreachable, reroutes = counters
    latency_of = {(link["from"], link["to"]): link["latency"]
                  for link in links}

    def recompute():
        # Lowest-cost path over up nodes and up links joining them.
        if not (node_up[source] and node_up[destination]):
            return None
        live_nodes = [n for n in nodes if node_up[n]]
        live_links = [{"from": link["from"], "to": link["to"],
                       "cost": link["cost"], "up": True}
                      for link in links
                      if link_up[(link["from"], link["to"])]
                      and node_up[link["from"]] and node_up[link["to"]]]
        live_cost_of, live_path_of = shortest_paths(live_nodes,
                                                    live_links, source)
        path = live_path_of[destination]
        return ((live_cost_of[destination], path)
                if path is not None else None)

    def route_of(target):
        return [target[0], target[1]] if target is not None else [None, []]

    i = 0
    n = len(items)
    while i < n or timer_at is not None:
        wakes = []
        if i < n:
            wakes.append(items[i][0])
        if timer_at is not None:
            wakes.append(timer_at)
        now = min(wakes)
        if cutoff is not None and now >= cutoff:
            # A wake at or after the cutoff belongs to the next run; a
            # timer due then stays pending in the checkpoint.
            break
        # Items at this tick run in input order before a timer expiring
        # on it; a timer due before the next item's tick expires first.
        while i < n and items[i][0] == now:
            item = items[i]
            i += 1
            if item[1] == 0:
                _, _, changes = item
                real_topo = 0
                real_impair = 0
                for change in changes:
                    if change[0] == 0:
                        _, node, up = change
                        if node_up[node] != up:
                            node_up[node] = up
                            real_topo += 1
                    elif change[0] == 1:
                        _, u, v, up = change
                        pair = (u, v)
                        if link_up[pair] != up:
                            link_up[pair] = up
                            real_topo += 1
                    else:
                        _, u, v, k, j = change
                        pair = (u, v)
                        if n_of[pair] != k or j_of[pair] != j:
                            n_of[pair] = k
                            j_of[pair] = j
                            real_impair += 1
                if real_topo or real_impair:
                    # Cancel the old timer and re-target on the new
                    # graph.
                    timer_start = timer_at = timer_target = None
                    target = recompute()
                    if target != installed:
                        # Arm the install timer at t+W.
                        timer_start = now
                        timer_at = now + wait
                        timer_target = target
                events.append([now, 0, real_topo, real_impair,
                               route_of(installed),
                               route_of(timer_target if timer_at is not None
                                        else installed),
                               timer_at])
            else:
                t, _, pid = item
                path = installed[1] if installed is not None else None
                if path is not None:
                    # The installed route is usable only while every
                    # node and link on it stays up.
                    for node in path:
                        if not node_up[node]:
                            path = None
                            break
                    if path is not None:
                        for u, v in zip(path, path[1:]):
                            if not link_up[(u, v)]:
                                path = None
                                break
                if path is None:
                    unreachable += 1
                    packets.append([pid, t, 2, None, None, []])
                else:
                    delay = 0
                    status = 0
                    used = path
                    for h in range(len(path) - 1):
                        pair = (path[h], path[h + 1])
                        count_of[pair] += 1
                        delay += latency_of[pair] + j_of[pair]
                        if t + delay > MAX_TIME:
                            fail(5)
                        mod = n_of[pair]
                        if mod and count_of[pair] % mod == 0:
                            # The packet is lost on this edge; later
                            # edges are neither counted nor timed.
                            status = 1
                            used = path[:h + 2]
                            break
                    if status == 0:
                        delivered += 1
                    else:
                        lost += 1
                    packets.append([pid, t, status, t + delay, delay,
                                    used])
        if timer_at is not None and timer_at == now:
            old = installed
            installed = timer_target
            events.append([now, 1, route_of(old), route_of(installed),
                           now - timer_start])
            reroutes += 1
            timer_start = timer_at = timer_target = None

    stats = [delivered, lost, unreachable, reroutes,
             _format_peak(lost, delivered + lost)
             if delivered + lost else "0.000000"]
    result = {"s": source, "d": destination, "e": events, "p": packets,
              "x": stats}
    checkpoint = (installed, node_up, link_up, n_of, j_of, count_of,
                  timer_start, timer_at, timer_target, events, packets,
                  (delivered, lost, unreachable, reroutes))
    return result, checkpoint


def compute_compound(nodes, links, source, destination, wait, items):
    # The plain compound entry: one uncut run from the initial up-graph
    # (see _compound_run for the full semantics).
    result, _ = _compound_run(nodes, links, source, destination, wait,
                              items)
    return result


def _parse_compound_items(data, node_set, pair_set, latency_of,
                          allow_empty=False, min_t=0, max_t=MAX_COST,
                          seen_ids=None):
    # Shared validation for compound/compoundcp DATA: a list of
    # [t, kind, payload] items (non-empty unless allow_empty) with t a
    # bounded integer inside [min_t, max_t] and non-decreasing, kind 0 a
    # non-empty change batch (node/link up flags and link impairments,
    # each object set at most once per batch), kind 1 a packet id unique
    # across the whole run (seen_ids seeds the set for a resumed run).
    # Returns the normalized (t, kind, ...) tuples.
    if not isinstance(data, list) or (not allow_empty and not data):
        fail(5)
    items = []
    if seen_ids is None:
        seen_ids = set()
    previous_time = None
    for item in data:
        if not isinstance(item, list) or len(item) != 3:
            fail(5)
        t, kind, payload = item
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if not min_t <= t <= max_t:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(kind) is not int or kind not in (0, 1):
            fail(5)
        if kind == 0:
            if not isinstance(payload, list) or not payload:
                fail(5)
            seen_nodes = set()
            seen_pairs = set()
            batch = []
            for change in payload:
                if (not isinstance(change, list)
                        or len(change) not in (3, 4, 5)):
                    fail(5)
                ckind = change[0]
                if type(ckind) is not int or ckind not in (0, 1, 2):
                    fail(5)
                if ckind == 0:
                    if len(change) != 3:
                        fail(5)
                    _, node, up = change
                    if type(node) is not str or node not in node_set:
                        fail(5)
                    if type(up) is not bool:
                        fail(5)
                    if node in seen_nodes:
                        fail(5)
                    seen_nodes.add(node)
                    batch.append((0, node, up))
                elif ckind == 1:
                    if len(change) != 4:
                        fail(5)
                    _, u, v, up = change
                    if (type(u) is not str or type(v) is not str
                            or (u, v) not in pair_set):
                        fail(5)
                    if type(up) is not bool:
                        fail(5)
                    if (u, v) in seen_pairs:
                        fail(5)
                    seen_pairs.add((u, v))
                    batch.append((1, u, v, up))
                else:
                    if len(change) != 5:
                        fail(5)
                    _, u, v, k, j = change
                    if (type(u) is not str or type(v) is not str
                            or (u, v) not in pair_set):
                        fail(5)
                    if type(k) is not int or not 0 <= k <= MAX_COST:
                        fail(5)
                    if (type(j) is not int
                            or not 0 <= latency_of[(u, v)] + j
                            <= MAX_COST):
                        fail(5)
                    if (u, v) in seen_pairs:
                        fail(5)
                    seen_pairs.add((u, v))
                    batch.append((2, u, v, k, j))
            items.append((t, 0, batch))
        else:
            pid = payload
            if type(pid) is not str or not 1 <= len(pid) <= 64:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if pid in seen_ids:
                fail(5)
            seen_ids.add(pid)
            items.append((t, 1, pid))
    return items


def _compoundcp_state(file_bytes, nodes, links, source, destination,
                      wait, at, checkpoint):
    # Build the compoundcp checkpoint STATE object from an _compound_run
    # checkpoint: keys b,n,l,r,g,e,p,c,h in this order, h the SHA-256 of
    # FILE's raw bytes followed by the compact UTF-8 JSON of
    # [b,n,l,r,g,e,p,c], lowercase hex.
    (installed, node_up, link_up, n_of, j_of, count_of,
     timer_start, timer_at, timer_target, events, packets,
     counters) = checkpoint
    b = [source, destination, wait, at]
    n_arr = [node_up[node] for node in nodes]
    l_arr = []
    for link in links:
        pair = (link["from"], link["to"])
        l_arr.append([link_up[pair], n_of[pair], j_of[pair],
                      count_of[pair]])
    r = [installed[0], installed[1]] if installed is not None \
        else [None, []]
    if timer_at is None:
        g = None
    else:
        g = [timer_start, timer_at,
             [timer_target[0], timer_target[1]]
             if timer_target is not None else [None, []]]
    c = list(counters)
    payload = json.dumps([b, n_arr, l_arr, r, g, events, packets, c],
                         ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(
        file_bytes + payload.encode("utf-8")).hexdigest()
    return {"b": b, "n": n_arr, "l": l_arr, "r": r, "g": g, "e": events,
            "p": packets, "c": c, "h": digest}


def _check_cp_route(route, node_set, pair_set, cost_of_pair, source,
                    destination):
    # An r-style route: [cost, path] or [null, []], the path a simple
    # source-to-destination walk over existing edges whose cost sum is
    # exactly the recorded cost.
    if not isinstance(route, list) or len(route) != 2:
        fail(5)
    cost, path = route
    if cost is None:
        if path != []:
            fail(5)
        return
    if type(cost) is not int or cost < 0:
        fail(5)
    if (not isinstance(path, list) or len(path) < 2
            or path[0] != source or path[-1] != destination):
        fail(5)
    for node in path:
        if type(node) is not str or node not in node_set:
            fail(5)
    if len(set(path)) != len(path):
        fail(5)
    total = 0
    for x, y in zip(path, path[1:]):
        if (x, y) not in pair_set:
            fail(5)
        total += cost_of_pair[(x, y)]
    if total != cost:
        fail(5)


def _check_compoundcp_ep(e, p, c, at, node_set, pair_set, cost_of_pair,
                         source, destination):
    # Checkpoint event/packet logs must be item-by-item what a compound
    # run emits: kind-0 batch events [t,0,topo,impair,route,route,timer]
    # and kind-1 install events [t,1,route,route,elapsed]; packet records
    # [pid,t,status,arrival,delay,used] with null arrival/delay and an
    # empty used exactly when status is 2. Times stay below AT and
    # non-decreasing inside each log, packet ids are unique, and c
    # tallies [status-0, status-1, status-2 packets, completed installs].
    if not isinstance(e, list) or not isinstance(p, list):
        fail(5)
    completed = 0
    previous = None
    for entry in e:
        if not isinstance(entry, list) or len(entry) not in (5, 7):
            fail(5)
        t, kind = entry[0], entry[1]
        if type(t) is not int or not 0 <= t < at:
            fail(5)
        if previous is not None and t < previous:
            fail(5)
        previous = t
        if type(kind) is not int or kind not in (0, 1):
            fail(5)
        if kind == 0:
            if len(entry) != 7:
                fail(5)
            _, _, topo, impair, current, pending, timer = entry
            if type(topo) is not int or not 0 <= topo <= MAX_TIME:
                fail(5)
            if type(impair) is not int or not 0 <= impair <= MAX_TIME:
                fail(5)
            _check_cp_route(current, node_set, pair_set, cost_of_pair,
                            source, destination)
            _check_cp_route(pending, node_set, pair_set, cost_of_pair,
                            source, destination)
            if timer is not None and (type(timer) is not int
                                      or not t <= timer <= MAX_TIME):
                fail(5)
        else:
            if len(entry) != 5:
                fail(5)
            _, _, old, new, elapsed = entry
            _check_cp_route(old, node_set, pair_set, cost_of_pair,
                            source, destination)
            _check_cp_route(new, node_set, pair_set, cost_of_pair,
                            source, destination)
            if type(elapsed) is not int or not 0 <= elapsed <= MAX_TIME:
                fail(5)
            completed += 1
    seen_ids = set()
    tallies = [0, 0, 0]
    previous = None
    for entry in p:
        if not isinstance(entry, list) or len(entry) != 6:
            fail(5)
        pid, t, status, arrival, delay, used = entry
        if type(pid) is not str or not 1 <= len(pid) <= 64:
            fail(5)
        try:
            pid.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if pid in seen_ids:
            fail(5)
        seen_ids.add(pid)
        if type(t) is not int or not 0 <= t < at:
            fail(5)
        if previous is not None and t < previous:
            fail(5)
        previous = t
        if type(status) is not int or status not in (0, 1, 2):
            fail(5)
        tallies[status] += 1
        if status == 2:
            if arrival is not None or delay is not None or used != []:
                fail(5)
        else:
            if (type(arrival) is not int
                    or not 0 <= arrival <= MAX_TIME
                    or type(delay) is not int
                    or not 0 <= delay <= MAX_TIME
                    or arrival != t + delay):
                fail(5)
            if not isinstance(used, list) or len(used) < 2:
                fail(5)
            for node in used:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if used[0] != source or len(set(used)) != len(used):
                fail(5)
            for x, y in zip(used, used[1:]):
                if (x, y) not in pair_set:
                    fail(5)
            if status == 0 and used[-1] != destination:
                fail(5)
    if not isinstance(c, list) or len(c) != 4:
        fail(5)
    for x in c:
        if type(x) is not int or not 0 <= x <= MAX_TIME:
            fail(5)
    if c != [tallies[0], tallies[1], tallies[2], completed]:
        fail(5)


def _validate_compoundcp_state(data, file_bytes, nodes, links, node_set,
                               source, destination, wait, at):
    # Validate a compoundcp checkpoint and return the engine state tuple
    # for _compound_run. The key order and the h digest over FILE's raw
    # bytes plus the compact UTF-8 JSON of [b,n,l,r,g,e,p,c] are checked
    # first (a mismatch is code 5), then the content itself.
    keys = ["b", "n", "l", "r", "g", "e", "p", "c", "h"]
    if not isinstance(data, dict) or list(data.keys()) != keys:
        fail(5)
    b = data["b"]
    n_arr = data["n"]
    l_arr = data["l"]
    r = data["r"]
    g = data["g"]
    e = data["e"]
    p = data["p"]
    c = data["c"]
    h = data["h"]
    if type(h) is not str:
        fail(5)
    payload = json.dumps([b, n_arr, l_arr, r, g, e, p, c],
                         ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(
        file_bytes + payload.encode("utf-8")).hexdigest()
    if h != digest:
        fail(5)
    # b pins the checkpoint to this invocation's parameters.
    if (not isinstance(b, list) or len(b) != 4
            or b[0] != source or b[1] != destination
            or type(b[2]) is not int or b[2] != wait
            or type(b[3]) is not int or b[3] != at):
        fail(5)
    if not isinstance(n_arr, list) or len(n_arr) != len(nodes):
        fail(5)
    for up in n_arr:
        if type(up) is not bool:
            fail(5)
    if not isinstance(l_arr, list) or len(l_arr) != len(links):
        fail(5)
    for index, entry in enumerate(l_arr):
        if not isinstance(entry, list) or len(entry) != 4:
            fail(5)
        up, k, j, count = entry
        if type(up) is not bool:
            fail(5)
        if type(k) is not int or not 0 <= k <= MAX_COST:
            fail(5)
        if (type(j) is not int
                or not 0 <= links[index]["latency"] + j <= MAX_COST):
            fail(5)
        if type(count) is not int or not 0 <= count <= MAX_TIME:
            fail(5)
    pair_set = {(link["from"], link["to"]) for link in links}
    cost_of_pair = {(link["from"], link["to"]): link["cost"]
                    for link in links}
    _check_cp_route(r, node_set, pair_set, cost_of_pair, source,
                    destination)
    if g is not None:
        if not isinstance(g, list) or len(g) != 3:
            fail(5)
        start, due, target = g
        # A retained timer was armed before AT and expires at or after
        # it; a timer due earlier would already have fired.
        if type(start) is not int or type(due) is not int:
            fail(5)
        if not 0 <= start < at or due != start + wait or due < at:
            fail(5)
        _check_cp_route(target, node_set, pair_set, cost_of_pair,
                        source, destination)
    _check_compoundcp_ep(e, p, c, at, node_set, pair_set, cost_of_pair,
                         source, destination)

    installed = None if r[0] is None else (r[0], r[1])
    node_up = dict(zip(nodes, n_arr))
    link_up = {}
    n_of = {}
    j_of = {}
    count_of = {}
    for index, link in enumerate(links):
        pair = (link["from"], link["to"])
        up, k, j, count = l_arr[index]
        link_up[pair] = up
        n_of[pair] = k
        j_of[pair] = j
        count_of[pair] = count
    if g is None:
        timer_start = timer_at = timer_target = None
    else:
        timer_start = g[0]
        timer_at = g[1]
        timer_target = None if g[2][0] is None else (g[2][0], g[2][1])
    counters = (c[0], c[1], c[2], c[3])
    return (installed, node_up, link_up, n_of, j_of, count_of,
            timer_start, timer_at, timer_target, e, p, counters)


def _check_branch_name(name):
    # A checkpoint name follows the packet-id rules: a 1..64 character
    # UTF-8 string.
    if type(name) is not str or not 1 <= len(name) <= 64:
        fail(5)
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        fail(5)


def _copy_engine_state(state):
    # Shallow-copy the mutable parts of an _compound_run state tuple so
    # sibling branches resuming from the same checkpoint never see each
    # other's mutations (entries themselves are never mutated in place).
    (installed, node_up, link_up, n_of, j_of, count_of,
     timer_start, timer_at, timer_target, events, packets,
     counters) = state
    return (installed, dict(node_up), dict(link_up), dict(n_of),
            dict(j_of), dict(count_of), timer_start, timer_at,
            timer_target, list(events), list(packets), counters)


def _load_branch_db(path):
    # Read the raw bytes and strictly decode the branch DB. A missing
    # file returns (None, None) so an OP0 commit can bootstrap an empty
    # DB; every other open/read failure is fatal code 3 for all ops
    # (callers also turn None into code 3 for ops 1/2/3). Invalid UTF-8
    # or JSON (syntax, duplicate keys, non-finite numbers) is code 4.
    # The exact on-disk bytes come back too so a write op can skip the
    # atomic replace when nothing changed.
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return None, None
    except OSError:
        fail(3)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        fail(4)
    try:
        db = json.loads(text, parse_constant=_reject_constant,
                        parse_float=_finite_float,
                        object_pairs_hook=_object_no_dup)
    except (ValueError, RecursionError):
        fail(4)
    return db, raw


def _validate_branch_db(db, file_bytes, nodes, links, node_set, source,
                        destination, wait):
    # Validate a decoded branch DB {"p": [[name, parent, data, state],
    # ...]} and replay every entry along its parent chain: each stored
    # nine-key STATE must match the checkpoint recomputed from the
    # parent's checkpoint with the entry's DATA (roots start from the
    # initial up-graph, child items take parent-AT <= t < AT), and each
    # parent must be null or an earlier unique name. Any state or
    # parent-chain mismatch is code 5. Returns (records, by_name) with
    # each record [name, parent, data, state, checkpoint], checkpoint
    # the recomputed engine state a child would resume from.
    if not isinstance(db, dict) or list(db.keys()) != ["p"]:
        fail(5)
    entries = db["p"]
    if not isinstance(entries, list):
        fail(5)
    pair_set = {(link["from"], link["to"]) for link in links}
    latency_of = {(link["from"], link["to"]): link["latency"]
                  for link in links}
    records = []
    by_name = {}
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 4:
            fail(5)
        name, parent, data, state = entry
        _check_branch_name(name)
        if name in by_name:
            fail(5)
        if parent is not None \
                and (type(parent) is not str or parent not in by_name):
            fail(5)
        if not isinstance(state, dict):
            fail(5)
        b = state.get("b")
        if not isinstance(b, list) or len(b) != 4 \
                or type(b[3]) is not int or not 0 <= b[3] <= MAX_COST:
            fail(5)
        at = b[3]
        _validate_compoundcp_state(state, file_bytes, nodes, links,
                                   node_set, source, destination, wait,
                                   at)
        if parent is None:
            items = _parse_compound_items(data, node_set, pair_set,
                                          latency_of, allow_empty=True,
                                          max_t=at - 1)
            _, checkpoint = _compound_run(nodes, links, source,
                                          destination, wait, items,
                                          cutoff=at)
        else:
            parent_record = by_name[parent]
            parent_at = parent_record[3]["b"][3]
            if at < parent_at:
                fail(5)
            seen_ids = {pkt[0] for pkt in parent_record[3]["p"]}
            items = _parse_compound_items(data, node_set, pair_set,
                                          latency_of, allow_empty=True,
                                          min_t=parent_at, max_t=at - 1,
                                          seen_ids=seen_ids)
            _, checkpoint = _compound_run(
                nodes, links, source, destination, wait, items,
                state=_copy_engine_state(parent_record[4]), cutoff=at)
        recomputed = _compoundcp_state(file_bytes, nodes, links, source,
                                       destination, wait, at, checkpoint)
        if state != recomputed:
            fail(5)
        record = [name, parent, data, state, checkpoint]
        records.append(record)
        by_name[name] = record
    return records, by_name


def _parse_drill_events(raw_events, up_pairs, node_set, a, b):
    # Shared validation for drill/multidrill event lists: t is a bounded
    # integer inside [a, b] and non-decreasing; node events carry a known
    # node plus bool, link events carry an edge that is up in FILE plus
    # bool. A link already down can neither open a failure nor be flipped
    # back. Returns the normalized (t, kind, ...) tuples.
    events = []
    previous_time = None
    for event in raw_events:
        if not isinstance(event, list) or len(event) not in (4, 5):
            fail(5)
        t = event[0]
        kind = event[1]
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if not a <= t <= b:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(kind) is not int or kind not in (0, 1):
            fail(5)
        if kind == 0:
            if len(event) != 4:
                fail(5)
            _, _, node, up = event
            if type(node) is not str or node not in node_set:
                fail(5)
            if type(up) is not bool:
                fail(5)
            events.append((t, 0, node, up))
        else:
            if len(event) != 5:
                fail(5)
            _, _, u, v, up = event
            if (type(u) is not str or type(v) is not str
                    or (u, v) not in up_pairs):
                fail(5)
            if type(up) is not bool:
                fail(5)
            events.append((t, 1, u, v, up))
    return events


def _parse_drill_items(data, node_set, pair_set):
    # Shared validation for drill/multidrill records, reusing the audit
    # schema exactly: edges only need to exist in the topology, up or
    # down, since the data is a record of paths already taken. Returns
    # (pid, f, t, s, d, path) tuples in input (non-decreasing t) order.
    items = []
    seen_ids = set()
    previous_time = None
    for item in data:
        if not isinstance(item, list) or len(item) != 6:
            fail(5)
        pid, f, t, s, d, path = item
        if type(pid) is not str or not 1 <= len(pid) <= 64:
            fail(5)
        try:
            pid.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if pid in seen_ids:
            fail(5)
        seen_ids.add(pid)
        if type(f) is not str or not 1 <= len(f) <= 64:
            fail(5)
        try:
            f.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(s) is not int or s not in (0, 1, 2):
            fail(5)
        if s == 2:
            # A no-route loss carries no delay and no path at all.
            if d is not None or path != []:
                fail(5)
        else:
            if type(d) is not int or not 0 <= d <= MAX_TIME:
                fail(5)
            # A non-empty simple node array walking directed edges
            # (length >= 2 for s=1, so a last edge exists).
            if not isinstance(path, list) or not path:
                fail(5)
            if s == 1 and len(path) < 2:
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for x, y in zip(path, path[1:]):
                if (x, y) not in pair_set:
                    fail(5)
        items.append((pid, f, t, s, d, path))
    return items


def _is_policy(value):
    # An SLO policy as used by slogate: a six-element list of
    # non-boolean integers in [0, MAX_COST] ([u, o, d, f, s, g]).
    return (isinstance(value, list) and len(value) == 6
            and all(type(x) is int and 0 <= x <= MAX_COST for x in value))


def _load_state(path):
    # Read and strictly decode the hotload state file. JSON syntax
    # errors, duplicate keys, and non-finite numbers are code 4; any
    # read/UTF-8 problem is code 3. Structural/range checks belong to
    # _validate_hotload_state and stay code 5.
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        fail(3)
    except UnicodeDecodeError:
        fail(4)
    try:
        data = json.loads(text, parse_constant=_reject_constant,
                          parse_float=_finite_float,
                          object_pairs_hook=_object_no_dup)
    except (ValueError, RecursionError):
        fail(4)
    return data


def _validate_hotload_state(data):
    # State is {"v": v, "p": p, "h": h} with keys in that order: v is
    # the current version, p the current policy, and h a version-zero
    # continuous history of [version, policy] pairs whose last entry is
    # exactly [v, p]. Returns the normalized (v, p, h).
    if not isinstance(data, dict) or list(data.keys()) != ["v", "p", "h"]:
        fail(5)
    v = data["v"]
    p = data["p"]
    h = data["h"]
    if type(v) is not int or not 0 <= v <= MAX_COST:
        fail(5)
    if not _is_policy(p):
        fail(5)
    if not isinstance(h, list) or len(h) != v + 1:
        fail(5)
    expected_version = 0
    for entry in h:
        if not isinstance(entry, list) or len(entry) != 2:
            fail(5)
        hv, hp = entry
        if type(hv) is not int or hv != expected_version:
            fail(5)
        if not _is_policy(hp):
            fail(5)
        expected_version += 1
    if h[-1][0] != v or h[-1][1] != p:
        fail(5)
    return v, p, [list(entry) for entry in h]


def _validate_config_pack(data):
    # A config pack is {"v": v, "t": t, "p": p, "h": h} with keys in
    # that order: v is the current version, t the current topology
    # (metric's FILE mode), p the current policy (slogate's six-int
    # POLICY), and h a non-empty version-zero continuous history of
    # [version, t, p] triples whose every t/p is valid and whose last
    # entry is exactly [v, t, p]. Returns the normalized (v, t, p, h).
    if not isinstance(data, dict) or list(data.keys()) != ["v", "t", "p", "h"]:
        fail(5)
    v = data["v"]
    t = data["t"]
    p = data["p"]
    h = data["h"]
    if type(v) is not int or not 0 <= v <= MAX_COST:
        fail(5)
    _validate_topology(t, metrics=True)
    if not _is_policy(p):
        fail(5)
    if not isinstance(h, list) or len(h) == 0 or len(h) != v + 1:
        fail(5)
    expected_version = 0
    for entry in h:
        if not isinstance(entry, list) or len(entry) != 3:
            fail(5)
        hv, ht, hp = entry
        if type(hv) is not int or hv != expected_version:
            fail(5)
        _validate_topology(ht, metrics=True)
        if not _is_policy(hp):
            fail(5)
        expected_version += 1
    if h[-1][0] != v or h[-1][1] != t or h[-1][2] != p:
        fail(5)
    return v, t, p, [list(entry) for entry in h]


def _validate_policytx_rules(rule_items, node_set, pair_set):
    # policytx rule set: each rule is [n, s, d, a, b, c, path]. n, s, d,
    # c, and path follow the policy subcommand's rule checks; the policy
    # wildcard port p is replaced by the closed interval [a, b] with
    # 0 <= a <= b <= 65535. Returns the rules as 7-tuples in array order.
    if not isinstance(rule_items, list):
        fail(5)
    rules = []
    for item in rule_items:
        if not isinstance(item, list) or len(item) != 7:
            fail(5)
        n, s, d, a, b, c, path = item
        if type(n) is not int or not 0 <= n <= MAX_COST:
            fail(5)
        if (type(s) is not str or type(d) is not str
                or s not in node_set or d not in node_set):
            fail(5)
        if (type(a) is not int or type(b) is not int
                or not 0 <= a <= b <= 65535):
            fail(5)
        if c is not None:
            if type(c) is not str or not 1 <= len(c) <= 32:
                fail(5)
            try:
                c.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
        if (not isinstance(path, list) or not path
                or path[0] != s or path[-1] != d):
            fail(5)
        for node in path:
            if type(node) is not str or node not in node_set:
                fail(5)
        if len(set(path)) != len(path):
            fail(5)
        for edge_a, edge_b in zip(path, path[1:]):
            if (edge_a, edge_b) not in pair_set:
                fail(5)
        rules.append((n, s, d, a, b, c, path))
    return rules


def _validate_policytx_state(data, node_set, pair_set):
    # A policytx STATE is {"v": v, "r": r} (legacy, read-only: the
    # history is treated as h=[[v, r]]) or {"v": v, "r": r, "h": h}
    # with exactly those keys in that order. v is the current version
    # in 0..MAX_COST, r the current rule set (see
    # _validate_policytx_rules), and h a non-empty array of
    # [version, rules] pairs whose versions are continuous from the
    # first entry's version through v and whose last entry is exactly
    # [v, r]. Returns the normalized (v, rules, history); legacy
    # states are never migrated on disk.
    if not isinstance(data, dict):
        fail(5)
    keys = list(data.keys())
    if keys == ["v", "r"]:
        legacy = True
    elif keys == ["v", "r", "h"]:
        legacy = False
    else:
        fail(5)
    v = data["v"]
    if type(v) is not int or not 0 <= v <= MAX_COST:
        fail(5)
    rules = _validate_policytx_rules(data["r"], node_set, pair_set)
    if legacy:
        return v, rules, [[v, rules]]
    history_raw = data["h"]
    if not isinstance(history_raw, list) or len(history_raw) == 0:
        fail(5)
    first_entry = history_raw[0]
    if (not isinstance(first_entry, list) or len(first_entry) != 2
            or type(first_entry[0]) is not int
            or first_entry[0] < 0):
        fail(5)
    history = []
    expected_version = first_entry[0]
    for entry in history_raw:
        if not isinstance(entry, list) or len(entry) != 2:
            fail(5)
        hv, hr = entry
        if type(hv) is not int or hv != expected_version:
            fail(5)
        history.append([hv, _validate_policytx_rules(
            hr, node_set, pair_set)])
        expected_version += 1
    if history[-1][0] != v or history[-1][1] != rules:
        fail(5)
    return v, rules, history


def _policytx_rule_shape(item):
    # Topology-independent shape/range check for one policytx rule
    # [n, s, d, a, b, c, path]: n in 0..MAX_COST, s/d are strings (node
    # membership is checked against the selected replay topology),
    # 0 <= a <= b <= 65535, c is null or a 1..32 UTF-8 codepoint string,
    # and path is a non-empty list of strings starting at s and ending
    # at d with no repeated node. Edge membership (and therefore whether
    # the rule is legal for the topology) is checked by the caller via
    # _validate_policytx_rules against the selected topology's pair set.
    if not isinstance(item, list) or len(item) != 7:
        fail(5)
    n, s, d, a, b, c, path = item
    if type(n) is not int or not 0 <= n <= MAX_COST:
        fail(5)
    if type(s) is not str or type(d) is not str:
        fail(5)
    if (type(a) is not int or type(b) is not int
            or not 0 <= a <= b <= 65535):
        fail(5)
    if c is not None:
        if type(c) is not str or not 1 <= len(c) <= 32:
            fail(5)
        try:
            c.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
    if (not isinstance(path, list) or not path
            or path[0] != s or path[-1] != d):
        fail(5)
    for node in path:
        if type(node) is not str:
            fail(5)
    if len(set(path)) != len(path):
        fail(5)
    return item


def _policytx_state_shape(data):
    # Topology-independent structural validation of a policytx STATE,
    # used by the read-only policyreplay entry point where a single STATE
    # may hold rule sets for several different pack topologies and so no
    # single node/pair set can validate every history entry up front.
    # Accepts the legacy {"v", "r"} form (history h=[[v, r]]) and the
    # {"v", "r", "h"} form with exactly those keys in that order. v is in
    # 0..MAX_COST, r is a rule set (shape only), and h is a non-empty
    # array of [version, rules] pairs whose versions are continuous from
    # the first entry's version through v and whose last entry is exactly
    # [v, r]. Returns the normalized (v, history) with each rule set only
    # shape-checked; binding to the selected topology happens after PV is
    # chosen. The raw rule arrays (not tuples) are kept so equality of
    # the last entry against [v, r] mirrors _validate_policytx_state.
    if not isinstance(data, dict):
        fail(5)
    keys = list(data.keys())
    if keys == ["v", "r"]:
        legacy = True
    elif keys == ["v", "r", "h"]:
        legacy = False
    else:
        fail(5)
    v = data["v"]
    if type(v) is not int or not 0 <= v <= MAX_COST:
        fail(5)
    current = data["r"]
    if not isinstance(current, list):
        fail(5)
    for item in current:
        _policytx_rule_shape(item)
    if legacy:
        return v, [[v, [list(rule) for rule in current]]]
    history_raw = data["h"]
    if not isinstance(history_raw, list) or len(history_raw) == 0:
        fail(5)
    first_entry = history_raw[0]
    if (not isinstance(first_entry, list) or len(first_entry) != 2
            or type(first_entry[0]) is not int
            or first_entry[0] < 0):
        fail(5)
    history = []
    expected_version = first_entry[0]
    for entry in history_raw:
        if not isinstance(entry, list) or len(entry) != 2:
            fail(5)
        hv, hr = entry
        if type(hv) is not int or hv != expected_version:
            fail(5)
        if not isinstance(hr, list):
            fail(5)
        for item in hr:
            _policytx_rule_shape(item)
        history.append([hv, [list(rule) for rule in hr]])
        expected_version += 1
    if history[-1][0] != v or history[-1][1] != \
            [list(rule) for rule in current]:
        fail(5)
    return v, history


def _policytx_export_object(v, rules, history):
    # Normalized history export (policytx op 4): an object with key
    # order v, r, h; h keeps the version and rule-set order, and a
    # legacy state is exported as h=[[v, r]]. Rules are copied back to
    # plain 7-item arrays in array order.
    return {"v": v, "r": [list(rule) for rule in rules],
            "h": [[hv, [list(rule) for rule in hr]]
                  for hv, hr in history]}


def _write_distinct_atomic(dst_path, blocked_paths, payload):
    # Atomically write payload to dst_path via an exclusively created
    # sibling temp file, but only when dst does not already hold those
    # bytes (same bytes rewrite nothing, status 1). Every path in
    # blocked_paths must name a different file than dst_path (both as
    # normalized strings and, when both exist on disk, by
    # os.path.samefile); dst_path itself must be a non-empty path. A
    # blocked/empty path is code 5; any existing dst read problem other
    # than absence and any write problem is code 3. The blocked paths
    # were themselves read successfully earlier, so they exist. On
    # failure the destination keeps its bytes and only this call's temp
    # file is removed.
    if type(dst_path) is not str or dst_path == "":
        fail(5)
    if "\x00" in dst_path:
        # A path with an embedded NUL can never name a file.
        fail(5)
    try:
        dst_norm = os.path.abspath(dst_path)
    except (OSError, ValueError):
        fail(5)
    blocked_norms = []
    for blocked in blocked_paths:
        if type(blocked) is not str or blocked == "" or "\x00" in blocked:
            fail(5)
        try:
            blocked_norm = os.path.abspath(blocked)
        except (OSError, ValueError):
            fail(5)
        if blocked_norm == dst_norm:
            fail(5)
        blocked_norms.append(blocked_norm)
    try:
        with open(dst_norm, "rb") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = None
    except OSError:
        fail(3)
    for blocked_norm in blocked_norms:
        try:
            if os.path.samefile(dst_norm, blocked_norm):
                fail(5)
        except FileNotFoundError:
            # dst absent (blocked exists): distinct files.
            pass
        except OSError:
            fail(3)
    if existing == payload:
        return 1
    directory = os.path.dirname(dst_norm)
    suffix = 0
    while True:
        tmp_path = os.path.join(directory,
                                os.path.basename(dst_norm)
                                + ".tmp." + str(suffix))
        try:
            fd = os.open(tmp_path,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            suffix += 1
            continue
        except OSError:
            fail(3)
        break
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, dst_norm)
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        fail(3)
    return 0


def _state_payload(state):
    # Canonical on-disk form: top-level key order v,p,h, compact
    # separators, non-ASCII UTF-8, integers in decimal, one trailing LF.
    text = json.dumps(state, ensure_ascii=False,
                      separators=(",", ":")) + "\n"
    return text.encode("utf-8")


def _write_state_atomic(path, state):
    # Replace the state file atomically: serialize, then exclusively
    # create a unique sibling temp file with an incrementing suffix (a
    # collision only retries under the next name), flush+fsync it,
    # os.replace it over the destination, then fsync the directory.
    # Any failure removes only the temp file this call acquired and
    # leaves the destination byte-for-byte untouched.
    payload = _state_payload(state)
    directory = os.path.dirname(os.path.abspath(path))
    suffix = 0
    while True:
        tmp_path = path + ".tmp." + str(suffix)
        try:
            fd = os.open(tmp_path,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:
            suffix += 1
            continue
        except OSError:
            fail(3)
        break
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        fail(3)


def _config_rollback(pack_path, pack, v, topo, policy, history, base,
                     ts_list, q_pairs):
    # Multi-version safe rollback (config op 3). Every TS version must
    # appear in the history (version-zero continuous over 0..v) and every
    # Q endpoint must be a node of the current topology. For each TS in
    # order, each [s, d] in Q is routed on the current topology and on
    # that version's topology with the route subcommand's lowest-cost
    # path (R = [cost, path], [null, []] when unreachable; a target
    # topology missing an endpoint counts as no route). A version passes
    # when every currently reachable pair stays reachable at no higher
    # cost; the first passing version is selected. No passer is status 2;
    # a selected configuration equal to the current one is status 1 and
    # BASE is ignored; otherwise BASE must equal v with v < MAX_COST, the
    # selected [t, p] is appended to the untruncated history as version
    # v+1 and the pack is replaced atomically (status 0). Runs T*K
    # Dijkstra searches (one per distinct source per trial topology, the
    # current topology's shared across trials), each O(V^2 + E), and
    # keeps the TK trial rows of at most V-node paths: O(TK(V^2 + E) + S)
    # time and O(TKV + S) space with S the total input/output size.
    cur_nodes = topo["nodes"]
    cur_links = topo["links"]
    cur_node_set = set(cur_nodes)
    for ts in ts_list:
        if ts > v:
            fail(5)
    for s, d in q_pairs:
        if s not in cur_node_set or d not in cur_node_set:
            fail(5)

    # Routes on the current topology, computed once per distinct source.
    cur_cost = {}
    cur_path = {}
    for s, _d in q_pairs:
        if s not in cur_cost:
            cur_cost[s], cur_path[s] = shortest_paths(cur_nodes, cur_links,
                                                      s)

    trials = []
    selected = None
    for ts in ts_list:
        target = history[ts][1]
        t_nodes = target["nodes"]
        t_links = target["links"]
        t_node_set = set(t_nodes)
        t_cost = {}
        t_path = {}
        rows = []
        passes = True
        for s, d in q_pairs:
            old_cost = cur_cost[s][d]
            old_r = ([old_cost, cur_path[s][d]] if old_cost is not None
                     else [None, []])
            if s not in t_node_set or d not in t_node_set:
                new_r = [None, []]
            else:
                if s not in t_cost:
                    t_cost[s], t_path[s] = shortest_paths(t_nodes, t_links,
                                                          s)
                new_cost = t_cost[s][d]
                new_r = ([new_cost, t_path[s][d]] if new_cost is not None
                         else [None, []])
            if old_cost is not None \
                    and (new_r[0] is None or new_r[0] > old_cost):
                passes = False
            rows.append([s, d, old_r, new_r])
        trials.append([ts, passes, rows])
        if selected is None and passes:
            selected = ts

    if selected is None:
        return {"op": 3, "status": 2, "selected": None, "trials": trials,
                "config": pack}
    sel_t = history[selected][1]
    sel_p = history[selected][2]
    if sel_t == topo and sel_p == policy:
        # Rolling back to the configuration already current is
        # idempotent; BASE is ignored and nothing is written.
        return {"op": 3, "status": 1, "selected": selected,
                "trials": trials, "config": pack}
    if base != v or v >= MAX_COST:
        fail(5)
    new_pack = {"v": v + 1, "t": sel_t, "p": sel_p,
                "h": history + [[v + 1, sel_t, sel_p]]}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 3, "status": 0, "selected": selected, "trials": trials,
            "config": new_pack}


def _config_replay_sim(pack, v, history, base, log):
    # Shared in-memory replay simulation for config ops 4 and 6. BASE
    # must be a version present in the version-zero continuous history
    # h: the first record's pre is BASE, every seq is pre + 1, and each
    # later pre is the previous seq. A record at seq <= v must equal
    # h[seq] = [seq, t, p] exactly (reused, s=0), and the first record
    # past v must be v+1, after which records append consecutively as
    # [seq, t, p] (s=1), never past MAX_COST. A bad shape or range, a
    # broken chain, a gap, or an h conflict fails with code 5. Nothing
    # is written: the caller decides what to do with the simulated pack.
    # Returns (applied, steps, new_pack); with no new records applied is
    # 0 and new_pack is the current pack. O(S) time and space with S the
    # total input/output size.
    if base > v:
        fail(5)
    new_history = [list(entry) for entry in history]
    steps = []
    applied = 0
    expected_pre = base
    next_new = v + 1
    for record in log:
        if not isinstance(record, list) or len(record) != 4:
            fail(5)
        seq, pre, rec_t, rec_p = record
        if type(seq) is not int or type(pre) is not int \
                or not 0 <= seq <= MAX_COST or not 0 <= pre <= MAX_COST:
            fail(5)
        if pre != expected_pre or seq != pre + 1:
            fail(5)
        _validate_topology(rec_t, metrics=True)
        if not _is_policy(rec_p):
            fail(5)
        if seq <= v:
            if history[seq] != [seq, rec_t, rec_p]:
                fail(5)
            steps.append([seq, pre, 0])
        else:
            if seq != next_new:
                fail(5)
            new_history.append([seq, rec_t, rec_p])
            next_new = seq + 1
            applied += 1
            steps.append([seq, pre, 1])
        expected_pre = seq
    if applied == 0:
        return 0, steps, pack
    new_pack = {"v": v + applied, "t": new_history[-1][1],
                "p": new_history[-1][2], "h": new_history}
    return applied, steps, new_pack


def _config_replay(pack_path, pack, v, history, base, log):
    # Replay a LOG of [seq, pre, t, p] records against the history
    # (config op 4). Validation and simulation are shared with the op 6
    # preview in _config_replay_sim; this wrapper performs the same
    # in-memory pass and, when it adds new records, replaces the pack
    # atomically once (status 0). No new records is status 1
    # (idempotent, no write).
    applied, steps, new_pack = _config_replay_sim(pack, v, history,
                                                  base, log)
    if applied == 0:
        return {"op": 4, "status": 1, "applied": 0, "steps": steps,
                "config": pack}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 4, "status": 0, "applied": applied, "steps": steps,
            "config": new_pack}


def _config_preview(pack, v, history, base, log):
    # Read-only replay preview (config op 6). Runs exactly the op 4
    # validation and in-memory simulation via _config_replay_sim but
    # never writes PACK, any other file, or a temp file: the returned
    # status/applied/steps/config are precisely what op 4 with the same
    # inputs would produce (its config's v,t,p,h byte-identical), so
    # repeated previews emit the same output while PACK stays untouched.
    # Status 0 when the LOG adds new versions, 1 when all are reused.
    applied, steps, new_pack = _config_replay_sim(pack, v, history,
                                                  base, log)
    if applied == 0:
        return {"op": 6, "status": 1, "applied": 0, "steps": steps,
                "config": pack}
    return {"op": 6, "status": 0, "applied": applied, "steps": steps,
            "config": new_pack}


def _config_state_diff(old_t, new_t, old_p, new_p):
    # Difference between two validated [topology, policy] pairs. Node
    # lists are sorted by Unicode code point; edge lists by their
    # (from, to) endpoint pair in code point order. Added/removed edges
    # carry [from, to, cost, up, bandwidth, latency]; a changed edge
    # carries [from, to, old, new] with old/new the [cost, up,
    # bandwidth, latency] vectors. The policy delta is the elementwise
    # new-minus-old six-integer array. O(S) with S the input size.
    old_nodes = set(old_t["nodes"])
    new_nodes = set(new_t["nodes"])
    n = [sorted(new_nodes - old_nodes), sorted(old_nodes - new_nodes)]
    old_links = {(link["from"], link["to"]): link
                 for link in old_t["links"]}
    new_links = {(link["from"], link["to"]): link
                 for link in new_t["links"]}

    def edge_row(link):
        return [link["from"], link["to"], link["cost"], link["up"],
                link["bandwidth"], link["latency"]]

    added = [edge_row(new_links[pair])
             for pair in sorted(new_links.keys() - old_links.keys())]
    removed = [edge_row(old_links[pair])
               for pair in sorted(old_links.keys() - new_links.keys())]
    changed = []
    for pair in sorted(old_links.keys() & new_links.keys()):
        old_vec = edge_row(old_links[pair])[2:]
        new_vec = edge_row(new_links[pair])[2:]
        if old_vec != new_vec:
            changed.append([pair[0], pair[1], old_vec, new_vec])
    p = [new - old for new, old in zip(new_p, old_p)]
    return n, [added, removed, changed], p


def _config_diff_audit(pack, v, history, base, log):
    # Read-only replay diff audit (config op 7). Runs exactly the op 4
    # validation and in-memory simulation via _config_replay_sim and,
    # like op 6, never writes PACK, any other file, or a temp file.
    # Each LOG-order step is [seq, pre, s, n, l, p]: s marks reuse (0)
    # or a new version (1), and n/l/p diff the pre version's [t, p]
    # against the record's [t, p]. final is [old_v, new_v, n, l, p]
    # diffing the original pack against the simulated result; with no
    # differences n/l are empty arrays and p is six zeros. Status 0
    # when the LOG adds new versions, 1 when all are reused.
    applied, sim_steps, new_pack = _config_replay_sim(pack, v, history,
                                                      base, log)
    sim_history = new_pack["h"]
    steps = []
    for record, sim_step in zip(log, sim_steps):
        seq, pre, s = sim_step
        old_t = sim_history[pre][1]
        old_p = sim_history[pre][2]
        n, l, p = _config_state_diff(old_t, record[2], old_p, record[3])
        steps.append([seq, pre, s, n, l, p])
    n, l, p = _config_state_diff(pack["t"], new_pack["t"],
                                 pack["p"], new_pack["p"])
    final = [v, new_pack["v"], n, l, p]
    return {"op": 7, "status": 0 if applied else 1, "applied": applied,
            "steps": steps, "final": final}


def _config_event_clock(pack_path, pack, v, topo, policy, history, mode,
                        base, event, new_t, new_p):
    # Event-clock configuration transaction (config op 8):
    # [8, m, b, e, t, p]. mode 0 previews in memory only — no file, temp
    # file, or other side effect; mode 1 commits via the same atomic
    # pack replace as the other config ops. A target [t, p] equal to the
    # current topology and policy is idempotent: status 1, b is ignored,
    # nothing is written, and old/new both stay at v. Otherwise b must
    # equal the current v and v must be below MAX_COST (else code 5);
    # the candidate appends [v+1, t, p] to the untruncated history as
    # version v+1. applied is true only for a mode-1 change commit; a
    # preview of the same change differs solely by mode and applied and
    # reports the same candidate config. diff is the [n, l, p] delta of
    # the current [t, p] against the target, in op 7's row structure,
    # code-point ordering, and six-integer policy delta. Committing the
    # same target twice adds no second version. O(S) time and space with
    # S the total input/output size.
    n, l, p_delta = _config_state_diff(topo, new_t, policy, new_p)
    diff = [n, l, p_delta]
    if new_t == topo and new_p == policy:
        return {"op": 8, "mode": mode, "status": 1, "event": event,
                "old": v, "new": v, "applied": False, "diff": diff,
                "config": pack}
    if base != v or v >= MAX_COST:
        fail(5)
    new_pack = {"v": v + 1, "t": new_t, "p": new_p,
                "h": history + [[v + 1, new_t, new_p]]}
    if mode == 1:
        _write_state_atomic(pack_path, new_pack)
        applied = True
    else:
        applied = False
    return {"op": 8, "mode": mode, "status": 0, "event": event,
            "old": v, "new": v + 1, "applied": applied, "diff": diff,
            "config": new_pack}


def _config_rollback_tx(pack_path, pack, v, topo, policy, history, mode,
                        base, event, source):
    # Event-clock rollback transaction (config op 9):
    # [9, m, b, e, r]. It follows op 8's contract exactly, except the
    # target [t, p] is the history entry h[r] (r must be a version present
    # in h) rather than an inline t/p. mode 0 previews in memory only — no
    # file, temp file, or other side effect; mode 1 commits via the same
    # atomic pack replace as the other config ops. A target equal to the
    # current topology and policy is idempotent: status 1, b is ignored,
    # nothing is written, and old/new both stay at v. Otherwise b must
    # equal the current v and v must be below MAX_COST (else code 5); the
    # candidate appends [v+1, t, p] to the untruncated history as version
    # v+1. applied is true only for a mode-1 change commit; a preview of
    # the same change differs solely by mode and applied and reports the
    # same candidate config. diff is the [n, l, p] delta of the current
    # [t, p] against h[r], in op 7's row structure, code-point ordering,
    # and six-integer policy delta. Repeatedly rolling back to the same
    # target adds no second version. O(S) time and space with S the total
    # input/output size.
    if source > v:
        fail(5)
    target = history[source]
    new_t, new_p = target[1], target[2]
    n, l, p_delta = _config_state_diff(topo, new_t, policy, new_p)
    diff = [n, l, p_delta]
    if new_t == topo and new_p == policy:
        return {"op": 9, "mode": mode, "status": 1, "event": event,
                "source": source, "old": v, "new": v, "applied": False,
                "diff": diff, "config": pack}
    if base != v or v >= MAX_COST:
        fail(5)
    new_pack = {"v": v + 1, "t": new_t, "p": new_p,
                "h": history + [[v + 1, new_t, new_p]]}
    if mode == 1:
        _write_state_atomic(pack_path, new_pack)
        applied = True
    else:
        applied = False
    return {"op": 9, "mode": mode, "status": 0, "event": event,
            "source": source, "old": v, "new": v + 1, "applied": applied,
            "diff": diff, "config": new_pack}


def _config_export_log(out_path, v, history, from_v, to_v):
    # Export the replay log for versions from_v+1..to_v (config op 5).
    # The interval must satisfy 0 <= from_v < to_v <= v. LOG is the
    # ascending records [i, i-1, h[i][1], h[i][2]] for i in
    # from_v+1..to_v — exactly the LOG that op 4 with BASE=from_v would
    # replay onto the pack truncated at from_v to rebuild the pack
    # truncated at to_v. PACK is never modified; OUT receives only the
    # LOG array in the canonical byte form via one atomic replace, or
    # nothing when OUT already holds those bytes (status 1). O(S) time
    # and space with S the total input/output size.
    if not from_v < to_v <= v:
        fail(5)
    log = [[i, i - 1, history[i][1], history[i][2]]
           for i in range(from_v + 1, to_v + 1)]
    try:
        with open(out_path, "rb") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = None
    except OSError:
        fail(3)
    if existing == _state_payload(log):
        # OUT already holds the canonical bytes: do not write.
        return {"op": 5, "status": 1, "from": from_v, "to": to_v,
                "count": to_v - from_v, "log": log}
    _write_state_atomic(out_path, log)
    return {"op": 5, "status": 0, "from": from_v, "to": to_v,
            "count": to_v - from_v, "log": log}


def _config_rollback_log(pack_path, pack, v, history, mode, base, log,
                         out_path):
    # Rollback log export/replay (config op 10): [10, m, B, L, O]. L is
    # a non-empty list of [e, r, o, n, a] items: e is a non-decreasing
    # event time, r the source version whose h[r] = [r, t, p] is the
    # rollback target, o the version the item is checked against, n the
    # next version, and a the commit flag. B must be a version present
    # in h; the first item's o is B and every later o is the previous
    # item's n when that item committed (a true) else the previous o;
    # r <= o always. A target equal to h[o]'s [t, p] is a no-op and
    # must carry a=false, n=o; any other target must carry n=o+1 with
    # a=false a precheck and a=true a commit. mode 0 (O a non-empty
    # path) only validates the references — a commit's h[n] must equal
    # the target — and writes L to OUT in the canonical byte form via
    # one atomic replace, or nothing when OUT already holds those bytes
    # (status 1); PACK is never touched. mode 1 (O null) validates the
    # same way, ignores the a=false items, and for each commit either
    # verifies h[n] against the target when n is already in h or
    # appends [n, t, p] consecutively from v+1, replacing PACK
    # atomically once; replaying the same L again only verifies, so
    # repeated replays are idempotent (status 1, no write). steps
    # echoes each item as [e, r, o, n, a, s] with s=1 for an appended
    # version else 0; applied counts the appends. O(S) time and space
    # with S the total input/output size.
    if base > v:
        fail(5)
    sim_history = [list(entry) for entry in history]
    steps = []
    applied = 0
    prev_e = None
    prev_o = None
    prev_n = None
    prev_a = None
    for item in log:
        e, r, o, n, a = item
        if prev_e is not None and e < prev_e:
            fail(5)
        expected_o = base if prev_o is None \
            else (prev_n if prev_a else prev_o)
        if o != expected_o or r > o:
            fail(5)
        target_t, target_p = sim_history[r][1], sim_history[r][2]
        if sim_history[o][1] == target_t and sim_history[o][2] == target_p:
            if a or n != o:
                fail(5)
        elif n != o + 1:
            fail(5)
        s = 0
        if a:
            # A commit: the target must already be h[n] (export always,
            # replay when n is a known version) or append consecutively
            # from v+1 (replay only).
            if n < len(sim_history):
                if sim_history[n][1] != target_t \
                        or sim_history[n][2] != target_p:
                    fail(5)
            elif mode == 1 and n == len(sim_history):
                sim_history.append([n, target_t, target_p])
                applied += 1
                s = 1
            else:
                fail(5)
        steps.append([e, r, o, n, a, s])
        prev_e, prev_o, prev_n, prev_a = e, o, n, a
    if mode == 0:
        try:
            with open(out_path, "rb") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = None
        except OSError:
            fail(3)
        if existing == _state_payload(log):
            # OUT already holds the canonical bytes: do not write.
            return {"op": 10, "status": 1, "applied": 0, "steps": steps,
                    "config": pack}
        _write_state_atomic(out_path, log)
        return {"op": 10, "status": 0, "applied": 0, "steps": steps,
                "config": pack}
    if applied == 0:
        # Every commit verified against h: idempotent, no write.
        return {"op": 10, "status": 1, "applied": 0, "steps": steps,
                "config": pack}
    new_pack = {"v": v + applied, "t": sim_history[-1][1],
                "p": sim_history[-1][2], "h": sim_history}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 10, "status": 0, "applied": applied, "steps": steps,
            "config": new_pack}


def _config_segmented_replay(history, base, segments, allow_append):
    # Shared single-pass core for config ops 11-13. Validate a non-empty
    # chain of [b, L, c] segments whose L items are [e, r, o, n, a]
    # against one simulated history seeded from PACK.h.
    #
    # Segment chain: the first b is base, every later b is the previous
    # segment's c, a segment's first item carries o=b, and c is the
    # chained o after its last item (n when that item committed else o).
    # Within and across segments e is non-decreasing and the o chain runs
    # first-item o=b, then the previous item's n when that item committed
    # else its o; r <= o always. When h[o] equals h[r] the item is a
    # no-op: a must be false and n=o; otherwise n=o+1.
    #
    # Commit policy: a commit's n that is already a simulated version must
    # equal h[r]'s target; a missing n is accepted only when appends are
    # allowed for that item's region and n is exactly the next simulated
    # version, in which case [n, t, p] is appended then and there.
    # allow_append is a bool for one global policy (op 11, and op 13's
    # mode) or a per-segment-index sequence (op 12: false for the
    # checkpoint prefix G[:I], true for the suffix); anything else is an
    # error. During this same pass the core also learns the longest
    # prefix whose commits were all versions native to the incoming
    # PACK.h (op 13): a commit n appended earlier in this pass, or an
    # actual append, ends the matched prefix at that segment.
    #
    # Returns (sim_history, applied, out_segments, matched) in one linear
    # walk: applied counts the appends, out_segments rows are
    # [b, c, steps] with steps the [e, r, o, n, a, s] items (s=1 for an
    # appended version else 0), and matched is the number of leading
    # segments referencing only PACK.h-native versions. O(S) time and
    # space with S the total input/output size.
    sim_history = [list(entry) for entry in history]
    history_len = len(sim_history)
    per_segment = isinstance(allow_append, (list, tuple))
    out_segments = []
    applied = 0
    prev_e = None
    chain_o = base
    matched = len(segments)
    for seg_index, (b, log, c) in enumerate(segments):
        if b != chain_o:
            fail(5)
        may_append = allow_append[seg_index] if per_segment \
            else allow_append
        steps = []
        prev_o = None
        prev_n = None
        prev_a = None
        seg_native_only = True
        for item in log:
            e, r, o, n, a = item
            if prev_e is not None and e < prev_e:
                fail(5)
            expected_o = b if prev_o is None \
                else (prev_n if prev_a else prev_o)
            if o != expected_o or r > o:
                fail(5)
            target_t, target_p = sim_history[r][1], sim_history[r][2]
            if sim_history[o][1] == target_t \
                    and sim_history[o][2] == target_p:
                if a or n != o:
                    fail(5)
            elif n != o + 1:
                fail(5)
            s = 0
            if a:
                # A commit: a known version must already equal the
                # target; a missing one may only append consecutively in
                # a region allowed to append. A known n that was itself
                # appended earlier in this pass does not count toward the
                # PACK.h-matched prefix (op 13).
                if n < len(sim_history):
                    if sim_history[n][1] != target_t \
                            or sim_history[n][2] != target_p:
                        fail(5)
                    if n >= history_len:
                        seg_native_only = False
                elif may_append and n == len(sim_history):
                    sim_history.append([n, target_t, target_p])
                    applied += 1
                    s = 1
                    seg_native_only = False
                else:
                    fail(5)
            steps.append([e, r, o, n, a, s])
            prev_e, prev_o, prev_n, prev_a = e, o, n, a
        end_o = prev_n if prev_a else prev_o
        if c != end_o:
            fail(5)
        chain_o = c
        if not seg_native_only and matched == len(segments):
            # First segment whose commits are not all already in PACK.h:
            # the longest matching prefix ends right before it.
            matched = seg_index
        out_segments.append([b, c, steps])
    return sim_history, applied, out_segments, matched


def _config_segmented_rollback_log(pack_path, pack, v, history, mode,
                                   base, segments, out_path):
    # Segmented rollback log export/replay (config op 11):
    # [11, m, B, G, O]. G is a non-empty list of [b, L, c] segments
    # whose L is a non-empty list of op-10 [e, r, o, n, a] items and
    # whose b/c are bounded non-boolean integers. The segments chain
    # like one flat op-10 log: the first segment's b is B, every later
    # b is the previous segment's c, each segment's first item carries
    # o=b, and c is the chained o after the segment's last item (its n
    # when that item committed, else its o); e is non-decreasing across
    # segment boundaries too. Every item follows op 10's per-item
    # checks (r <= o, the target-equality n/a rule, the commit
    # reference/append rule) against one shared simulated history.
    # mode 0 (O a non-empty path) only validates the references — a
    # commit's h[n] must equal the target — and writes G to OUT in the
    # canonical byte form via one atomic replace, or nothing when OUT
    # already holds those bytes (status 1); PACK is never touched.
    # mode 1 (O null) validates the same way, ignores the a=false
    # items, and for each commit either verifies h[n] against the
    # target when n is already in h or appends [n, t, p] consecutively
    # from v+1, replacing PACK atomically once after every segment
    # validated; replaying the same G again only verifies, so repeated
    # replays are idempotent (status 1, no write). segments echoes each
    # segment as [b, c, steps] with steps the op-10 [e, r, o, n, a, s]
    # items (s=1 for an appended version else 0); applied counts the
    # appends. O(S) time and space with S the total input/output size.
    if base > v:
        fail(5)
    sim_history, applied, out_segments, _matched = \
        _config_segmented_replay(history, base, segments,
                                 allow_append=(mode == 1))
    if mode == 0:
        try:
            with open(out_path, "rb") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = None
        except OSError:
            fail(3)
        if existing == _state_payload(segments):
            # OUT already holds the canonical bytes: do not write.
            return {"op": 11, "status": 1, "applied": 0,
                    "segments": out_segments, "config": pack}
        _write_state_atomic(out_path, segments)
        return {"op": 11, "status": 0, "applied": 0,
                "segments": out_segments, "config": pack}
    if applied == 0:
        # Every commit verified against h: idempotent, no write.
        return {"op": 11, "status": 1, "applied": 0,
                "segments": out_segments, "config": pack}
    new_pack = {"v": v + applied, "t": sim_history[-1][1],
                "p": sim_history[-1][2], "h": sim_history}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 11, "status": 0, "applied": applied,
            "segments": out_segments, "config": new_pack}


def _config_checkpoint(pack_path, pack, v, history, mode, base, segments,
                       index, ckpt_path):
    # Checkpointed segmented rollback log (config op 12):
    # [12, m, B, G, I, C]. B and G follow op 11 exactly; I is a
    # non-boolean integer in 0..len(G) splitting G into the checkpointed
    # prefix G[:I] and the remaining suffix G[I:]; C is a non-empty
    # checkpoint file path. The checkpoint is {"b": B, "i": I, "v": cv,
    # "d": digest} with keys in that order, where cv is B when I is 0
    # else the c of the I-th segment (1-based), and digest is the
    # lowercase hex SHA-256 of G[:I] in the canonical byte form with the
    # trailing LF removed. The whole of G is validated in memory against
    # one shared simulated history with op 11's per-item and
    # segment-chain checks, except that every prefix commit must
    # reference a version already present in PACK.h and match it (never
    # an append), while suffix commits follow op 11's replay rule
    # (verify a known version else append consecutively in memory).
    # mode 0 (generate) writes the checkpoint to C in the canonical byte
    # form via one atomic replace, or nothing when C already holds those
    # bytes (status 1); PACK is never touched and segments is [].
    # mode 1 (restore) reads C (read errors code 3; UTF-8/JSON syntax,
    # duplicate keys, and non-finite numbers code 4), requires its key
    # order, types, and b/i/v/d values to match the checkpoint
    # recomputed from B/I/G (else code 5), validates the prefix against
    # PACK.h the same way, then replays G[I:] like op 11's mode 1:
    # existing versions are verified, missing versions append
    # consecutively from v+1, and PACK is replaced atomically once when
    # anything appended; C is never written. Replaying the same restore
    # again only verifies, so repeated restores are idempotent (status
    # 1, no write). segments echoes the suffix segments as op-11
    # [b, c, steps] rows ([] for mode 0); applied counts the appended
    # versions (always 0 for mode 0). On any failure PACK and C keep
    # their original bytes. O(S) time and space with S the total
    # input/output size.
    if base > v:
        fail(5)
    if index == 0:
        ckpt_v = base
    else:
        ckpt_v = segments[index - 1][2]
    digest = hashlib.sha256(
        _state_payload(segments[:index])[:-1]).hexdigest()
    checkpoint = {"b": base, "i": index, "v": ckpt_v, "d": digest}
    if mode == 1:
        saved = _load_state(ckpt_path)
        if not isinstance(saved, dict) \
                or list(saved.keys()) != ["b", "i", "v", "d"]:
            fail(5)
        saved_b, saved_i, saved_v, saved_d = \
            saved["b"], saved["i"], saved["v"], saved["d"]
        if type(saved_b) is not int or type(saved_i) is not int \
                or type(saved_v) is not int \
                or not 0 <= saved_b <= MAX_COST \
                or not 0 <= saved_i <= MAX_COST \
                or not 0 <= saved_v <= MAX_COST \
                or type(saved_d) is not str:
            fail(5)
        if saved != checkpoint:
            # b/i/v or the digest conflicts with B/I/G[:I].
            fail(5)
    # The checkpoint prefix G[:I] may only verify versions already in
    # PACK.h (never an append); the suffix G[I:] follows op 11's replay
    # rule (verify a known version else append consecutively).
    allow_append = [False] * index \
        + [True] * (len(segments) - index)
    sim_history, applied, all_segments, _matched = \
        _config_segmented_replay(history, base, segments, allow_append)
    out_segments = all_segments[index:]
    if mode == 0:
        try:
            with open(ckpt_path, "rb") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = None
        except OSError:
            fail(3)
        if existing == _state_payload(checkpoint):
            # C already holds the canonical bytes: do not write.
            return {"op": 12, "mode": 0, "status": 1,
                    "checkpoint": checkpoint, "applied": 0,
                    "segments": [], "config": pack}
        _write_state_atomic(ckpt_path, checkpoint)
        return {"op": 12, "mode": 0, "status": 0,
                "checkpoint": checkpoint, "applied": 0,
                "segments": [], "config": pack}
    if applied == 0:
        # Every suffix commit verified against h: idempotent, no write.
        return {"op": 12, "mode": 1, "status": 1,
                "checkpoint": checkpoint, "applied": 0,
                "segments": out_segments, "config": pack}
    new_pack = {"v": v + applied, "t": sim_history[-1][1],
                "p": sim_history[-1][2], "h": sim_history}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 12, "mode": 1, "status": 0,
            "checkpoint": checkpoint, "applied": applied,
            "segments": out_segments, "config": new_pack}


def _config_multi_checkpoint(pack_path, pack, v, history, mode, base,
                             segments, ckpt_path):
    # Multi-checkpoint restore (config op 13): [13, m, B, G, C]. B and
    # G follow op 11 exactly and C is a non-empty manifest path. The
    # manifest is {"b": B, "points": points} with keys in that order and
    # one point [i, cv, d, prev] per i in 0..len(G): cv is B for i=0
    # else the c of segment i-1, d is the lowercase hex SHA-256 of
    # canonical G[:i] with the trailing LF removed, and prev is null for
    # i=0 else i-1. The point digests are hashed incrementally over the
    # growing canonical prefix, so building all points stays O(S).
    # mode 0 (generate) validates G exactly like op 11's export (every
    # commit references a version already present in PACK.h and matching
    # it) and writes the manifest to C via one atomic replace, or
    # nothing when C already holds those bytes (status 1); PACK is never
    # touched and segments is []. mode 1 (restore) reads C (read errors
    # code 3; UTF-8/JSON syntax, duplicate keys, and non-finite numbers
    # code 4), requires its key order, types, and b/points values to
    # match the manifest recomputed from B/G (else code 5), then
    # validates the whole G like op 11's mode 1 replay and selects the
    # largest i for which every G[:i] commit exists in PACK.h and
    # matches (never an append); G[i:] is replayed per op 11: existing
    # versions are verified and missing ones append consecutively from
    # v+1, replacing PACK atomically once when anything appends. C is
    # never written and a repeated restore only verifies, so restores
    # are idempotent (status 1, no write). selected is len(G) for mode
    # 0 and the selected i for mode 1; segments echoes the suffix
    # segments as op-11 [b, c, steps] rows ([] for mode 0); applied
    # counts the appended versions. On any failure PACK and C keep
    # their original bytes. O(S) time and space with S the total
    # input/output size.
    if base > v:
        fail(5)
    nseg = len(segments)
    point_v = [base]
    for _b, _log, seg_c in segments:
        point_v.append(seg_c)
    # Incremental hash of "[" + dumps(G[:i] elements joined by ","):
    # copying the hasher at each boundary yields the SHA-256 of
    # canonical G[:i] (closing "]" included, trailing LF excluded).
    hasher = hashlib.sha256(b"[")
    points = []
    for i in range(nseg + 1):
        prefix_hasher = hasher.copy()
        prefix_hasher.update(b"]")
        prev_i = None if i == 0 else i - 1
        points.append([i, point_v[i], prefix_hasher.hexdigest(), prev_i])
        if i < nseg:
            if i > 0:
                hasher.update(b",")
            hasher.update(json.dumps(segments[i], ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8"))
    manifest = {"b": base, "points": points}
    if mode == 1:
        saved = _load_state(ckpt_path)
        if not isinstance(saved, dict) \
                or list(saved.keys()) != ["b", "points"]:
            fail(5)
        saved_points = saved["points"]
        if type(saved["b"]) is not int or not 0 <= saved["b"] <= MAX_COST \
                or not isinstance(saved_points, list) \
                or len(saved_points) != nseg + 1:
            fail(5)
        for point in saved_points:
            if not isinstance(point, list) or len(point) != 4:
                fail(5)
            pi, pv, pd, pprev = point
            if type(pi) is not int or not 0 <= pi <= MAX_COST \
                    or type(pv) is not int or not 0 <= pv <= MAX_COST \
                    or type(pd) is not str:
                fail(5)
            if pprev is not None and (type(pprev) is not int
                                      or not 0 <= pprev <= MAX_COST):
                fail(5)
        if saved != manifest:
            # b/points conflict with the manifest recomputed from B/G.
            fail(5)
    # One replay pass validates the whole G like op 11 (appends only in
    # mode 1) and reports the longest prefix whose segments reference
    # only versions native to PACK.h; the first segment past it is the
    # restore point and G[selected:] is echoed/replayed.
    sim_history, applied, all_segments, selected = \
        _config_segmented_replay(history, base, segments,
                                 allow_append=(mode == 1))
    if mode == 0:
        try:
            with open(ckpt_path, "rb") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = None
        except OSError:
            fail(3)
        if existing == _state_payload(manifest):
            # C already holds the canonical bytes: do not write.
            return {"op": 13, "mode": 0, "status": 1,
                    "selected": nseg, "manifest": manifest,
                    "applied": 0, "segments": [], "config": pack}
        _write_state_atomic(ckpt_path, manifest)
        return {"op": 13, "mode": 0, "status": 0,
                "selected": nseg, "manifest": manifest,
                "applied": 0, "segments": [], "config": pack}
    out_segments = all_segments[selected:]
    if applied == 0:
        # Every suffix commit verified against h: idempotent, no write.
        return {"op": 13, "mode": 1, "status": 1,
                "selected": selected, "manifest": manifest,
                "applied": 0, "segments": out_segments, "config": pack}
    new_pack = {"v": v + applied, "t": sim_history[-1][1],
                "p": sim_history[-1][2], "h": sim_history}
    _write_state_atomic(pack_path, new_pack)
    return {"op": 13, "mode": 1, "status": 0,
            "selected": selected, "manifest": manifest,
            "applied": applied, "segments": out_segments,
            "config": new_pack}


def _validate_hotload_records(links, events, data, node_set, pair_set, a, b):
    # Stream validation matching slogate's data contract (the record
    # checks inside compute_convstat) without running the windowed gate:
    # apply the normalized events to the final up-graph in O(events),
    # then verify every [t, f, path] record in O(records). Every hotload
    # request validates its inputs before the idempotent/base/gate
    # decision, so a rollback stays O(H + J + P) with no gate compute.
    node_up = {}
    link_up = {(link["from"], link["to"]): link["up"] for link in links}
    for _t, kind, *rest in events:
        if kind == 0:
            node, up = rest
            node_up[node] = up
        else:
            u, v, up = rest
            link_up[(u, v)] = up
    previous_time = None
    seen_marks = set()
    for item in data:
        if not isinstance(item, list) or len(item) != 3:
            fail(5)
        t, f, path = item
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if not a <= t <= b:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        previous_time = t
        if type(f) is not str or not 1 <= len(f) <= 64:
            fail(5)
        try:
            f.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if (t, f) in seen_marks:
            fail(5)
        seen_marks.add((t, f))
        if not isinstance(path, list):
            fail(5)
        if path:
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
                if not node_up.get(node, True):
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for x, y in zip(path, path[1:]):
                if (x, y) not in pair_set:
                    fail(5)
                if not link_up[(x, y)]:
                    fail(5)


def _parse_pshift_flows_rules(links, node_set, raw_flows, raw_rules,
                                limit_text):
    # Shared FLOWS/RULES/LIMIT validation for pshift and pshiftcp,
    # matching pshift's exact per-item checks (code 5). RULES is a
    # policytx rule set; FLOWS is [id,s,d,b,p,c,path] with the given
    # path an up simple path in FILE (never required to satisfy
    # RULES), p/c the policytx query checks. LIMIT keeps its pshift
    # position, after the FLOWS/RULES shape checks. Returns the
    # validated flow tuples, rule tuples, edge pair set, and LIMIT.
    if not isinstance(raw_flows, list):
        fail(5)
    up_of = {}
    for link in links:
        up_of[(link["from"], link["to"])] = link["up"]
    pair_set = set(up_of)
    # RULES uses policytx's rule-set shape exactly.
    rules = _validate_policytx_rules(raw_rules, node_set, pair_set)
    flows = []
    seen_ids = set()
    for item in raw_flows:
        if not isinstance(item, list) or len(item) != 7:
            fail(5)
        rid, s, d, b, port, klass, flow_path = item
        if type(rid) is not str or not 1 <= len(rid) <= 64:
            fail(5)
        try:
            rid.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if rid in seen_ids:
            fail(5)
        seen_ids.add(rid)
        if (type(s) is not str or type(d) is not str
                or s not in node_set or d not in node_set or s == d):
            fail(5)
        if type(b) is not int or not 1 <= b <= MAX_COST:
            fail(5)
        if type(port) is not int or not 0 <= port <= 65535:
            fail(5)
        if type(klass) is not str or not 1 <= len(klass) <= 32:
            fail(5)
        try:
            klass.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if (not isinstance(flow_path, list) or not flow_path
                or flow_path[0] != s or flow_path[-1] != d):
            fail(5)
        for node in flow_path:
            if type(node) is not str or node not in node_set:
                fail(5)
        if len(set(flow_path)) != len(flow_path):
            fail(5)
        for a, q in zip(flow_path, flow_path[1:]):
            edge_pair = (a, q)
            if edge_pair not in up_of or not up_of[edge_pair]:
                fail(5)
        flows.append((rid, s, d, b, port, klass, flow_path))
    limit = _bounded_int_arg(limit_text)
    return flows, rules, pair_set, limit


def _parse_pshift_events(raw_events, node_set, pair_set, count=None):
    # Shared EVENTS validation for pshift and pshiftcp: a non-empty
    # array of flowshift's kinds 0..5 with kind 1 extended to
    # [t,1,id,s,d,b,p,c], plus [t,6,R] with R a policytx rule set.
    # t is non-decreasing; cross-event semantics are enforced during
    # the replay and are also code 5. pshiftcp M=0 passes count=I: the
    # whole array has already parsed as JSON, but only its first I
    # items are structurally validated and executed, so a malformed
    # or illegal remaining item never reaches the archive. pshift and
    # pshiftcp M=1 pass count=None and validate every item.
    if not isinstance(raw_events, list) or not raw_events:
        fail(5)

    def pshift_valid_id(value):
        if type(value) is not str or not 1 <= len(value) <= 64:
            return False
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return True

    checked = raw_events if count is None else raw_events[:count]
    events = []
    previous_time = None
    for item in checked:
        if not isinstance(item, list) or len(item) < 2:
            fail(5)
        t, kind = item[0], item[1]
        if type(t) is not int or not 0 <= t <= MAX_COST:
            fail(5)
        if previous_time is not None and t < previous_time:
            fail(5)
        if type(kind) is not int or kind not in (0, 1, 2, 3, 4, 5, 6):
            fail(5)
        if kind == 0:
            if len(item) != 5:
                fail(5)
            _, _, u, v, b = item
            if type(u) is not str or type(v) is not str \
                    or (u, v) not in pair_set:
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            events.append((0, t, u, v, b))
        elif kind == 1:
            if len(item) != 8:
                fail(5)
            _, _, nid, s, d, b, port, klass = item
            if not pshift_valid_id(nid):
                fail(5)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set
                    or s == d):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            if type(port) is not int or not 0 <= port <= 65535:
                fail(5)
            if type(klass) is not str or not 1 <= len(klass) <= 32:
                fail(5)
            try:
                klass.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            events.append((1, t, nid, s, d, b, port, klass))
        elif kind == 2:
            if len(item) != 3:
                fail(5)
            _, _, nid = item
            if not pshift_valid_id(nid):
                fail(5)
            events.append((2, t, nid))
        elif kind == 3:
            if len(item) != 4:
                fail(5)
            _, _, nid, b = item
            if not pshift_valid_id(nid):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            events.append((3, t, nid, b))
        elif kind == 4:
            if len(item) != 4:
                fail(5)
            _, _, n, bring_up = item
            if type(n) is not str or n not in node_set:
                fail(5)
            if type(bring_up) is not bool:
                fail(5)
            events.append((4, t, n, bring_up))
        elif kind == 5:
            if len(item) != 5:
                fail(5)
            _, _, u, v, bring_up = item
            if type(u) is not str or type(v) is not str \
                    or (u, v) not in pair_set:
                fail(5)
            if type(bring_up) is not bool:
                fail(5)
            events.append((5, t, u, v, bring_up))
        else:
            if len(item) != 3:
                fail(5)
            new_rules = _validate_policytx_rules(
                item[2], node_set, pair_set)
            events.append((6, t, new_rules))
        previous_time = t
    return events


def main():
    argv = sys.argv
    if len(argv) < 2:
        fail(2)
    if argv[1] == "route":
        if len(argv) != 4:
            fail(2)
        file_path, source = argv[2], argv[3]
        nodes, links, node_set = load_network(file_path)
        if source not in node_set:
            fail(5)
        result = compute_routes(nodes, links, source)
    elif argv[1] == "ecmp":
        if len(argv) != 5:
            fail(2)
        file_path, source, flow = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path)
        if not 1 <= len(flow) <= MAX_FLOW_LEN:
            fail(5)
        try:
            flow.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if source not in node_set:
            fail(5)
        result = compute_ecmp(nodes, links, source, flow)
    elif argv[1] == "metric":
        if len(argv) != 5:
            fail(2)
        file_path, source, order = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path, metrics=True)
        order_names = order.split(",")
        if (len(order_names) != 4
                or set(order_names) != {"hop", "cost", "bandwidth", "latency"}
                or len(set(order_names)) != 4):
            fail(5)
        if source not in node_set:
            fail(5)
        result = compute_metric(nodes, links, source, order_names)
    elif argv[1] == "wm":
        if len(argv) != 5:
            fail(2)
        file_path, source, weights_text = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            weights = json.loads(weights_text,
                                 parse_constant=_reject_constant,
                                 parse_float=_finite_float,
                                 object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if (not isinstance(weights, list) or len(weights) != 4
                or any(type(w) is not int or not 0 <= w <= MAX_COST
                       for w in weights)
                or all(w == 0 for w in weights)):
            fail(5)
        if source not in node_set:
            fail(5)
        result = compute_wm(nodes, links, source, weights)
    elif argv[1] == "wmecmp":
        if len(argv) != 6:
            fail(2)
        file_path, source, flow = argv[2], argv[3], argv[4]
        weights_text = argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            weights = json.loads(weights_text,
                                 parse_constant=_reject_constant,
                                 parse_float=_finite_float,
                                 object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if (not isinstance(weights, list) or len(weights) != 4
                or any(type(w) is not int or not 0 <= w <= MAX_COST
                       for w in weights)
                or all(w == 0 for w in weights)):
            fail(5)
        if not 1 <= len(flow) <= MAX_FLOW_LEN:
            fail(5)
        try:
            flow.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if source not in node_set:
            fail(5)
        result = compute_wmecmp(nodes, links, source, flow, weights)
    elif argv[1] == "protect":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        delay_text, events_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        if (not delay_text
                or any(c not in "0123456789" for c in delay_text)):
            fail(5)
        delay = int(delay_text)
        if delay > MAX_COST:
            fail(5)
        try:
            events = json.loads(events_text, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(events, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        previous_time = None
        for event in events:
            if (not isinstance(event, dict)
                    or list(event) != ["time", "from", "to", "up"]):
                fail(5)
            time = event["time"]
            frm = event["from"]
            to = event["to"]
            up = event["up"]
            if type(time) is not int or not 0 <= time <= MAX_COST:
                fail(5)
            if previous_time is not None and time < previous_time:
                fail(5)
            previous_time = time
            if (type(frm) is not str or type(to) is not str
                    or (frm, to) not in pair_set):
                fail(5)
            if type(up) is not bool:
                fail(5)
        result = compute_protect(nodes, links, source, destination,
                                 delay, events)
    elif argv[1] == "forward":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        limit_text, table_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, strict=True)
        if source not in node_set or destination not in node_set:
            fail(5)
        if (not limit_text
                or any(c not in "0123456789" for c in limit_text)):
            fail(5)
        # Strip leading zeros before int() so absurdly long digit strings
        # cannot trip Python's integer conversion digit limit.
        limit_digits = limit_text.lstrip("0") or "0"
        if len(limit_digits) > 10:
            fail(5)
        limit = int(limit_digits)
        if limit > MAX_COST:
            fail(5)
        try:
            table = json.loads(table_text, parse_constant=_reject_constant,
                               parse_float=_finite_float,
                               object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(table, dict) or set(table) != node_set:
            fail(5)
        for value in table.values():
            if (value is not None
                    and (type(value) is not str or value not in node_set)):
                fail(5)
        result = compute_forward(links, source, destination, limit, table)
    elif argv[1] == "queue":
        if len(argv) != 8:
            fail(2)
        file_path, frm, to = argv[2], argv[3], argv[4]
        cap_text, step_text, data_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, strict=True)
        if frm not in node_set or to not in node_set:
            fail(5)
        if not any(link["from"] == frm and link["to"] == to and link["up"]
                   for link in links):
            fail(5)
        cap = _bounded_int_arg(cap_text)
        if cap < 1:
            fail(5)
        step = _bounded_int_arg(step_text)
        if step < 1:
            fail(5)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        packets = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if (not isinstance(item, dict)
                    or set(item) != {"id", "time", "size"}):
                fail(5)
            pid = item["id"]
            time = item["time"]
            size = item["size"]
            if type(pid) is not str or pid == "" or pid in seen_ids:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            seen_ids.add(pid)
            if type(time) is not int or not 0 <= time <= MAX_COST:
                fail(5)
            if previous_time is not None and time < previous_time:
                fail(5)
            previous_time = time
            if type(size) is not int or not 1 <= size <= MAX_COST:
                fail(5)
            packets.append((pid, time, size))
        result = compute_queue(frm, to, cap, step, packets)
    elif argv[1] == "fragment":
        if len(argv) != 3:
            fail(2)
        data_text = argv[2]
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list) or len(data) != 4:
            fail(5)
        ident, ttl, mtus, hex_text = data
        if type(ident) is not str or not 1 <= len(ident) <= 64:
            fail(5)
        try:
            ident.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        if type(ttl) is not int or not 1 <= ttl <= MAX_COST:
            fail(5)
        if not isinstance(mtus, list) or len(mtus) == 0:
            fail(5)
        for mtu in mtus:
            if type(mtu) is not int or not 25 <= mtu <= MAX_COST:
                fail(5)
        if (type(hex_text) is not str or hex_text == ""
                or len(hex_text) % 2 != 0
                or any(ch not in "0123456789abcdef" for ch in hex_text)
                or len(hex_text) // 2 > MAX_COST):
            fail(5)
        payload = bytes.fromhex(hex_text)
        result = compute_fragment(ident, ttl, mtus, payload)
    elif argv[1] == "reassemble":
        if len(argv) != 3:
            fail(2)
        data_text = argv[2]
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list) or len(data) == 0:
            fail(5)
        pieces = []
        expected_offset = 0
        last_index = len(data) - 1
        for index, item in enumerate(data):
            if not isinstance(item, list) or len(item) != 4:
                fail(5)
            offset, more, hex_text, checksum = item
            if type(offset) is not int or not 0 <= offset <= MAX_COST:
                fail(5)
            if type(more) is not bool or more != (index != last_index):
                fail(5)
            if (type(hex_text) is not str or hex_text == ""
                    or len(hex_text) % 2 != 0
                    or any(ch not in "0123456789abcdef" for ch in hex_text)
                    or len(hex_text) // 2 > MAX_COST):
                fail(5)
            if (type(checksum) is not str or len(checksum) != 64
                    or any(ch not in "0123456789abcdef"
                           for ch in checksum)):
                fail(5)
            blob = bytes.fromhex(hex_text)
            if hashlib.sha256(blob).hexdigest() != checksum:
                fail(5)
            # Contiguity check: rejects reordering, overlap, and gaps.
            if offset != expected_offset:
                fail(5)
            expected_offset += len(blob)
            if expected_offset > MAX_COST:
                fail(5)
            pieces.append(blob)
        payload = b"".join(pieces)
        result = {"length": len(payload), "payload": payload.hex()}
    elif argv[1] == "rewrite":
        if len(argv) != 4:
            fail(2)
        r_text, d_text = argv[2], argv[3]
        try:
            rules = json.loads(r_text, parse_constant=_reject_constant,
                               parse_float=_finite_float,
                               object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        try:
            packets = json.loads(d_text, parse_constant=_reject_constant,
                                 parse_float=_finite_float,
                                 object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(rules, list):
            fail(5)
        parsed_rules = []
        for rule in rules:
            if not isinstance(rule, list) or len(rule) != 11:
                fail(5)
            n, ms, md, a, b, mc, ns, nd, nport, nc, k = rule
            if type(n) is not int or not 0 <= n <= MAX_COST:
                fail(5)
            if type(a) is not int or type(b) is not int \
                    or not 0 <= a <= 65535 or not 0 <= b <= 65535 \
                    or a > b:
                fail(5)
            for value in (ms, md, mc, ns, nd, nc):
                if value is not None:
                    if type(value) is not str \
                            or not 1 <= len(value) <= 64:
                        fail(5)
                    try:
                        value.encode("utf-8")
                    except UnicodeEncodeError:
                        fail(5)
            if nport is not None and (type(nport) is not int
                                      or not 0 <= nport <= 65535):
                fail(5)
            if type(k) is not int or not 0 <= k <= MAX_COST:
                fail(5)
            parsed_rules.append(rule)
        if not isinstance(packets, list):
            fail(5)
        parsed_packets = []
        seen_ids = set()
        for item in packets:
            if not isinstance(item, list) or len(item) != 8:
                fail(5)
            ident, s, d, p, c, ttl, hex_text, digest = item
            for value in (ident, s, d, c):
                if type(value) is not str:
                    fail(5)
                try:
                    value.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
            if ident in seen_ids:
                fail(5)
            seen_ids.add(ident)
            if type(p) is not int or not 0 <= p <= 65535:
                fail(5)
            if type(ttl) is not int or not 1 <= ttl <= MAX_COST:
                fail(5)
            if (type(hex_text) is not str
                    or len(hex_text) % 2 != 0
                    or any(ch not in "0123456789abcdef" for ch in hex_text)
                    or len(hex_text) // 2 > MAX_COST):
                fail(5)
            if (type(digest) is not str or len(digest) != 64
                    or any(ch not in "0123456789abcdef"
                           for ch in digest)):
                fail(5)
            if _rewrite_digest(s, d, p, c, ttl, hex_text) != digest:
                fail(5)
            parsed_packets.append(item)
        result = compute_rewrite(parsed_rules, parsed_packets)
    elif argv[1] == "reorder":
        if len(argv) != 8:
            fail(2)
        file_path, frm, to = argv[2], argv[3], argv[4]
        base_text, window_text, data_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, strict=True)
        if frm not in node_set or to not in node_set:
            fail(5)
        if not any(link["from"] == frm and link["to"] == to and link["up"]
                   for link in links):
            fail(5)
        base = _bounded_int_arg(base_text)
        window = _bounded_int_arg(window_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        packets = []
        seen_ids = set()
        previous_time = None
        for seq, item in enumerate(data):
            if not isinstance(item, list) or len(item) != 3:
                fail(5)
            pid, time, jitter = item
            if type(pid) is not str or pid == "" or pid in seen_ids:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            seen_ids.add(pid)
            if type(time) is not int or not 0 <= time <= MAX_COST:
                fail(5)
            if previous_time is not None and time < previous_time:
                fail(5)
            previous_time = time
            if (type(jitter) is not int
                    or not -MAX_COST <= jitter <= MAX_COST):
                fail(5)
            delay = base + jitter
            arrival = time + delay
            if delay < 0 or arrival > MAX_COST:
                fail(5)
            packets.append((pid, seq, arrival))
        result = compute_reorder(frm, to, base, window, packets)
    elif argv[1] == "converge":
        if len(argv) != 8:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        delay_text, run_text, events_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, strict=True)
        if source not in node_set or destination not in node_set:
            fail(5)
        delay = _bounded_int_arg(delay_text)
        run = _bounded_int_arg(run_text)
        try:
            events = json.loads(events_text, parse_constant=_reject_constant,
                                parse_float=_finite_float,
                                object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(events, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        previous_time = None
        for event in events:
            if (not isinstance(event, dict)
                    or list(event) != ["time", "from", "to", "up"]):
                fail(5)
            time = event["time"]
            frm = event["from"]
            to = event["to"]
            up = event["up"]
            if type(time) is not int or not 0 <= time <= MAX_COST:
                fail(5)
            if previous_time is not None and time < previous_time:
                fail(5)
            previous_time = time
            if (type(frm) is not str or type(to) is not str
                    or (frm, to) not in pair_set):
                fail(5)
            if type(up) is not bool:
                fail(5)
        result = compute_converge(nodes, links, source, destination,
                                  delay, run, events)
    elif argv[1] == "policy":
        if len(argv) != 8:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        port_text, klass, rules_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, strict=True)
        if source not in node_set or destination not in node_set:
            fail(5)
        port = _bounded_int_arg(port_text)
        if port > 65535:
            fail(5)
        if not 1 <= len(klass) <= 32:
            fail(5)
        try:
            klass.encode("utf-8")
        except UnicodeEncodeError:
            fail(5)
        try:
            rule_items = json.loads(rules_text,
                                    parse_constant=_reject_constant,
                                    parse_float=_finite_float,
                                    object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(rule_items, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        rules = []
        for item in rule_items:
            if not isinstance(item, list) or len(item) != 6:
                fail(5)
            n, s, d, p, c, path = item
            if type(n) is not int or not 0 <= n <= MAX_COST:
                fail(5)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set):
                fail(5)
            if p is not None and (type(p) is not int
                                  or not 0 <= p <= 65535):
                fail(5)
            if c is not None:
                if type(c) is not str or not 1 <= len(c) <= 32:
                    fail(5)
                try:
                    c.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
            if (not isinstance(path, list) or not path
                    or path[0] != s or path[-1] != d):
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for a, b in zip(path, path[1:]):
                if (a, b) not in pair_set:
                    fail(5)
            rules.append((n, s, d, p, c, path))
        result = compute_policy(nodes, links, source, destination,
                                port, klass, rules)
    elif argv[1] == "policytx":
        if len(argv) != 5:
            fail(2)
        file_path, state_path, op_text = argv[2], argv[3], argv[4]
        # Read/decode FILE and STATE first (read errors code 3, strict
        # JSON errors code 4), then the inline OP, then shape checks.
        nodes, links, node_set = load_network(file_path, strict=True)
        raw_state = _load_state(state_path)
        try:
            op = json.loads(op_text, parse_constant=_reject_constant,
                            parse_float=_finite_float,
                            object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(op, list) or len(op) == 0 \
                or type(op[0]) is not int:
            fail(5)
        kind = op[0]
        pair_set = {(link["from"], link["to"]) for link in links}
        if kind == 0:
            # [0, BASE, R]: validate the OP shape and STATE, then R and
            # BASE. R equal to the current rules is idempotent (no base
            # check, no write); otherwise BASE must equal the current v
            # and v must be below MAX_COST, and [v+1, R] is appended to
            # the untruncated history while STATE atomically becomes
            # {v+1, R, h} (a legacy {v, r} STATE is read-only and is
            # only migrated by a successful commit). A failed write
            # leaves STATE's bytes untouched.
            if len(op) != 3 or type(op[1]) is not int:
                fail(5)
            base = op[1]
            v, rules, history = _validate_policytx_state(
                raw_state, node_set, pair_set)
            new_rules = _validate_policytx_rules(op[2], node_set,
                                                 pair_set)
            if new_rules == rules:
                # Loading the rule set already current is idempotent:
                # BASE is ignored (even when out of range), STATE is
                # not rewritten.
                status = 1
                version = v
            else:
                if (type(base) is not int or not 0 <= base <= MAX_COST
                        or base != v or v >= MAX_COST):
                    fail(5)
                history = history + [[v + 1, new_rules]]
                new_state = {
                    "v": v + 1,
                    "r": [list(rule) for rule in new_rules],
                    "h": [[hv, [list(rule) for rule in hr]]
                          for hv, hr in history],
                }
                _write_state_atomic(state_path, new_state)
                status = 0
                version = v + 1
            result = {"op": 0, "status": status, "version": version,
                      "rules": [list(rule) for rule in new_rules],
                      "result": None}
        elif kind == 1:
            # [1, s, d, p, c]: read-only policy lookup over the current
            # rules; nothing is written. s/d/p/c follow the policy
            # subcommand's S/D/P/C checks (c is a required non-empty
            # string; only a rule's c may be null to act as wildcard).
            if len(op) != 5:
                fail(5)
            _, source, destination, port, klass = op
            if (type(source) is not str or type(destination) is not str
                    or source not in node_set
                    or destination not in node_set):
                fail(5)
            if type(port) is not int or not 0 <= port <= 65535:
                fail(5)
            if type(klass) is not str or not 1 <= len(klass) <= 32:
                fail(5)
            try:
                klass.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            v, rules, _ = _validate_policytx_state(
                raw_state, node_set, pair_set)
            query = compute_policytx(nodes, links, source, destination,
                                     port, klass, rules)
            result = {"op": 1, "status": 2, "version": v,
                      "rules": [list(rule) for rule in rules],
                      "result": query}
        elif kind == 2:
            # [2, BASE, T]: roll back to the rule set recorded at
            # version T in the history h. T must be present in h; when
            # that rule set equals the current one the op is idempotent
            # (status 1, BASE ignored, no write). Otherwise BASE must
            # equal v with v < MAX_COST, [v+1, target] is appended to
            # the untruncated history and STATE atomically becomes
            # {v+1, target, h} (status 0). result is [T, old v, new v].
            if len(op) != 3 or type(op[1]) is not int:
                fail(5)
            base = op[1]
            target = op[2]
            v, rules, history = _validate_policytx_state(
                raw_state, node_set, pair_set)
            if type(target) is not int:
                fail(5)
            target_rules = None
            for hv, hr in history:
                if hv == target:
                    target_rules = hr
                    break
            if target_rules is None:
                fail(5)
            if target_rules == rules:
                # Reviving the rule set already current is idempotent:
                # BASE is ignored (even when out of range), STATE is
                # not rewritten.
                status = 1
                version = v
                emit_rules = rules
            else:
                if (not 0 <= base <= MAX_COST
                        or base != v or v >= MAX_COST):
                    fail(5)
                history = history + [[v + 1, target_rules]]
                new_state = {
                    "v": v + 1,
                    "r": [list(rule) for rule in target_rules],
                    "h": [[hv, [list(rule) for rule in hr]]
                          for hv, hr in history],
                }
                _write_state_atomic(state_path, new_state)
                status = 0
                version = v + 1
                emit_rules = target_rules
            result = {"op": 2, "status": status, "version": version,
                      "rules": [list(rule) for rule in emit_rules],
                      "result": [target, v, version]}
        elif kind == 3:
            # [3, T]: read-only history audit. T is a non-boolean
            # integer in 0..MAX_COST that must be a version recorded in
            # h; a legacy {v, r} STATE's history only contains v, so it
            # can only audit that version. Nothing is written; result
            # is [T, target rule set].
            if len(op) != 2:
                fail(5)
            target = op[1]
            if type(target) is not int or type(target) is bool \
                    or not 0 <= target <= MAX_COST:
                fail(5)
            v, rules, history = _validate_policytx_state(
                raw_state, node_set, pair_set)
            target_rules = None
            for hv, hr in history:
                if hv == target:
                    target_rules = hr
                    break
            if target_rules is None:
                fail(5)
            result = {"op": 3, "status": 2, "version": v,
                      "rules": [list(rule) for rule in rules],
                      "result": [target,
                                 [list(rule) for rule in target_rules]]}
        elif kind == 4:
            # [4, OUT]: export the normalized history to OUT. The export
            # object has key order v, r, h with h keeping the version and
            # rule-set order (a legacy {v, r} STATE is exported as
            # h=[[v, r]]); OUT receives the canonical compact UTF-8 bytes
            # with a single trailing LF and is directly usable as a
            # policytx STATE. OUT must be a non-empty path distinct from
            # FILE and STATE; identical bytes rewrite nothing (status 1),
            # otherwise one atomic replace writes them (status 0). STATE
            # and FILE are never modified.
            if len(op) != 2 or type(op[1]) is not str or len(op[1]) == 0:
                fail(5)
            out_path = op[1]
            v, rules, history = _validate_policytx_state(
                raw_state, node_set, pair_set)
            export = _policytx_export_object(v, rules, history)
            payload = _state_payload(export)
            status = _write_distinct_atomic(
                out_path, [file_path, state_path], payload)
            result = {"op": 4, "status": status, "version": v,
                      "rules": [list(rule) for rule in rules],
                      "result": export}
        else:
            fail(5)
    elif argv[1] == "policyreplay":
        if len(argv) != 7:
            fail(2)
        pack_path, state_path = argv[2], argv[3]
        tv_text, pv_text, data_text = argv[4], argv[5], argv[6]
        # Read-only replay of a pack topology version against a
        # policytx rule-set version. Read/decode PACK and STATE first
        # (read errors code 3, strict JSON errors code 4), then the
        # inline DATA, then all shape/range checks (code 5).
        raw_pack = _load_state(pack_path)
        raw_state = _load_state(state_path)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        tv = _bounded_int_arg(tv_text)
        pv = _bounded_int_arg(pv_text)
        _pack_v, _pack_t, _pack_policy, pack_history = \
            _validate_config_pack(raw_pack)
        if tv > _pack_v:
            # The pack history is continuous over 0..v, so tv > v is
            # the only way TV can be absent from its h.
            fail(5)
        _state_v, state_history = _policytx_state_shape(raw_state)
        selected_rules_raw = None
        for hv, hr in state_history:
            if hv == pv:
                selected_rules_raw = hr
                break
        if selected_rules_raw is None:
            fail(5)
        selected_t = None
        for entry in pack_history:
            if entry[0] == tv:
                selected_t = entry[1]
                break
        nodes, links, node_set = _validate_topology(selected_t,
                                                    metrics=True)
        pair_set = {(link["from"], link["to"]) for link in links}
        # The selected rule set must be legal for the selected topology:
        # every s/d and path node names one of its nodes and every path
        # edge one of its links.
        rules = _validate_policytx_rules(selected_rules_raw, node_set,
                                         pair_set)
        if not isinstance(data, list):
            fail(5)
        # Validate and answer each item in one pass, keeping DATA's order
        # (duplicates included). A failure lands before the shared output
        # tail, so stdout stays empty; only the ordered results survive.
        # Per-query scratch (the rule priority order, link maps, and the
        # Dijkstra tables) is released each iteration, so beyond the
        # parsed input and the emitted results the working memory stays
        # O(V^2 + E + L).
        results = []
        for item in data:
            # Each DATA item is exactly [s, d, p, c]; items may repeat
            # and keep their order, and the array may be empty. s/d may
            # name the same node.
            if not isinstance(item, list) or len(item) != 4:
                fail(5)
            source, destination, port, klass = item
            if (type(source) is not str or type(destination) is not str
                    or source not in node_set
                    or destination not in node_set):
                fail(5)
            if type(port) is not int or not 0 <= port <= 65535:
                fail(5)
            if type(klass) is not str or not 1 <= len(klass) <= 32:
                fail(5)
            try:
                klass.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            # Matching follows policytx exactly: ascending n with ties in
            # array order, endpoint/port-interval/class match, rules whose
            # path holds a down edge are skipped, and with no match the
            # route lowest-cost path is the fallback.
            rule, cost, path = compute_policytx(
                nodes, links, source, destination, port, klass, rules)
            results.append([source, destination, port, klass,
                            rule, cost, path])
        result = {"topologyVersion": tv, "policyVersion": pv,
                  "results": results}
    elif argv[1] == "reserve":
        if len(argv) != 4:
            fail(2)
        file_path, data_text = argv[2], argv[3]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        requests = []
        seen_ids = set()
        for item in data:
            if not isinstance(item, list) or len(item) != 4:
                fail(5)
            rid, s, d, b = item
            if type(rid) is not str or not 1 <= len(rid) <= 64:
                fail(5)
            try:
                rid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if rid in seen_ids:
                fail(5)
            seen_ids.add(rid)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set or s == d):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            requests.append((rid, s, d, b))
        result = compute_reserve(nodes, links, requests)
    elif argv[1] == "rebalance":
        if len(argv) != 5:
            fail(2)
        file_path, data_text, limit_text = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        up_of = {}
        for link in links:
            up_of[(link["from"], link["to"])] = link["up"]
        demands = []
        seen_ids = set()
        for item in data:
            if not isinstance(item, list) or len(item) != 5:
                fail(5)
            rid, s, d, b, path = item
            if type(rid) is not str or not 1 <= len(rid) <= 64:
                fail(5)
            try:
                rid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if rid in seen_ids:
                fail(5)
            seen_ids.add(rid)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set or s == d):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            if (not isinstance(path, list) or not path
                    or path[0] != s or path[-1] != d):
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for a, c in zip(path, path[1:]):
                pair = (a, c)
                if pair not in up_of or not up_of[pair]:
                    fail(5)
            demands.append((rid, s, d, b, path))
        limit = _bounded_int_arg(limit_text)
        result = compute_rebalance(nodes, links, demands, limit)
    elif argv[1] == "loadshift":
        if len(argv) != 6:
            fail(2)
        file_path, limit_text, flows_text, events_text = \
            argv[2], argv[3], argv[4], argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            raw_flows = json.loads(
                flows_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        # FLOWS uses rebalance's DATA shape exactly: [id,s,d,b,path]
        # items with unique ids and up simple paths.
        if not isinstance(raw_flows, list):
            fail(5)
        up_of = {}
        for link in links:
            up_of[(link["from"], link["to"])] = link["up"]
        flows = []
        seen_ids = set()
        for item in raw_flows:
            if not isinstance(item, list) or len(item) != 5:
                fail(5)
            rid, s, d, b, path = item
            if type(rid) is not str or not 1 <= len(rid) <= 64:
                fail(5)
            try:
                rid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if rid in seen_ids:
                fail(5)
            seen_ids.add(rid)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set or s == d):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            if (not isinstance(path, list) or not path
                    or path[0] != s or path[-1] != d):
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for a, c in zip(path, path[1:]):
                pair = (a, c)
                if pair not in up_of or not up_of[pair]:
                    fail(5)
            flows.append((rid, s, d, b, path))
        limit = _bounded_int_arg(limit_text)
        # EVENTS is a non-empty array of [t,u,v,b]: t non-decreasing in
        # 0..MAX_COST, b in 1..MAX_COST, both non-boolean integers; the
        # edge u->v must exist in FILE; the same edge may not repeat at
        # the same time. Syntax failures are code 4, every shape or value
        # failure here is code 5.
        if not isinstance(raw_events, list) or not raw_events:
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        events = []
        previous_time = None
        seen_at_time = set()
        for item in raw_events:
            if not isinstance(item, list) or len(item) != 4:
                fail(5)
            t, u, v, b = item
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            if type(u) is not str or type(v) is not str \
                    or (u, v) not in pair_set:
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            if t != previous_time:
                seen_at_time = set()
            if (u, v) in seen_at_time:
                fail(5)
            seen_at_time.add((u, v))
            previous_time = t
            events.append((t, u, v, b))
        result = compute_loadshift(nodes, links, flows, limit, events)
    elif argv[1] == "flowshift":
        if len(argv) != 6:
            fail(2)
        file_path, limit_text, flows_text, events_text = \
            argv[2], argv[3], argv[4], argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            raw_flows = json.loads(
                flows_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        # FLOWS uses rebalance/loadshift's DATA shape exactly:
        # [id,s,d,b,path] items with unique ids and up simple paths.
        if not isinstance(raw_flows, list):
            fail(5)
        up_of = {}
        for link in links:
            up_of[(link["from"], link["to"])] = link["up"]
        flows = []
        seen_ids = set()
        for item in raw_flows:
            if not isinstance(item, list) or len(item) != 5:
                fail(5)
            rid, s, d, b, path = item
            if type(rid) is not str or not 1 <= len(rid) <= 64:
                fail(5)
            try:
                rid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if rid in seen_ids:
                fail(5)
            seen_ids.add(rid)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set or s == d):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            if (not isinstance(path, list) or not path
                    or path[0] != s or path[-1] != d):
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for a, c in zip(path, path[1:]):
                pair = (a, c)
                if pair not in up_of or not up_of[pair]:
                    fail(5)
            flows.append((rid, s, d, b, path))
        limit = _bounded_int_arg(limit_text)
        # EVENTS is a non-empty array whose items are
        # [t,0,u,v,b], [t,1,id,s,d,b], [t,2,id], [t,3,id,b],
        # [t,4,n,up], or [t,5,u,v,up]: t is a non-boolean integer in
        # 0..MAX_COST and non-decreasing, equal t keeps input order, b
        # is a non-boolean integer in 1..MAX_COST, u->v must name an
        # edge in FILE, n a node in FILE, up must be a JSON boolean, and
        # id/s/d are validated as in reserve/loadshift (id 1..64
        # codepoints, s/d existing distinct nodes). Cross-event id
        # semantics (re-addition conflicts, changes of absent ids) are
        # enforced during the replay and are also code 5. Syntax
        # failures are code 4, every shape or value failure here is 5.
        if not isinstance(raw_events, list) or not raw_events:
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}

        def valid_id(value):
            if type(value) is not str or not 1 <= len(value) <= 64:
                return False
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                return False
            return True

        events = []
        previous_time = None
        for item in raw_events:
            if not isinstance(item, list) or len(item) < 2:
                fail(5)
            t, kind = item[0], item[1]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            if type(kind) is not int or kind not in (0, 1, 2, 3, 4, 5):
                fail(5)
            if kind == 0:
                if len(item) != 5:
                    fail(5)
                _, _, u, v, b = item
                if type(u) is not str or type(v) is not str \
                        or (u, v) not in pair_set:
                    fail(5)
                if type(b) is not int or not 1 <= b <= MAX_COST:
                    fail(5)
                events.append((0, t, u, v, b))
            elif kind == 1:
                if len(item) != 6:
                    fail(5)
                _, _, nid, s, d, b = item
                if not valid_id(nid):
                    fail(5)
                if (type(s) is not str or type(d) is not str
                        or s not in node_set or d not in node_set
                        or s == d):
                    fail(5)
                if type(b) is not int or not 1 <= b <= MAX_COST:
                    fail(5)
                events.append((1, t, nid, s, d, b))
            elif kind == 2:
                if len(item) != 3:
                    fail(5)
                _, _, nid = item
                if not valid_id(nid):
                    fail(5)
                events.append((2, t, nid))
            elif kind == 3:
                if len(item) != 4:
                    fail(5)
                _, _, nid, b = item
                if not valid_id(nid):
                    fail(5)
                if type(b) is not int or not 1 <= b <= MAX_COST:
                    fail(5)
                events.append((3, t, nid, b))
            elif kind == 4:
                if len(item) != 4:
                    fail(5)
                _, _, n, bring_up = item
                if type(n) is not str or n not in node_set:
                    fail(5)
                if type(bring_up) is not bool:
                    fail(5)
                events.append((4, t, n, bring_up))
            else:
                if len(item) != 5:
                    fail(5)
                _, _, u, v, bring_up = item
                if type(u) is not str or type(v) is not str \
                        or (u, v) not in pair_set:
                    fail(5)
                if type(bring_up) is not bool:
                    fail(5)
                events.append((5, t, u, v, bring_up))
            previous_time = t
        result = compute_flowshift(nodes, links, flows, limit, events)
    elif argv[1] == "pshift":
        if len(argv) != 7:
            fail(2)
        file_path, limit_text, flows_text, rules_text, events_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            raw_flows = json.loads(
                flows_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            raw_rules = json.loads(
                rules_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        flows, rules, pair_set, limit = _parse_pshift_flows_rules(
            links, node_set, raw_flows, raw_rules, limit_text)
        events = _parse_pshift_events(raw_events, node_set, pair_set)
        result = compute_pshift(nodes, links, flows, limit, rules, events)
    elif argv[1] == "pshiftcp":
        if len(argv) != 10:
            fail(2)
        # Public order: FILE LIMIT FLOWS RULES I M STATE EVENTS.
        file_path, limit_text, flows_text, rules_text, cut_text, \
            mode_text, state_path, events_text = (
                argv[2], argv[3], argv[4], argv[5], argv[6],
                argv[7], argv[8], argv[9])
        # An empty STATE path or one with an embedded NUL can never
        # name a file: illegal argument (code 5), not the read/write
        # error (code 3) Python would otherwise raise.
        if state_path == "" or "\x00" in state_path:
            fail(5)
        # I is a non-boolean decimal integer; M is 0 or 1. Their
        # textual/range errors are code 5. I's upper bound is checked
        # once the EVENTS array is parsed.
        cut = _bounded_int_arg(cut_text)
        mode = _bounded_int_arg(mode_text)
        if mode > 1:
            fail(5)
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except OSError:
            fail(3)
        # M=1 reads STATE before the inline JSON is parsed (the same
        # precedence compoundcp uses): a STATE read/UTF-8 error (code
        # 3) or STATE JSON error (code 4) then wins over the inline
        # arguments. M=0 never reads STATE as input.
        if mode == 1:
            raw_state = _load_state(state_path)
        try:
            raw_flows = json.loads(
                flows_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            raw_rules = json.loads(
                rules_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            # M=0 still parses the whole EVENTS argument as JSON: a
            # syntax error is code 4. Only structural/semantic
            # validation is limited to the first I items below.
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        flows, rules, pair_set, limit = _parse_pshift_flows_rules(
            links, node_set, raw_flows, raw_rules, limit_text)
        if not isinstance(raw_events, list) or not raw_events:
            # The top-level array shape is part of the EVENTS JSON
            # contract both modes need (M=0 needs its length and
            # prefix).
            fail(5)
        if cut > len(raw_events):
            fail(5)
        if mode == 0:
            # Validate and execute only the first I events; the
            # remaining items' structure or semantics are irrelevant
            # to the archive and must not affect it.
            events = _parse_pshift_events(raw_events, node_set,
                                          pair_set, count=cut)
            engine = _PShiftEngine(nodes, links, flows, limit, rules)
            engine.run(events)
            checkpoint = _pshiftcp_state(
                engine, cut, limit, raw_flows, raw_rules, raw_events,
                file_bytes)
            payload = _state_payload(checkpoint)
            # The atomic write happens only after the prefix run has
            # fully succeeded; a failure leaves stdout empty and
            # STATE's bytes untouched. Replace is skipped when STATE
            # already holds exactly these bytes.
            try:
                with open(state_path, "rb") as f:
                    current = f.read()
            except FileNotFoundError:
                current = None
            except OSError:
                fail(3)
            if current != payload:
                _write_state_atomic(state_path, checkpoint)
            # stdout is byte-for-byte the archived STATE.
            result = checkpoint
        else:
            # Read-only resume: validate and execute every event. The
            # checkpoint must match this invocation exactly (key
            # order, digest, and every field recomputed by replaying
            # the prefix), then the remaining events continue from
            # that prefix state, producing the full pshift output
            # byte for byte. STATE is never written.
            events = _parse_pshift_events(raw_events, node_set, pair_set)
            prefix = _PShiftEngine(nodes, links, flows, limit, rules)
            prefix.run(events[:cut])
            _validate_pshiftcp_state(
                raw_state, prefix, cut, limit, raw_flows, raw_rules,
                raw_events, file_bytes)
            prefix.run(events[cut:])
            result = prefix.result()
    elif argv[1] == "retune":
        if len(argv) != 5:
            fail(2)
        file_path, limit_text, data_text = argv[2], argv[3], argv[4]
        nodes, links, node_set = load_network(file_path, metrics=True,
                                              strict=True)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if (not isinstance(data, list) or len(data) != 2
                or not isinstance(data[0], list)
                or not isinstance(data[1], list)):
            fail(5)
        c_items, g_items = data[0], data[1]
        if not g_items:
            # G must be non-empty.
            fail(5)
        up_of = {}
        for link in links:
            up_of[(link["from"], link["to"])] = link["up"]
        current = []
        current_ids = set()
        for item in c_items:
            if not isinstance(item, list) or len(item) != 5:
                fail(5)
            rid, s, d, b, path = item
            if type(rid) is not str or not 1 <= len(rid) <= 64:
                fail(5)
            try:
                rid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if rid in current_ids:
                fail(5)
            current_ids.add(rid)
            if (type(s) is not str or type(d) is not str
                    or s not in node_set or d not in node_set or s == d):
                fail(5)
            if type(b) is not int or not 1 <= b <= MAX_COST:
                fail(5)
            if (not isinstance(path, list) or not path
                    or path[0] != s or path[-1] != d):
                fail(5)
            for node in path:
                if type(node) is not str or node not in node_set:
                    fail(5)
            if len(set(path)) != len(path):
                fail(5)
            for a, c in zip(path, path[1:]):
                pair = (a, c)
                if pair not in up_of or not up_of[pair]:
                    fail(5)
            current.append((rid, s, d, b, path))
        changes = []
        seen_changes = set()
        for item in g_items:
            if not isinstance(item, list) or not 2 <= len(item) <= 5:
                fail(5)
            if type(item[0]) is not int or item[0] not in (0, 1):
                fail(5)
            if item[0] == 0:
                if len(item) != 2:
                    fail(5)
                rid = item[1]
                if type(rid) is not str or not 1 <= len(rid) <= 64:
                    fail(5)
                try:
                    rid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if rid in seen_changes or rid not in current_ids:
                    # G ids are unique and every deletion must hit C.
                    fail(5)
                seen_changes.add(rid)
                changes.append((0, rid))
            else:
                if len(item) != 5:
                    fail(5)
                rid, s, d, b = item[1], item[2], item[3], item[4]
                if type(rid) is not str or not 1 <= len(rid) <= 64:
                    fail(5)
                try:
                    rid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if rid in seen_changes or rid in current_ids:
                    # G ids are unique and a new id must not be in C.
                    fail(5)
                seen_changes.add(rid)
                if (type(s) is not str or type(d) is not str
                        or s not in node_set or d not in node_set
                        or s == d):
                    fail(5)
                if type(b) is not int or not 1 <= b <= MAX_COST:
                    fail(5)
                changes.append((1, rid, s, d, b))
        limit = _bounded_int_arg(limit_text)
        result = compute_retune(nodes, links, current, changes, limit)
    elif argv[1] == "quality":
        if len(argv) != 6:
            fail(2)
        file_path, a_text, b_text, data_text = \
            argv[2], argv[3], argv[4], argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        items = []
        seen_ids = {}  # id -> (f, t, d, path) of its first occurrence
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 5:
                fail(5)
            pid, f, t, d, path = item
            if type(pid) is not str or not 1 <= len(pid) <= 64:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if type(f) is not str or not 1 <= len(f) <= 64:
                fail(5)
            try:
                f.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if d is not None and (type(d) is not int
                                  or not 0 <= d <= MAX_COST):
                fail(5)
            if not isinstance(path, list):
                fail(5)
            if d is None:
                # A lost packet carries no path at all.
                if path:
                    fail(5)
            else:
                # A delivered packet's path is a non-empty simple node
                # array walking up directed edges.
                if not path:
                    fail(5)
                for node in path:
                    if type(node) is not str or node not in node_set:
                        fail(5)
                if len(set(path)) != len(path):
                    fail(5)
                for x, y in zip(path, path[1:]):
                    if (x, y) not in up_pairs:
                        fail(5)
            signature = (f, t, d, path)
            if pid in seen_ids:
                # A repeated id is dropped when the whole item matches;
                # the same id on a different item is an error.
                if seen_ids[pid] != signature:
                    fail(5)
                continue
            seen_ids[pid] = signature
            items.append((pid, f, t, d, path))
        result = compute_quality(a, b, items)
    elif argv[1] == "audit":
        if len(argv) != 6:
            fail(2)
        file_path, a_text, b_text, data_text = \
            argv[2], argv[3], argv[4], argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        # Edges only need to exist in the topology, up or down: the data
        # is a record of paths already taken.
        pair_set = {(link["from"], link["to"]) for link in links}
        items = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 6:
                fail(5)
            pid, f, t, s, d, path = item
            if type(pid) is not str or not 1 <= len(pid) <= 64:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if pid in seen_ids:
                fail(5)
            seen_ids.add(pid)
            if type(f) is not str or not 1 <= len(f) <= 64:
                fail(5)
            try:
                f.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(s) is not int or s not in (0, 1, 2):
                fail(5)
            if s == 2:
                # A no-route loss carries no delay and no path at all.
                if d is not None or path != []:
                    fail(5)
            else:
                if type(d) is not int or not 0 <= d <= MAX_TIME:
                    fail(5)
                # A non-empty simple node array walking directed edges
                # (length >= 2 for s=1, so a last edge exists).
                if not isinstance(path, list) or not path:
                    fail(5)
                if s == 1 and len(path) < 2:
                    fail(5)
                for node in path:
                    if type(node) is not str or node not in node_set:
                        fail(5)
                if len(set(path)) != len(path):
                    fail(5)
                for x, y in zip(path, path[1:]):
                    if (x, y) not in pair_set:
                        fail(5)
            items.append((pid, f, t, s, d, path))
        result = compute_audit(links, a, b, items)
    elif argv[1] == "drill":
        if len(argv) != 7:
            fail(2)
        file_path, a_text, b_text, events_text, data_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        # A link event may target only an edge that is up in FILE; a link
        # already down can neither open a failure nor be flipped back.
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        events = []
        previous_time = None
        for event in raw_events:
            if not isinstance(event, list) or len(event) not in (4, 5):
                fail(5)
            t = event[0]
            kind = event[1]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if not a <= t <= b:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(kind) is not int or kind not in (0, 1):
                fail(5)
            if kind == 0:
                if len(event) != 4:
                    fail(5)
                _, _, node, up = event
                if type(node) is not str or node not in node_set:
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                events.append((t, 0, node, up))
            else:
                if len(event) != 5:
                    fail(5)
                _, _, u, v, up = event
                if (type(u) is not str or type(v) is not str
                        or (u, v) not in up_pairs):
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                events.append((t, 1, u, v, up))
        # Records reuse the audit schema exactly: edges only need to exist
        # in the topology, up or down, since the data is a record of paths
        # already taken.
        pair_set = {(link["from"], link["to"]) for link in links}
        items = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 6:
                fail(5)
            pid, f, t, s, d, path = item
            if type(pid) is not str or not 1 <= len(pid) <= 64:
                fail(5)
            try:
                pid.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if pid in seen_ids:
                fail(5)
            seen_ids.add(pid)
            if type(f) is not str or not 1 <= len(f) <= 64:
                fail(5)
            try:
                f.encode("utf-8")
            except UnicodeEncodeError:
                fail(5)
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(s) is not int or s not in (0, 1, 2):
                fail(5)
            if s == 2:
                # A no-route loss carries no delay and no path at all.
                if d is not None or path != []:
                    fail(5)
            else:
                if type(d) is not int or not 0 <= d <= MAX_TIME:
                    fail(5)
                # A non-empty simple node array walking directed edges
                # (length >= 2 for s=1, so a last edge exists).
                if not isinstance(path, list) or not path:
                    fail(5)
                if s == 1 and len(path) < 2:
                    fail(5)
                for node in path:
                    if type(node) is not str or node not in node_set:
                        fail(5)
                if len(set(path)) != len(path):
                    fail(5)
                for x, y in zip(path, path[1:]):
                    if (x, y) not in pair_set:
                        fail(5)
            items.append((pid, f, t, s, d, path))
        result = compute_drill(links, a, b, events, items)
    elif argv[1] == "multidrill":
        if len(argv) != 7:
            fail(2)
        file_path, a_text, b_text, events_text, data_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        items = _parse_drill_items(data, node_set, pair_set)
        result = compute_multidrill(links, a, b, events, items)
    elif argv[1] == "convstat":
        if len(argv) != 7:
            fail(2)
        file_path, a_text, b_text, events_text, data_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_convstat(links, node_set, pair_set, a, b,
                                  events, data)
    elif argv[1] == "slosum":
        if len(argv) != 8:
            fail(2)
        file_path, a_text, b_text, width_text, events_text, data_text = \
            argv[2], argv[3], argv[4], argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        width = _bounded_int_arg(width_text)
        if width < 1:
            fail(5)
        try:
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_slosum(links, node_set, pair_set, a, b, width,
                                events, data)
    elif argv[1] == "sloeval":
        if len(argv) != 9:
            fail(2)
        file_path, a_text, b_text, width_text, policy_text, events_text, \
            data_text = (argv[2], argv[3], argv[4], argv[5], argv[6],
                         argv[7], argv[8])
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        width = _bounded_int_arg(width_text)
        if width < 1:
            fail(5)
        try:
            policy = json.loads(policy_text, parse_constant=_reject_constant,
                                parse_float=_finite_float,
                                object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        # POLICY is [u, o, d, f, s, g], six non-boolean integers in
        # [0, MAX_COST].
        if not isinstance(policy, list) or len(policy) != 6:
            fail(5)
        for value in policy:
            if type(value) is not int or not 0 <= value <= MAX_COST:
                fail(5)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_sloeval(links, node_set, pair_set, a, b, width,
                                 policy, events, data)
    elif argv[1] == "slocmp":
        if len(argv) != 10:
            fail(2)
        file_path, a_text, b_text, width_text, old_text, new_text, \
            events_text, data_text = (argv[2], argv[3], argv[4], argv[5],
                                      argv[6], argv[7], argv[8], argv[9])
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        width = _bounded_int_arg(width_text)
        if width < 1:
            fail(5)
        try:
            old = json.loads(old_text, parse_constant=_reject_constant,
                             parse_float=_finite_float,
                             object_pairs_hook=_object_no_dup)
            new = json.loads(new_text, parse_constant=_reject_constant,
                             parse_float=_finite_float,
                             object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        # OLD and NEW each follow sloeval's POLICY contract: [u, o, d, f,
        # s, g], six non-boolean integers in [0, MAX_COST].
        for policy in (old, new):
            if not isinstance(policy, list) or len(policy) != 6:
                fail(5)
            for value in policy:
                if type(value) is not int or not 0 <= value <= MAX_COST:
                    fail(5)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_slocmp(links, node_set, pair_set, a, b, width,
                                old, new, events, data)
    elif argv[1] == "slogate":
        if len(argv) != 10:
            fail(2)
        file_path, a_text, b_text, width_text, cur_text, new_text, \
            events_text, data_text = (argv[2], argv[3], argv[4], argv[5],
                                      argv[6], argv[7], argv[8], argv[9])
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        width = _bounded_int_arg(width_text)
        if width < 1:
            fail(5)
        try:
            cur = json.loads(cur_text, parse_constant=_reject_constant,
                             parse_float=_finite_float,
                             object_pairs_hook=_object_no_dup)
            new = json.loads(new_text, parse_constant=_reject_constant,
                             parse_float=_finite_float,
                             object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        # CUR and NEW each follow sloeval's POLICY contract: [u, o, d, f,
        # s, g], six non-boolean integers in [0, MAX_COST].
        for policy in (cur, new):
            if not isinstance(policy, list) or len(policy) != 6:
                fail(5)
            for value in policy:
                if type(value) is not int or not 0 <= value <= MAX_COST:
                    fail(5)
        if not isinstance(raw_events, list) or not isinstance(data, list):
            fail(5)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        result = compute_slogate(links, node_set, pair_set, a, b, width,
                                 cur, new, events, data)
    elif argv[1] == "replay":
        if len(argv) != 6:
            fail(2)
        file_path, a_text, b_text, data_text = \
            argv[2], argv[3], argv[4], argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        if a > b:
            fail(5)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        events = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) < 2:
                fail(5)
            t = item[0]
            kind = item[1]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(kind) is not int or kind not in (0, 1):
                fail(5)
            if kind == 0:
                if len(item) != 5:
                    fail(5)
                _, _, u, v, up = item
                if (type(u) is not str or type(v) is not str
                        or (u, v) not in pair_set):
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                events.append((0, t, u, v, up))
            else:
                if len(item) != 6:
                    fail(5)
                _, _, pid, f, s, d = item
                if type(pid) is not str or not 1 <= len(pid) <= 64:
                    fail(5)
                try:
                    pid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if pid in seen_ids:
                    fail(5)
                seen_ids.add(pid)
                if type(f) is not str or not 1 <= len(f) <= 64:
                    fail(5)
                try:
                    f.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if (type(s) is not str or type(d) is not str
                        or s not in node_set or d not in node_set):
                    fail(5)
                events.append((1, t, pid, f, s, d))
        result = compute_replay(nodes, links, a, b, events)
    elif argv[1] == "nfail":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, data_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        items = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) not in (2, 3):
                fail(5)
            t = item[0]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if len(item) == 3:
                _, n, up = item
                if type(n) is not str or n not in node_set:
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                items.append((t, n, up))
            else:
                _, pid = item
                if type(pid) is not str or not 1 <= len(pid) <= 64:
                    fail(5)
                try:
                    pid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if pid in seen_ids:
                    fail(5)
                seen_ids.add(pid)
                items.append((t, pid))
        result = compute_nfail(nodes, links, source, destination,
                               wait, items)
    elif argv[1] == "lfail":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, data_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        items = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) not in (2, 4):
                fail(5)
            t = item[0]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if len(item) == 4:
                _, u, v, up = item
                if (type(u) is not str or type(v) is not str
                        or (u, v) not in pair_set):
                    fail(5)
                if type(up) is not bool:
                    fail(5)
                items.append((t, u, v, up))
            else:
                _, pid = item
                if type(pid) is not str or not 1 <= len(pid) <= 64:
                    fail(5)
                try:
                    pid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if pid in seen_ids:
                    fail(5)
                seen_ids.add(pid)
                items.append((t, pid))
        result = compute_lfail(nodes, links, source, destination,
                               wait, items)
    elif argv[1] == "lrepair":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, data_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        items = []
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 4:
                fail(5)
            t, u, v, up = item
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if (type(u) is not str or type(v) is not str
                    or (u, v) not in pair_set):
                fail(5)
            if type(up) is not bool:
                fail(5)
            items.append((t, u, v, up))
        result = compute_lrepair(nodes, links, source, destination,
                                 wait, items)
    elif argv[1] == "nrepair":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, data_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        items = []
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 3:
                fail(5)
            t, n, up = item
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(n) is not str or n not in node_set:
                fail(5)
            if type(up) is not bool:
                fail(5)
            items.append((t, n, up))
        result = compute_nrepair(nodes, links, source, destination,
                                 wait, items)
    elif argv[1] == "fault":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, data_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list) or not data:
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        batches = []
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) != 2:
                fail(5)
            t, changes = item
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t <= previous_time:
                fail(5)
            previous_time = t
            if not isinstance(changes, list) or not changes:
                fail(5)
            seen_nodes = set()
            seen_pairs = set()
            batch = []
            for change in changes:
                if not isinstance(change, list) or len(change) not in (3, 4):
                    fail(5)
                kind = change[0]
                if type(kind) is not int or kind not in (0, 1):
                    fail(5)
                if kind == 0:
                    if len(change) != 3:
                        fail(5)
                    _, node, up = change
                    if type(node) is not str or node not in node_set:
                        fail(5)
                    if type(up) is not bool:
                        fail(5)
                    if node in seen_nodes:
                        fail(5)
                    seen_nodes.add(node)
                    batch.append((0, node, up))
                else:
                    if len(change) != 4:
                        fail(5)
                    _, u, v, up = change
                    if (type(u) is not str or type(v) is not str
                            or (u, v) not in pair_set):
                        fail(5)
                    if type(up) is not bool:
                        fail(5)
                    if (u, v) in seen_pairs:
                        fail(5)
                    seen_pairs.add((u, v))
                    batch.append((1, u, v, up))
            batches.append((t, batch))
        result = compute_fault(nodes, links, source, destination,
                               wait, batches)
    elif argv[1] == "impair":
        if len(argv) != 6:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        data_text = argv[5]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(data, list):
            fail(5)
        pair_set = {(link["from"], link["to"]) for link in links}
        latency_of = {(link["from"], link["to"]): link["latency"]
                      for link in links}
        items = []
        seen_ids = set()
        previous_time = None
        for item in data:
            if not isinstance(item, list) or len(item) < 2:
                fail(5)
            t = item[0]
            kind = item[1]
            if type(t) is not int or not 0 <= t <= MAX_COST:
                fail(5)
            if previous_time is not None and t < previous_time:
                fail(5)
            previous_time = t
            if type(kind) is not int or kind not in (0, 1):
                fail(5)
            if kind == 0:
                if len(item) != 6:
                    fail(5)
                _, _, u, v, n, j = item
                if (type(u) is not str or type(v) is not str
                        or (u, v) not in pair_set):
                    fail(5)
                if type(n) is not int or not 0 <= n <= MAX_COST:
                    fail(5)
                if (type(j) is not int
                        or not 0 <= latency_of[(u, v)] + j <= MAX_COST):
                    fail(5)
                items.append((0, t, u, v, n, j))
            else:
                if len(item) != 3:
                    fail(5)
                _, _, pid = item
                if type(pid) is not str or not 1 <= len(pid) <= 64:
                    fail(5)
                try:
                    pid.encode("utf-8")
                except UnicodeEncodeError:
                    fail(5)
                if pid in seen_ids:
                    fail(5)
                seen_ids.add(pid)
                items.append((1, t, pid))
        result = compute_impair(nodes, links, source, destination, items)
    elif argv[1] == "compound":
        if len(argv) != 7:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, data_text = argv[5], argv[6]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        pair_set = {(link["from"], link["to"]) for link in links}
        latency_of = {(link["from"], link["to"]): link["latency"]
                      for link in links}
        items = _parse_compound_items(data, node_set, pair_set,
                                      latency_of)
        result = compute_compound(nodes, links, source, destination,
                                  wait, items)
    elif argv[1] == "compoundcp":
        if len(argv) != 10:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, at_text, m_text = argv[5], argv[6], argv[7]
        state_path, data_text = argv[8], argv[9]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        at = _bounded_int_arg(at_text)
        mode = _bounded_int_arg(m_text)
        if mode > 1:
            fail(5)
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except OSError:
            fail(3)
        if mode == 1:
            raw_state = _load_state(state_path)
        try:
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        pair_set = {(link["from"], link["to"]) for link in links}
        latency_of = {(link["from"], link["to"]): link["latency"]
                      for link in links}
        if mode == 0:
            # M=0 accepts only items with t < AT and runs the clock up
            # to (not including) AT, keeping a timer due at or after AT
            # pending in the checkpoint; DATA may be empty, in which
            # case the checkpoint is the initial state.
            items = _parse_compound_items(data, node_set, pair_set,
                                          latency_of, allow_empty=True,
                                          max_t=at - 1)
            _, checkpoint = _compound_run(nodes, links, source,
                                          destination, wait, items,
                                          cutoff=at)
            result = _compoundcp_state(file_bytes, nodes, links, source,
                                       destination, wait, at, checkpoint)
            payload = _state_payload(result)
            # Atomic replace, skipped when the file already holds
            # exactly these bytes.
            try:
                with open(state_path, "rb") as f:
                    current = f.read()
            except OSError:
                current = None
            if current != payload:
                _write_state_atomic(state_path, result)
        else:
            # M=1 accepts only items with t >= AT, resumes from the
            # checkpoint (read-only), and reports the merged run; items
            # at AT run before a timer expiring at AT, and an empty
            # DATA still advances and settles the pending timer.
            engine_state = _validate_compoundcp_state(
                raw_state, file_bytes, nodes, links, node_set, source,
                destination, wait, at)
            seen_ids = {entry[0] for entry in raw_state["p"]}
            items = _parse_compound_items(data, node_set, pair_set,
                                          latency_of, allow_empty=True,
                                          min_t=at, seen_ids=seen_ids)
            result, _ = _compound_run(nodes, links, source, destination,
                                      wait, items, state=engine_state)
    elif argv[1] == "branch":
        if len(argv) != 8:
            fail(2)
        file_path, source, destination = argv[2], argv[3], argv[4]
        wait_text, db_path, op_text = argv[5], argv[6], argv[7]
        nodes, links, node_set = load_network(file_path, metrics=True)
        if (source not in node_set or destination not in node_set
                or source == destination):
            fail(5)
        wait = _bounded_int_arg(wait_text)
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except OSError:
            fail(3)
        # Read/decode the DB before the inline OP (read errors code 3,
        # strict JSON errors code 4); a missing DB bootstraps empty only
        # for OP0, every other op gets code 3 and never touches it.
        db, db_raw = _load_branch_db(db_path)
        try:
            op = json.loads(op_text, parse_constant=_reject_constant,
                            parse_float=_finite_float,
                            object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(op, list) or len(op) == 0 \
                or type(op[0]) is not int:
            fail(5)
        kind = op[0]
        if kind == 0:
            # [0, name, parent, AT, DATA]: commit a named checkpoint.
            if len(op) != 5:
                fail(5)
            _, name, parent, at, data = op
            _check_branch_name(name)
            if parent is not None and type(parent) is not str:
                fail(5)
            if type(at) is not int or not 0 <= at <= MAX_COST:
                fail(5)
        elif kind == 1:
            # [1, name, DATA]: read-only resume from a named checkpoint.
            if len(op) != 3:
                fail(5)
            _, name, data = op
            if type(name) is not str:
                fail(5)
        elif kind in (2, 3):
            # [2, name]: delete a leaf branch. [3, name]: delete the
            # subtree rooted at name. Both are idempotent when the name
            # is absent from an existing, fully validated DB.
            if len(op) != 2:
                fail(5)
            _, name = op
            _check_branch_name(name)
        else:
            fail(5)
        if db is None:
            if kind != 0:
                fail(3)
            db = {"p": []}
        pair_set = {(link["from"], link["to"]) for link in links}
        latency_of = {(link["from"], link["to"]): link["latency"]
                      for link in links}
        records, by_name = _validate_branch_db(
            db, file_bytes, nodes, links, node_set, source, destination,
            wait)
        if kind == 0:
            existing = by_name.get(name)
            if existing is not None:
                # A same-name commit is idempotent only when parent, AT,
                # and DATA all match the stored entry.
                if (parent != existing[1] or at != existing[3]["b"][3]
                        or data != existing[2]):
                    fail(5)
            else:
                if parent is None:
                    items = _parse_compound_items(
                        data, node_set, pair_set, latency_of,
                        allow_empty=True, max_t=at - 1)
                    _, checkpoint = _compound_run(
                        nodes, links, source, destination, wait, items,
                        cutoff=at)
                else:
                    if parent not in by_name:
                        fail(5)
                    parent_record = by_name[parent]
                    parent_at = parent_record[3]["b"][3]
                    if at < parent_at:
                        fail(5)
                    seen_ids = {pkt[0] for pkt in parent_record[3]["p"]}
                    items = _parse_compound_items(
                        data, node_set, pair_set, latency_of,
                        allow_empty=True, min_t=parent_at, max_t=at - 1,
                        seen_ids=seen_ids)
                    _, checkpoint = _compound_run(
                        nodes, links, source, destination, wait, items,
                        state=_copy_engine_state(parent_record[4]),
                        cutoff=at)
                new_state = _compoundcp_state(file_bytes, nodes, links,
                                              source, destination, wait,
                                              at, checkpoint)
                db["p"].append([name, parent, data, new_state])
            payload = _state_payload(db)
            # Atomic replace, skipped when the file already holds
            # exactly these bytes.
            if db_raw != payload:
                _write_state_atomic(db_path, db)
            result = db
        elif kind == 1:
            # OP 1 leaves the DB untouched; the merged run resumes from
            # the named checkpoint, so its s,d,e,p,x match one compound
            # run over the whole chain's DATA plus this DATA.
            record = by_name.get(name)
            if record is None:
                fail(5)
            at = record[3]["b"][3]
            seen_ids = {pkt[0] for pkt in record[3]["p"]}
            items = _parse_compound_items(
                data, node_set, pair_set, latency_of, allow_empty=True,
                min_t=at, seen_ids=seen_ids)
            result, _ = _compound_run(
                nodes, links, source, destination, wait, items,
                state=_copy_engine_state(record[4]))
        else:
            # OP 2 deletes a single leaf: any child still parented to
            # name is code 5. OP 3 deletes name and every descendant.
            # A missing target is idempotent: no rewrite at all.
            if name not in by_name:
                result = db
            else:
                removed = {name}
                if kind == 2:
                    if any(record[1] == name for record in records):
                        fail(5)
                else:
                    # Collect descendants in linear time via a
                    # parent-to-children adjacency and a DFS stack.
                    children = {}
                    for record in records:
                        rparent = record[1]
                        if rparent is not None:
                            children.setdefault(rparent, []).append(
                                record[0])
                    stack = [name]
                    while stack:
                        cur = stack.pop()
                        for child in children.get(cur, ()):
                            if child not in removed:
                                removed.add(child)
                                stack.append(child)
                db["p"] = [[record[0], record[1], record[2], record[3]]
                           for record in records
                           if record[0] not in removed]
                # Exactly one atomic replace for the actual deletion.
                _write_state_atomic(db_path, db)
                result = db
    elif argv[1] == "hotload":
        if len(argv) != 11:
            fail(2)
        file_path, state_path, a_text, b_text, width_text, base_text, \
            op_text, events_text, data_text = (argv[2], argv[3], argv[4],
                                               argv[5], argv[6], argv[7],
                                               argv[8], argv[9], argv[10])
        # Inputs are validated up front, following slogate's order: both
        # files are read/decoded first (read errors code 3, strict JSON
        # errors code 4), then the integer args, then the inline JSON.
        nodes, links, node_set = load_network(file_path, metrics=True)
        raw_state = _load_state(state_path)
        a = _bounded_int_arg(a_text)
        b = _bounded_int_arg(b_text)
        width = _bounded_int_arg(width_text)
        base = _bounded_int_arg(base_text)
        if a > b or width < 1:
            fail(5)
        try:
            op = json.loads(op_text, parse_constant=_reject_constant,
                            parse_float=_finite_float,
                            object_pairs_hook=_object_no_dup)
            raw_events = json.loads(
                events_text, parse_constant=_reject_constant,
                parse_float=_finite_float, object_pairs_hook=_object_no_dup)
            data = json.loads(data_text, parse_constant=_reject_constant,
                              parse_float=_finite_float,
                              object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(op, list) or len(op) != 2 or type(op[0]) is not int:
            fail(5)
        kind = op[0]
        if kind not in (0, 1):
            fail(5)
        v, current_policy, history = _validate_hotload_state(raw_state)
        up_pairs = {(link["from"], link["to"]) for link in links
                    if link["up"]}
        pair_set = {(link["from"], link["to"]) for link in links}
        events = _parse_drill_events(raw_events, up_pairs, node_set, a, b)
        if not isinstance(data, list):
            fail(5)
        _validate_hotload_records(links, events, data, node_set, pair_set,
                                  a, b)

        if kind == 0:
            target_policy = op[1]
            if not _is_policy(target_policy):
                fail(5)
            if target_policy == current_policy:
                # Loading the policy already current is idempotent: no
                # base check, no gate, no new version, no STATE write.
                result = {"s": 2, "v": v, "p": current_policy, "why": []}
            else:
                if base != v:
                    fail(5)
                new_v = v + 1
                if new_v > MAX_COST:
                    fail(5)
                # Reuse the slogate gate with CUR the current policy and
                # NEW the candidate; a rejection writes nothing.
                gate = compute_slogate(links, node_set, pair_set, a, b,
                                       width, current_policy, target_policy,
                                       events, data)
                if gate["why"]:
                    result = {"s": 1, "v": v, "p": current_policy,
                              "why": gate["why"]}
                else:
                    new_history = history + [[new_v, target_policy]]
                    new_state = {"v": new_v, "p": target_policy,
                                 "h": new_history}
                    _write_state_atomic(state_path, new_state)
                    result = {"s": 0, "v": new_v, "p": target_policy,
                              "why": []}
        else:
            target = op[1]
            if type(target) is not int or not 0 <= target <= MAX_COST:
                fail(5)
            if target == v:
                # Rolling back to the current version is idempotent.
                result = {"s": 2, "v": v, "p": current_policy, "why": []}
            else:
                if base != v:
                    fail(5)
                if target >= len(history) or history[target][0] != target:
                    fail(5)
                new_v = v + 1
                if new_v > MAX_COST:
                    fail(5)
                target_policy = history[target][1]
                new_history = history + [[new_v, target_policy]]
                new_state = {"v": new_v, "p": target_policy,
                             "h": new_history}
                _write_state_atomic(state_path, new_state)
                result = {"s": 0, "v": new_v, "p": target_policy, "why": []}
    elif argv[1] == "snapshot":
        if len(argv) != 4:
            fail(2)
        state_path, op_text = argv[2], argv[3]
        # Read/decode STATE first (read errors code 3, strict JSON
        # errors code 4), then parse the inline OP, then check shapes.
        raw_state = _load_state(state_path)
        try:
            op = json.loads(op_text, parse_constant=_reject_constant,
                            parse_float=_finite_float,
                            object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(op, list) or len(op) == 0 \
                or type(op[0]) is not int:
            fail(5)
        kind = op[0]
        if kind == 0:
            # [0, OUT]: export STATE to OUT.
            if len(op) != 2 or type(op[1]) is not str or len(op[1]) == 0:
                fail(5)
            out_path = op[1]
        elif kind == 1:
            # [1, BASE, IN]: import IN into STATE.
            if len(op) != 3 or type(op[1]) is not int \
                    or not 0 <= op[1] <= MAX_COST \
                    or type(op[2]) is not str or len(op[2]) == 0:
                fail(5)
            base, in_path = op[1], op[2]
        elif kind == 2:
            # [2]: audit only, nothing is written.
            if len(op) != 1:
                fail(5)
        else:
            fail(5)
        v, current_policy, history = _validate_hotload_state(raw_state)
        state = {"v": v, "p": current_policy, "h": history}
        if kind == 0:
            try:
                with open(out_path, "rb") as f:
                    existing = f.read()
            except FileNotFoundError:
                existing = None
            except OSError:
                fail(3)
            if existing == _state_payload(state):
                # OUT already holds the canonical bytes: do not write.
                result = {"op": 0, "status": 1, "state": state}
            else:
                _write_state_atomic(out_path, state)
                result = {"op": 0, "status": 0, "state": state}
        elif kind == 1:
            raw_in = _load_state(in_path)
            in_v, in_policy, in_history = _validate_hotload_state(raw_in)
            in_state = {"v": in_v, "p": in_policy, "h": in_history}
            if base != v:
                fail(5)
            if in_state == state:
                # Importing the state already current is idempotent.
                result = {"op": 1, "status": 1, "state": state}
            else:
                _write_state_atomic(state_path, in_state)
                result = {"op": 1, "status": 0, "state": in_state}
        else:
            result = {"op": 2, "status": 2, "state": state}
    elif argv[1] == "config":
        if len(argv) != 4:
            fail(2)
        pack_path, op_text = argv[2], argv[3]
        # Read/decode PACK first (read errors code 3, strict JSON
        # errors code 4), then parse the inline OP, then check shapes.
        raw_pack = _load_state(pack_path)
        try:
            op = json.loads(op_text, parse_constant=_reject_constant,
                            parse_float=_finite_float,
                            object_pairs_hook=_object_no_dup)
        except (ValueError, RecursionError):
            fail(4)
        if not isinstance(op, list) or len(op) == 0 \
                or type(op[0]) is not int:
            fail(5)
        kind = op[0]
        if kind == 0:
            # [0, OUT]: export PACK to OUT.
            if len(op) != 2 or type(op[1]) is not str or len(op[1]) == 0:
                fail(5)
            out_path = op[1]
        elif kind == 1:
            # [1, BASE, IN]: import IN into PACK.
            if len(op) != 3 or type(op[1]) is not int \
                    or not 0 <= op[1] <= MAX_COST \
                    or type(op[2]) is not str or len(op[2]) == 0:
                fail(5)
            base, in_path = op[1], op[2]
        elif kind == 2:
            # [2]: audit only, nothing is written.
            if len(op) != 1:
                fail(5)
        elif kind == 3:
            # [3, BASE, TS, Q]: multi-version safe rollback. BASE is a
            # bounded integer; TS a non-empty list of distinct bounded
            # integers; Q a non-empty list of distinct [s, d] pairs.
            if len(op) != 4 or type(op[1]) is not int \
                    or not 0 <= op[1] <= MAX_COST:
                fail(5)
            base = op[1]
            ts_list = op[2]
            if not isinstance(ts_list, list) or not ts_list:
                fail(5)
            seen_versions = set()
            for ts in ts_list:
                if type(ts) is not int or not 0 <= ts <= MAX_COST \
                        or ts in seen_versions:
                    fail(5)
                seen_versions.add(ts)
            q_pairs = op[3]
            if not isinstance(q_pairs, list) or not q_pairs:
                fail(5)
            seen_queries = set()
            for pair in q_pairs:
                if not isinstance(pair, list) or len(pair) != 2:
                    fail(5)
                s, d = pair
                if type(s) is not str or type(d) is not str \
                        or (s, d) in seen_queries:
                    fail(5)
                seen_queries.add((s, d))
        elif kind == 4 or kind == 6 or kind == 7:
            # [4, BASE, LOG] replay / [6, BASE, LOG] read-only preview /
            # [7, BASE, LOG] read-only diff audit. BASE is a bounded
            # non-boolean integer; LOG a non-empty list of
            # [seq, pre, t, p] records whose seq/pre are bounded
            # non-boolean integers. The chain, topology, policy, and
            # history conflicts are checked after PACK validation in
            # _config_replay_sim. Ops 6 and 7 validate and simulate
            # exactly like op 4 but never write anything.
            if len(op) != 3 or type(op[1]) is not int \
                    or not 0 <= op[1] <= MAX_COST:
                fail(5)
            base = op[1]
            log = op[2]
            if not isinstance(log, list) or not log:
                fail(5)
            for record in log:
                if not isinstance(record, list) or len(record) != 4:
                    fail(5)
                seq, pre = record[0], record[1]
                if type(seq) is not int or type(pre) is not int \
                        or not 0 <= seq <= MAX_COST \
                        or not 0 <= pre <= MAX_COST:
                    fail(5)
        elif kind == 5:
            # [5, F, T, OUT]: export the replay log for versions
            # F+1..T. F and T are bounded non-boolean integers; OUT a
            # non-empty path. The 0 <= F < T <= v interval is checked
            # after PACK validation in _config_export_log.
            if len(op) != 4 or type(op[1]) is not int \
                    or type(op[2]) is not int \
                    or not 0 <= op[1] <= MAX_COST \
                    or not 0 <= op[2] <= MAX_COST \
                    or type(op[3]) is not str or len(op[3]) == 0:
                fail(5)
            from_v, to_v, out_path = op[1], op[2], op[3]
        elif kind == 8:
            # [8, m, b, e, t, p]: event-clock configuration transaction.
            # m is 0 (read-only preview) or 1 (atomic commit); b/e are
            # bounded non-boolean integers (expected version / event
            # time); t follows the metric topology and p the six-integer
            # policy, both validated after PACK validation. The b
            # conflict and MAX_COST overflow are checked in
            # _config_event_clock.
            if len(op) != 6 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or type(op[3]) is not int \
                    or not 0 <= op[2] <= MAX_COST \
                    or not 0 <= op[3] <= MAX_COST:
                fail(5)
            mode, base, event = op[1], op[2], op[3]
            new_t, new_p = op[4], op[5]
        elif kind == 9:
            # [9, m, b, e, r]: event-clock rollback transaction. m is 0
            # (read-only preview) or 1 (atomic commit); b/e/r are bounded
            # non-boolean integers (expected version, event time, and the
            # source version whose h[r] = [r, t, p] is the rollback
            # target). The r-present-in-h check (r <= v), the b conflict
            # with the current v, and the MAX_COST overflow are checked
            # after PACK validation in _config_rollback_tx.
            if len(op) != 5 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or type(op[3]) is not int \
                    or type(op[4]) is not int \
                    or not 0 <= op[2] <= MAX_COST \
                    or not 0 <= op[3] <= MAX_COST \
                    or not 0 <= op[4] <= MAX_COST:
                fail(5)
            mode, base, event, source = op[1], op[2], op[3], op[4]
        elif kind == 10:
            # [10, m, B, L, O]: rollback log export (m=0, O a non-empty
            # path) / replay (m=1, O null). m is 0 or 1; B is a bounded
            # non-boolean integer (the base version the first item's o
            # must equal); L a non-empty list of [e, r, o, n, a] items
            # whose e/r/o/n are bounded non-boolean integers and a a
            # boolean. The B-present-in-h check, the non-decreasing e,
            # the o chain, r <= o, the target-equality n/a rule, and
            # the commit reference/append checks run after PACK
            # validation in _config_rollback_log.
            if len(op) != 5 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or not 0 <= op[2] <= MAX_COST:
                fail(5)
            mode, base = op[1], op[2]
            log = op[3]
            if not isinstance(log, list) or not log:
                fail(5)
            for item in log:
                if not isinstance(item, list) or len(item) != 5:
                    fail(5)
                e, r, o, n, a = item
                if type(e) is not int or type(r) is not int \
                        or type(o) is not int or type(n) is not int \
                        or not 0 <= e <= MAX_COST \
                        or not 0 <= r <= MAX_COST \
                        or not 0 <= o <= MAX_COST \
                        or not 0 <= n <= MAX_COST \
                        or type(a) is not bool:
                    fail(5)
            out_path = op[4]
            if mode == 0:
                if type(out_path) is not str or len(out_path) == 0:
                    fail(5)
            elif out_path is not None:
                fail(5)
        elif kind == 11:
            # [11, m, B, G, O]: segmented rollback log export (m=0, O a
            # non-empty path) / replay (m=1, O null). m is 0 or 1; B is
            # a bounded non-boolean integer (the base version the first
            # segment's b must equal); G a non-empty list of [b, L, c]
            # segments whose b/c are bounded non-boolean integers and
            # whose L is a non-empty list of [e, r, o, n, a] items
            # shaped exactly like op 10's. The B-present-in-h check,
            # the b/c segment chain, the non-decreasing e (across
            # segments too), the o chain, r <= o, the target-equality
            # n/a rule, and the commit reference/append checks run
            # after PACK validation in _config_segmented_rollback_log.
            if len(op) != 5 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or not 0 <= op[2] <= MAX_COST:
                fail(5)
            mode, base = op[1], op[2]
            segments = op[3]
            if not isinstance(segments, list) or not segments:
                fail(5)
            for segment in segments:
                if not isinstance(segment, list) or len(segment) != 3:
                    fail(5)
                seg_b, seg_log, seg_c = segment
                if type(seg_b) is not int or type(seg_c) is not int \
                        or not 0 <= seg_b <= MAX_COST \
                        or not 0 <= seg_c <= MAX_COST:
                    fail(5)
                if not isinstance(seg_log, list) or not seg_log:
                    fail(5)
                for item in seg_log:
                    if not isinstance(item, list) or len(item) != 5:
                        fail(5)
                    e, r, o, n, a = item
                    if type(e) is not int or type(r) is not int \
                            or type(o) is not int or type(n) is not int \
                            or not 0 <= e <= MAX_COST \
                            or not 0 <= r <= MAX_COST \
                            or not 0 <= o <= MAX_COST \
                            or not 0 <= n <= MAX_COST \
                            or type(a) is not bool:
                        fail(5)
            out_path = op[4]
            if mode == 0:
                if type(out_path) is not str or len(out_path) == 0:
                    fail(5)
            elif out_path is not None:
                fail(5)
        elif kind == 12:
            # [12, m, B, G, I, C]: checkpointed segmented rollback log.
            # m is 0 (generate the checkpoint into C, PACK untouched) or
            # 1 (restore from C and replay the remaining segments); B is
            # a bounded non-boolean integer (the base version the first
            # segment's b must equal); G a non-empty list of [b, L, c]
            # segments shaped exactly like op 11's; I a non-boolean
            # integer in 0..len(G) splitting G into the checkpointed
            # prefix G[:I] and the replayed suffix G[I:]; C a non-empty
            # checkpoint file path. The B-present-in-h check, the
            # checkpoint key-order/type/digest checks, the prefix
            # commit-reference checks against PACK.h, and op 11's
            # segment-chain and per-item checks run after PACK
            # validation in _config_checkpoint.
            if len(op) != 6 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or not 0 <= op[2] <= MAX_COST:
                fail(5)
            mode, base = op[1], op[2]
            segments = op[3]
            if not isinstance(segments, list) or not segments:
                fail(5)
            for segment in segments:
                if not isinstance(segment, list) or len(segment) != 3:
                    fail(5)
                seg_b, seg_log, seg_c = segment
                if type(seg_b) is not int or type(seg_c) is not int \
                        or not 0 <= seg_b <= MAX_COST \
                        or not 0 <= seg_c <= MAX_COST:
                    fail(5)
                if not isinstance(seg_log, list) or not seg_log:
                    fail(5)
                for item in seg_log:
                    if not isinstance(item, list) or len(item) != 5:
                        fail(5)
                    e, r, o, n, a = item
                    if type(e) is not int or type(r) is not int \
                            or type(o) is not int or type(n) is not int \
                            or not 0 <= e <= MAX_COST \
                            or not 0 <= r <= MAX_COST \
                            or not 0 <= o <= MAX_COST \
                            or not 0 <= n <= MAX_COST \
                            or type(a) is not bool:
                        fail(5)
            index = op[4]
            if type(index) is not int or not 0 <= index <= len(segments):
                fail(5)
            ckpt_path = op[5]
            if type(ckpt_path) is not str or len(ckpt_path) == 0:
                fail(5)
        elif kind == 13:
            # [13, m, B, G, C]: multi-checkpoint restore. m is 0
            # (generate the manifest into C, PACK untouched) or 1
            # (read C, select the longest prefix whose commits all
            # exist in PACK.h, replay the remaining suffix); B is a
            # bounded non-boolean integer (the base version the first
            # segment's b must equal); G a non-empty list of [b, L, c]
            # segments shaped exactly like op 11's; C a non-empty
            # manifest file path. The manifest key-order/type/digest
            # checks, the longest-prefix selection against PACK.h, and
            # op 11's segment-chain and per-item checks run after PACK
            # validation in _config_multi_checkpoint.
            if len(op) != 5 or type(op[1]) is not int \
                    or op[1] not in (0, 1) \
                    or type(op[2]) is not int \
                    or not 0 <= op[2] <= MAX_COST:
                fail(5)
            mode, base = op[1], op[2]
            segments = op[3]
            if not isinstance(segments, list) or not segments:
                fail(5)
            for segment in segments:
                if not isinstance(segment, list) or len(segment) != 3:
                    fail(5)
                seg_b, seg_log, seg_c = segment
                if type(seg_b) is not int or type(seg_c) is not int \
                        or not 0 <= seg_b <= MAX_COST \
                        or not 0 <= seg_c <= MAX_COST:
                    fail(5)
                if not isinstance(seg_log, list) or not seg_log:
                    fail(5)
                for item in seg_log:
                    if not isinstance(item, list) or len(item) != 5:
                        fail(5)
                    e, r, o, n, a = item
                    if type(e) is not int or type(r) is not int \
                            or type(o) is not int or type(n) is not int \
                            or not 0 <= e <= MAX_COST \
                            or not 0 <= r <= MAX_COST \
                            or not 0 <= o <= MAX_COST \
                            or not 0 <= n <= MAX_COST \
                            or type(a) is not bool:
                        fail(5)
            ckpt_path = op[4]
            if type(ckpt_path) is not str or len(ckpt_path) == 0:
                fail(5)
        else:
            fail(5)
        v, topo, policy, history = _validate_config_pack(raw_pack)
        pack = {"v": v, "t": topo, "p": policy, "h": history}
        if kind == 8:
            # The event t/p follow the same metric topology and
            # six-integer policy contracts as the pack's own t/p.
            _validate_topology(new_t, metrics=True)
            if not _is_policy(new_p):
                fail(5)
        if kind == 0:
            try:
                with open(out_path, "rb") as f:
                    existing = f.read()
            except FileNotFoundError:
                existing = None
            except OSError:
                fail(3)
            if existing == _state_payload(pack):
                # OUT already holds the canonical bytes: do not write.
                result = {"op": 0, "status": 1, "config": pack}
            else:
                _write_state_atomic(out_path, pack)
                result = {"op": 0, "status": 0, "config": pack}
        elif kind == 1:
            raw_in = _load_state(in_path)
            in_v, in_topo, in_policy, in_history = \
                _validate_config_pack(raw_in)
            in_pack = {"v": in_v, "t": in_topo, "p": in_policy,
                       "h": in_history}
            if base != v:
                fail(5)
            if in_pack == pack:
                # Importing the pack already current is idempotent.
                result = {"op": 1, "status": 1, "config": pack}
            else:
                _write_state_atomic(pack_path, in_pack)
                result = {"op": 1, "status": 0, "config": in_pack}
        elif kind == 2:
            result = {"op": 2, "status": 2, "config": pack}
        elif kind == 3:
            result = _config_rollback(pack_path, pack, v, topo, policy,
                                      history, base, ts_list, q_pairs)
        elif kind == 4:
            result = _config_replay(pack_path, pack, v, history, base, log)
        elif kind == 6:
            result = _config_preview(pack, v, history, base, log)
        elif kind == 7:
            result = _config_diff_audit(pack, v, history, base, log)
        elif kind == 8:
            result = _config_event_clock(pack_path, pack, v, topo, policy,
                                         history, mode, base, event,
                                         new_t, new_p)
        elif kind == 9:
            result = _config_rollback_tx(pack_path, pack, v, topo, policy,
                                         history, mode, base, event, source)
        elif kind == 5:
            result = _config_export_log(out_path, v, history, from_v, to_v)
        elif kind == 10:
            result = _config_rollback_log(pack_path, pack, v, history,
                                          mode, base, log, out_path)
        elif kind == 11:
            result = _config_segmented_rollback_log(pack_path, pack, v,
                                                    history, mode, base,
                                                    segments, out_path)
        elif kind == 12:
            result = _config_checkpoint(pack_path, pack, v, history,
                                        mode, base, segments, index,
                                        ckpt_path)
        elif kind == 13:
            result = _config_multi_checkpoint(pack_path, pack, v,
                                              history, mode, base,
                                              segments, ckpt_path)
    else:
        fail(2)
    # Write raw UTF-8 bytes to the binary stdout buffer: the text layer
    # would apply the locale encoding and newline conversion (e.g. \r\n
    # on Windows), corrupting the required byte-exact output.
    out = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(out.encode("utf-8") + b"\n")


if __name__ == "__main__":
    main()
