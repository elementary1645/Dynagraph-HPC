# Phase 6B-1 campaign foundation

Phase 6B-1R repairs the independent acceptance findings. Campaign-plan and trial
manifest versions remain 1. Hardware reports and admission outputs now require
version 2; incomplete version-1 hardware records are rejected, never silently
upgraded. Historical v1 evidence remains preserved. See the remediation contract
below and the research log for actual commands and results.

Phase 6B-1 implements planning and read-only hardware qualification, not an
experiment executor. The user's Phase 6B-1 authorization supersedes the older
Phase 6 deferral for this subphase only. Phase 5C is merged at 8b05c2b; hosted
completion is supplied by the user, not newly established by these local checks.
Historical Phase 5 documents/results keep their original meaning. No performance,
race-freedom, or ThreadSanitizer acceptance claim follows from this work.

## Commands

Run from the repository root. No command executes the benchmark or changes
hardware placement. JSON goes to stdout; errors go to stderr. The caller chooses
whether to retain output in a new location. There is no run, resume or retry command.

```sh
python3 -B benchmarks/python/campaign.py validate --plan benchmarks/configs/campaign-development-v1.json
python3 -B benchmarks/python/campaign.py expand --plan benchmarks/configs/campaign-development-v1.json
python3 -B benchmarks/python/campaign.py inspect
python3 -B benchmarks/python/campaign.py inspect --executable build/release/dynagraph_bench
python3 -B benchmarks/python/campaign.py admit --plan benchmarks/configs/campaign-development-v1.json --hardware results/raw/hardware.json
python3 -B tests/test_campaign.py
```

For actual runtime-mapping evidence, `inspect --executable FILE --pid PID` may
read an **already-running** matching executable's Linux procfs mappings. This
never starts or attaches a debugger to the target. Do not start a benchmark for
this foundation's validation. Permission failures/missing mappings remain
unavailable evidence. Without --pid, ELF DT_NEEDED and the compiler's candidate
libgomp are only hints and cannot satisfy scientific runtime admission.

Exit codes: 0 valid plan/manifest/inspection or qualified/development admission;
1 scientific hardware rejected (diagnostics remain in JSON); 2 invalid input,
unsupported schema or collection I/O failure. Development exit 0 does not confer
scientific eligibility. The example has explicit zero placeholder build digests
and a two-logical-CPU development allocation; replace them with actual evidence
in a separately reviewed scientific plan. It is not an experiment matrix.

## Campaign schema 1

All listed keys are required, with exact fields at each schema level. There are
no scientific defaults. Integer fields are JSON integers (bool/floats rejected),
except the embedded unchanged v1 recipe's decimal-string seeds. Duplicate JSON
keys, nonfinite/fractional numbers, invalid UTF-8, excessive nesting and unknown
fields fail. Labels are 1..64 ASCII identifier characters; hashes are lowercase
64-character SHA-256; revision is a full 40-character Git object ID.

| Field | Contract |
| --- | --- |
| schema_version, campaign_id, panel | Version 1, researcher-assigned campaign ID, explicit panel ID |
| measurement_level, timing_mode | `engine-update-service-v1`; `full-trace` or `per-update` |
| workloads | 1..128 objects: id, complete recipe, recipe_sha256, graph_sha256, trace_sha256, bundle |
| configurations | 1..64 objects: unique id, workers 1..64, delta 1..UINT64_MAX; duplicate settings rejected |
| policies | Exactly dijkstra, delta-stepping, incremental, heuristic in canonical order |
| no_effect | Explicit shared_fast_path or execute_selected |
| heuristic | Exact existing 4096/32/65536 thresholds, with named fields |
| sessions | 1..32 unique session labels, in declared order |
| blocks | 4..400, divisible by four; repetitions per policy per cell/session |
| warmups, diagnostics | 0..100 warmups per measured worker group; 0 or 1 separate diagnostic per policy/cell/session |
| order_seed, order_version | uint64 seed; campaign-balanced-four-v1 |
| build | revision, Release build_type, executable relative path, executable_sha256, compiler_sha256, openmp_sha256, flags_sha256, uninstrumented=true |
| hardware | mode, allocated_cpus, min_physical_cores, allow_smt, allow_virtualization, min_available_memory_bytes, require_frequency_evidence, exclusive, reservation |
| limits | max_trials (<=100000), timeout_seconds (1..3600), max_memory_bytes (<=2^50), max_output_bytes (<=128 MiB) |
| expected_evidence | Exact ordered list in the example: plan.json, trial-manifest.json, hardware.json, admission.json, records.jsonl, stdout, stderr, exit.json, sha256.json |
| comparisons | Explicit configuration references; only worker-scaling with equal delta and differing workers |

A workload recipe is validated with existing `workloads.validate_spec`, includes
all graph/trace/weight/source parameters and four seeds, and must have a nonempty
trace. Its id matches recipe.workload_id, and the canonical recipe digest must
match recipe_sha256. Duplicate workload content identities are rejected. No
recipe generation, artifact read or benchmark execution occurs during planning.
Graph/trace hashes are **expected** identities; their correspondence to the recipe
must be verified by existing artifact regeneration before future execution. This
foundation does not falsely certify nonexistent bundles or compiled flags.

Bundle/executable references must be canonical relative POSIX paths with no
parent traversal, empty/dot components, absolute paths, backslashes, colons or
control characters. Planning never opens those references. A future executor
must also enforce containment against symlink aliases when staging files.
The CLI input paths are explicitly chosen local files; no embedded command,
plugin, shell expression or import path is accepted.

Serialization reuses sorted-key compact LF-terminated `canonical_json`. The plan
hash is SHA-256 of validated canonical bytes, independent of source JSON key order
and whitespace; array order is intentional and hashed. Campaign IDs are not a
global registry: the plan hash disambiguates reused labels. Version 1 permits a
bounded workload/configuration cross product, not an arbitrary executable matrix.

## Trial manifest

The envelope contains schema=dynagraph-campaign-trials, schema_version=1,
campaign_id, plan_sha256, planning_only=true, admission_required=true,
order_version and trials. Each row includes:

- trial_id (SHA-256 of plan hash and stable semantic coordinates), sequence;
- session, workload_id, configuration_id, policy, workers, delta;
- phase=warmup/diagnostic/measured, block and policy_position;
- worker_group, pairing_id and configuration_pairing_id.

Every trial references an immutable hashed plan rather than duplicating its build,
resource and workload requirements. Measured/warmup rows with one worker_group
belong to one future worker lifecycle: fresh engine warmups then a fresh measured
engine, preserving existing timing semantics. These are planned events, **not**
claims that each warmup should become a separate subprocess. Diagnostic groups
use block=-1 and are distinct from measured groups. Existing four-policy schedule
rows are position-balanced and balance ordered adjacent pairs in every four
blocks. Within each session, workload/configuration cells use seeded descending
Fisher-Yates with SplitMix64. Each cell consumes a fresh uint64 schedule seed.
Outer cells are randomized, not asserted to be position-balanced across sessions.

pairing_id joins the same workload/session/repetition across configurations;
configuration_pairing_id also fixes configuration for policy comparison. Neither
permits joining different timing modes, fast paths, delta, builds or workloads.
Those remain fixed at campaign level or checked by explicit comparisons. Planning
is not a statistical analysis engine.

Expansion is checked before constructing rows:

`workloads * configurations * sessions * 4 * (diagnostics + blocks * (1 + warmups))`

must fit both declared max_trials and the global 100000-event ceiling. Input is
bounded to 1 MiB, depth 32 and 50000 JSON nodes. CPU lists/ranges are separately
bounded. Declared future runtime/memory/output budgets are recorded, **not enforced
by a nonexistent executor**. No existing runner timeout changes.

## Hardware report and admission

Every observation has value, source and origin=observed/unavailable. Unavailable
values are null. User declarations are separate in the plan/admission output;
they never become observed exclusivity facts. The report records CPU model,
online logical CPUs, package/core/sibling IDs, NUMA CPU lists, effective affinity,
visible cgroup v2 ancestors, quota fractions, cpuset intersection, memory headroom,
MemAvailable, OS/kernel, virtualization/container indicators, compiler identity,
OpenMP library identity, executable digest, placement tools and cpufreq data.

Unified membership is resolved against `/proc/self/mountinfo`'s mount root, not
assumed to live at the namespace root. Every visible ancestor contributes CPU
quota, effective cpuset and memory limits/current usage. Missing controllers,
cgroup v1, escaped/unsupported mount mappings and hidden ancestry remain explicit
limitations. Unlimited visible quota never establishes ownership. Memory is a
point-in-time minimum of MemAvailable and visible ancestor headroom.

Scientific qualification requires:

- An explicit exclusive reservation declaration with a nonempty reference.
- Effective process affinity exactly matching sorted unique allocated CPUs.
- Consistent per-CPU topology, enough distinct package/core pairs, and no SMT
  sibling allocation unless explicitly permitted.
- Worker counts compatible with allocation/core requirements and every observed
  ancestor quota; allocated CPUs contained in the effective cpuset.
- Sufficient memory, with summaries consistent with recorded ancestor data.
- Allowed virtualization indicators; matching compiler, executable and runtime
  digests; runtime mapped by a matching observed process, not merely a candidate.
- Governor evidence for every allocated CPU when required.

Admission output binds the decision to campaign_id, canonical plan_sha256 and
canonical hardware_sha256; it cannot be interpreted as a result for another plan.
Missing or contradictory required observations reject scientific qualification.
Missing declarations/invalid plans reject both modes. Development plans explicitly
claim no exclusive reservation and can qualify for harness checks despite missing
scientific observations; every failed scientific check remains visible and
scientific_performance_allowed=false. No admission result authorizes multicore
scaling claims; multicore_scaling_claims_allowed is always false in this phase.

Reports can be copied or fabricated: this is qualification **on supplied evidence**,
not authenticated hardware attestation. Topology may itself be virtualized; CPU
model/count never establish physical ownership. Compiler identity is the inspected
host compiler, not proof of how an executable was built. Recorded revision, flags
hash and uninstrumented requirement still need a separately verified build record.
PID mapping observation is non-atomic and read-only; matching executable and stable
maps/start identity and mapped file device/inode checks reduce accidental mismatch, not hostile-host attacks. Runtime
support is currently Linux ELF/libgomp only. No binary under inspection is run;
fixed g++/readelf introspection commands use trusted host tools, without a shell.

## Acceptance and remaining work

Acceptance requires deterministic plans/hashes/schedules, strict rejection and
bounds, positive and negative synthetic hardware qualification, development-only
behavior on this host, unchanged legacy gates/goldens/analysis/archives and no
production code/timing/heuristic/dependency changes. New tests remain outside CTest,
keeping the existing 31-test acceptance profiles unchanged. The only CI change adds
`python -B tests/test_campaign.py` to the existing standalone archive/diagnostic
regression step in Debug/Release jobs, so the new contract is continuously checked
without adding acceptance tests or changing sanitizer jobs.

Future reviewed subphases must implement execution/staging, resource enforcement,
build-evidence linkage, observation freshness and reservation verification,
actual-team telemetry, controlled collection, additional measurement levels,
statistical inference and independent replication. No full experiment matrix,
benchmark results, speedups, heuristic tuning or native batch repair is included.

## Phase 6B-1R hardware-report v2 contract

These corrections address the four independently reproduced false-success cases.
The first eight regressions (API and CLI for each finding) were added against
95c515f before repairs: all eight failed while the original 38 tests passed.
The repaired suite retains the original acceptance cases with complete v2 fixtures
and adds nearby adversaries. No Phase 5C archive, timing JSONL, workload recipe,
analysis or public SSSP contract is modified.

### Cgroup ancestry

The `cgroups.value` object is closed and requires membership, mountinfo, views,
effective_cpuset, quota_pairs, memory_headroom_bytes and visibility. Membership
retains the unified `0::PATH` line. Mountinfo retains the complete observed text,
not just a selected mount. Every relevant cgroup2 mount is derived again during
admission, sorted by mount ID; ambiguity, duplicate IDs/points or inconsistent
hierarchy devices reject. Mount roots/points and membership must be canonical
absolute supported paths. Escaped mount paths and cgroup v1 remain unsupported.

Each view contains mount_id, device, root, mountpoint, membership, leaf, endpoint
and ancestors. The first seven fields must match the raw membership/mountinfo
mapping exactly. Ancestors must cover every directory from leaf through endpoint,
with neither missing nor extra entries. Each entry has path, cgroup_path,
`cpu.max`, `cpuset.cpus.effective`, `memory.max` and `memory.current`. Hierarchy
paths are reconstructed independently of filesystem aliases. All supplied views
must be present; removing an ancestor/view or changing an endpoint cannot be
hidden by merely refreshing summary fields.

All quota constraints are checked, cpusets intersect across every ancestor/view,
and memory headroom takes the minimum. Overlapping views of the same hierarchy
path must agree on quota, cpuset and memory-limit policy. Changing memory.current
is allowed because it is a gauge sampled at different times; the most restrictive
observed headroom is retained. Contradictory policy observations reject rather
than choosing a convenient view. Summary fields must equal recomputed values.

Limits: at most 16 matching views, 64 ancestors per view, 256 ancestor entries in
total, 4096 mountinfo records and 256 KiB UTF-8 mountinfo. Numeric controller values
are bounded canonical ASCII strings; CPU lists retain their separate limits.
If required controller evidence cannot be captured, the whole cgroup observation
is explicitly unavailable with a reason, and scientific qualification fails.
Full *declared visible* ancestry never proves absence of hidden host constraints;
a fabricated or edited raw mountinfo document is not authenticated by this parser.

### Runtime evidence

The closed candidate-library form has exactly path, sha256, soname and
linkage=`candidate-library`. Its path must be canonical absolute and its filename
must agree with supported soname `libgomp.so.1`. It can explain a host observation
but never satisfies scientific runtime-mapping admission.

The closed observed-process-mapping form additionally requires executable_sha256,
pid, process_stat, process_start_ticks, mappings and file_identity. A positive
integer PID must agree with a structurally valid Linux stat record (including at
least the 49 numeric fields after state); start ticks must agree with that record.
File identity has exactly device_major, device_minor, inode, size and mtime_ns,
with exact integer types and bounded ranges. Mapping lines must have valid address
ranges/permissions/numeric fields and agree with the runtime path, device and inode.
Duplicate/overlapping ranges, unknown fields, mismatched sonames, missing fields
and malformed types reject. Digests must match the plan and executable observation.

The collector validates the record it constructs, compares the mapped file's
identity before/after hashing, and rechecks process start identity, maps and
executable bytes. It never launches the supplied executable. Fixtures now contain
realistic complete synthetic stat/map/file records, not just a linkage label.
Runtime hashes and process records do not authenticate an untrusted host or make
this non-atomic observation an execution-time stability guarantee.

### Topology, optional facts and Unicode

All CPU topology rows are validated before checking allocated CPUs. Each sibling
array must exactly equal the complete package/core equivalence group, for every
CPU, including unallocated siblings. IDs are typed, sorted/unique where arrays
require it, and unknown nested fields reject. Supplied NUMA records must have
unique node IDs, disjoint CPU sets covering the supplied online topology, and no
SMT core split across nodes. Memory-only nodes may have empty CPU lists. Genuinely
unavailable optional NUMA remains null/unavailable; no NUMA-placement guarantee
is inferred from that absence. Valid multiple-node topology does not claim a
single-node placement policy.

Supplied compiler, virtualization, placement and frequency evidence is also
validated against closed structures. Missing required facts and contradictions
prevent scientific eligibility. User ownership declarations remain separate;
structural consistency is not independent observation, attestation or reservation
verification. No one-time result proves that the environment stays unchanged.

All campaign path references require strict UTF-8 encoding and filesystem encoding
roundtrip, including rejection of both high and low unpaired surrogates before
any future file access. Legitimate Unicode is retained. No NFC/NFD normalization
is performed: different code-point sequences are different hashed references on
the supported POSIX platform. Future staging must still check symlinks/aliases;
this policy does not certify normalization behavior of other filesystems.

## Phase 6B-1R2 runtime evidence v3

N1/N2 remediation replaces the observed runtime record with an explicitly versioned
`evidence_version=3` form. Campaign-plan/trial-manifest v1 and hardware/admission v2
remain unchanged. Candidate-library records remain diagnostic only. Old observed
runtime records lack mandatory v3 evidence and reject scientific admission; they
are never inferred/upgraded. Development mode still admits harness use while
recording scientific failures and denying scientific eligibility. Recapture runtime
provenance for scientific use. Cgroup, topology, Unicode and Phase 5C archive
contracts retain their previous meaning.

### Precisely supported linkage

Here, observed runtime linkage means **a direct `DT_NEEDED` entry for
`libgomp.so.1` in the matching process executable, plus a unique observed library
with that actual ELF `DT_SONAME`, whose complete file-backed `PT_LOAD` page images
match its process VMAs at one relocation bias**. Both the main executable and
library must be supported ELF images. The main executable must have an executable
entry and a canonical absolute glibc `ld-linux-x86-64.so.2` interpreter. The runtime
is an ET_DYN library without an interpreter. Filename matching discovers candidates;
it never establishes library identity. No `dlopen`, candidate execution, shell
interpolation or candidate-directed tool invocation is used by this collector.

This is a deliberately narrow supported subset: Linux procfs, ELF64 little-endian
x86-64, glibc interpreter, and a 4096-byte kernel page size explicitly recorded from
`sysconf(SC_PAGE_SIZE)`. Other architectures/classes/encodings/page sizes, indirect
or dlopen-only dependencies, static linkage, missing SONAMEs, multiple candidate
paths, deleted/replaced files, overlapping load-page images, and ambiguous or
incomplete supported evidence fail closed. Readable-only file mappings cannot
satisfy executable segment coverage. An additional differently named interposed
runtime, symbol resolution, lazy binding, or actual active execution of OpenMP
functions is not established by this supported relationship.

### Collection and offline validation

The standard-library-only `campaign_elf.py` parses bounded raw ELF metadata.
Each observed record adds page_size, elf and executable_elf to its previous
PID/stat/start/mappings/file-identity fields. Each ELF object has exactly file_size,
header, program_headers, dynamic, strings and interpreter. Byte fields are canonical
lowercase hexadecimal excerpts from the file; offsets are derived again from the
ELF headers and dynamic records rather than trusted extracted segment/SONAME labels.
No entire binary is embedded. Collected hashes cover the complete files.

The collector reads metadata and computes each digest using one regular-file
descriptor, comparing device/inode/size/mtime/ctime and the path identity around
collection. File size is capped at 256 MiB for collection. ELF evidence limits are
128 program headers and 64 KiB each for dynamic/string metadata. ELF headers,
program/section table bounds, load ranges/flags/alignment, dynamic termination,
string references, SONAME, dependency and interpreter records are checked. Metadata
must resolve inside unique file-backed load segments, and overlapping supplied
excerpts must contain identical bytes. RELRO must reside inside a writable load.
Process identity, maps, executable hash and file identities are rechecked as well.

The pure admission validator reparses those excerpts without opening paths. It
preserves procfs offsets and permissions, requires ordered nonoverlapping aligned
VMAs, and checks offset plus length against the page-rounded file size. Arithmetic
is checked against uint64 overflow. Actual data must start within the file; the
last mapped page may contain legitimate file padding. Zero-filled anonymous BSS
tails are outside the file-backed record and are not certified.

For each file-backed load, virtual-page and file-page offsets determine one shared
relocation bias. Virtual addresses need not equal file offsets. Every recorded VMA
must belong to a load and every file-backed load page must be covered, including
all executable pages. Read/execute permissions must match; writable permission may
be removed only inside the page range protected by GNU RELRO. Private mappings,
split VMAs, RELRO splits, different virtual/file offsets, final-page padding and
ordinary nonzero relocation biases are supported. Unsupported overlapping load
pages reject rather than guessing loader overwrite order.

The design follows the ELF ABI's [program header and load alignment rules](https://gabi.xinuos.com/elf/07-pheader.html)
and [dynamic linking records](https://gabi.xinuos.com/elf/08-dynamic.html).

### Trust boundary and tests

Supplied reports and metadata excerpts can still be fabricated. Offline validation
checks their consistency; it cannot recompute a whole-file hash from excerpts or
authenticate the host. A matching DT_NEEDED declaration and mapped load geometry
are not proof of loader symbol binding, executed OpenMP instructions, actual team
size, ownership, exclusivity, build flags or future stability. File/process rechecks
are non-atomic observations and do not defeat a hostile host. Existing scientific
qualification remains qualification on supplied evidence, never host attestation.

Regression tests retain F1–F4 and add the original N1/N2 red cases, malformed ELF
headers/tables/SONAMEs, executable coverage and permissions, page evidence,
overflow, bounds, linkage/version migration, and valid split/padded/relocated
layouts. A trusted, newly compiled idle helper directly linked with OpenMP supplies
a real positive procfs fixture. It only queries the runtime's configured maximum
and waits on stdin; it executes no graph query, parallel region or performance
campaign. The collector never starts an inspected executable. Validation commands,
actual outcomes and preserved failures are recorded in the research log.

## Phase 6B-1R3 ELF layout restrictions

Runtime evidence v3 and the other schema versions are unchanged. N3/N4 hardening
narrows the supported ELF layout within the existing Linux/x86-64/glibc/4096-byte
page subset. It does not broaden scientific qualification or add execution.

Every PT_LOAD p_align must be 0, 1, or a power of two no greater than 4096. Zero
and one specify no additional ELF alignment, but supported file-backed loading
still requires offset/vaddr congruence modulo the 4096-byte kernel page size.
All other supported alignments must also satisfy ELF offset/vaddr congruence.
The permitted maximum load alignment is thus at most the kernel page size, and
the already-required page-aligned relocation bias preserves every accepted load's
alignment. Larger ELF alignments are explicitly unsupported, even if a supplied
bias happens to satisfy them; records with these alignments must not qualify.
The locally available genuine libgomp was inspected before this choice: all four
PT_LOAD alignments were 4096. This observation is recorded, not assumed universal.
A future larger-alignment implementation needs separate origin/alignment tests.

The supported memory layout consists of disjoint page-rounded intervals
[floor_page(p_vaddr), ceil_page(p_vaddr + p_memsz)) for **every nonempty PT_LOAD**.
This includes zero-file-size loads and ordinary BSS tails. Adjacent intervals may
meet at an endpoint. Sharing a page between different nonempty load images is
unsupported even when their byte intervals are adjacent or nonoverlapping; the
validator does not emulate loader overwrite order. Empty memory spans occupy no
pages. Existing file-size <= memory-size and bounded file-offset rules remain.

Page rounding and both unrelocated and relocated memory endpoints use checked
uint64 arithmetic. Relocation checks include anonymous-only loads. Nonoverlapping
zero-fill/BSS regions do not require file-backed procfs VMAs; their contents and
anonymous VMAs are not certified. File-backed pages still require complete
coverage, consistent permissions, offsets and identity at one bias. Final file
page padding, BSS tails within a load, split VMAs, and RELRO remain supported.

Both the main executable and library receive these structural ELF checks. An
unsupported load layout fails scientific admission without upgrading old evidence
or changing development-only semantics. This remains provenance consistency on
supplied evidence: excerpts and declarations are unauthenticated, collection is
non-atomic, and no result proves active OpenMP execution, symbol binding, team
size, reservation ownership, build provenance or execution-time stability.
