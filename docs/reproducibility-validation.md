# Full validation and isolated builds — Phase 5C-3B-1

The current archive contract is the repaired v2 format in the Phase 5C-3B-3R
and 3R2 sections below; the latter refines configure/time validation. Earlier
phase observations remain historical.

This opt-in gate checks setup and registrations, without changing algorithms,
benchmark timing, CI or existing optional coverage. The default/minimal CMake
behavior remains available. Full validation is not a race-detector acceptance
claim or controlled performance experiment.

## Environment

The demonstrated baseline is Ubuntu/Linux x86_64, GCC 13.3.0 with libgomp,
CMake 3.28.3, Make and Python 3.14.2. CMake requires >=3.21 and C++17/OpenMP;
other toolchain/platform versions are not certified by these observations.
BUILD_TESTING=OFF needs no Python. Artifact tests require Python >=3.8; analysis
needs >=3.11. Full validation additionally requires every exact package version
in benchmarks/requirements-analysis.txt. No tool here installs dependencies.

With explicit dependency-install approval, create an ignored isolated environment:

```sh
python3 -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r benchmarks/requirements-analysis.txt
.venv-analysis/bin/python -m pip check
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/dynagraph-validation-mpl .venv-analysis/bin/python -B tools/validation/check_environment.py
```

Choose an available compatible Python with working venv/ensurepip; system Python
may lack that component. Do not substitute pins or upgrade system packages.
The gate compares all eleven installed versions and renders a PNG in memory with
Matplotlib Agg, so metadata-only installations cannot establish renderer readiness.
MPLCONFIGDIR must be writable. Exact pins do not establish cross-platform image
identity or archive operating-system libraries.

## Full gate and registration contract

```sh
cmake --preset debug -DDYNAGRAPH_FULL_VALIDATION=ON -DDYNAGRAPH_ANALYSIS_PYTHON="$PWD/.venv-analysis/bin/python"
cmake --build --preset debug --parallel 2
python3 -B tools/validation/check_registration.py --build build/debug
ctest --preset debug --parallel 1 --output-on-failure
```

Use the release preset similarly. Full mode requires BUILD_TESTING=ON, Python
>=3.11, exact rendering pins and functioning Agg. Invalid interpreter, dependency,
renderer or registration conditions fail configuration with diagnostics. The
checked-in tools/validation/default-tests.json is the sorted 31-name set grounded
in the merged Phase 5C-2 registrations. The configure gate checks actual CMake
TESTS names; the standalone checker enumerates generated CTest JSON and detects
missing, extra and duplicate names. It also requires the CTest JSON 1.0 envelope,
valid entries/properties and enabled tests. It works for any build directory/configuration.
Neither checker adds a CTest entry or changes any existing suite count.

Optional tiers remain OFF by default and additive. Full mode permits precisely
the enabled optional names. For a standalone check, explicitly declare them:

```sh
python3 -B tools/validation/check_registration.py --build build/release --optional concurrency-stress --optional concurrency-extended
```

System tiers use --optional system-stress/system-extended. Intentional-race
controls remain outside CMake/CTest/CI. Never run them as ordinary passing tests.

## Isolated procedure

After approval/commit of this implementation, this procedure clones a specific
revision locally, verifies its exact Git identity and clean state, requires fresh
build directories, validates the external interpreter and runs Debug, Release,
then ASan+UBSan sequentially. It refuses an existing output directory, preserves
combined output and per-command start/end timestamps, exit codes, environments
and wall times, and stops on the first failure. Keep the full output directory.

```sh
python3 -B tools/validation/clean_checkout.py --revision <reviewed-commit> --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-validation-new
```

The clean committed procedure requires the requested revision to contain these
tools. Before committing, --include-working-tree explicitly applies the tracked
patch and copies nonignored untracked files into the isolated base checkout.
The receipt records the clean base, binary patch hash and a complete typed source inventory.
This is a **clean-base checkout plus identified uncommitted overlay**, not a
claim that the changed implementation is already a clean committed revision.
No commit is created. Review the source inventory before using this mode.

The driver selects explicit GCC Debug/Release settings equivalent to the presets,
uses the same approved interpreter for every analysis gate, checks exactly 31
names before each build, and runs CTest --parallel 1. It does not use existing
build caches or install packages. Build parallelism is two compilation jobs;
no build/test suites overlap. Run without other verification workloads.

Sanitizer flags are -fsanitize=address,undefined -fno-omit-frame-pointer with
matching linker flags. The final suite sets
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1. LeakSanitizer needs process
inspection; ptrace-based sandboxes can fail independently of the program. Launch
the driver outside such a sandbox through the approved execution mechanism.
The script cannot escape a sandbox itself. Preserve failures and do not relabel
isolated reruns as full passes. No test timeout is increased.

## Gate failure fixtures

```sh
python3 -B tools/validation/test_gate.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-negative-new
```

Disposable interpreter wrappers simulate Python 3.10, missing/mismatched metadata
and Agg failure; a disposable source copy omits analysis_stats. Each case must
fail actual CMake configuration with its expected diagnostic. A nonexistent
interpreter is also tested. Missing/extra/duplicate name comparisons are checked
separately. No approved environment package is modified. These fixtures are
standalone infrastructure checks, keeping the approved default suite at 31.

CI parity, end-to-end real pipeline archives, portable evidence distribution and
alternative calibrated race tooling remain Phase 5C-3B-2 work. The race-detector
gate remains unmet. See research-log.md for actual commands/outcomes and limits.

## Executed pre-commit verification

On 2026-10-28, the driver verified clean base commit
`a6c6266262dff4a59f99fa9d6fd2381f38f3748a` in a separate clone, then applied the
explicit uncommitted overlay. Implementation/CMake hashes matched the tested
snapshot at the end of that original run (before the repair below). All three build directories were new; no existing cache was reused.
Results: Debug 31/31 (48.71 s), Release 31/31 (43.29 s), ASan+UBSan 31/31
(82.98 s), all exit 0. These were sequential outside-sandbox runs with leak
detection enabled. Dijkstra passed at 1.07/0.07/3.14 s under its unchanged limit.

All six negative configure fixtures rejected their intended condition. Additional
checks confirmed minimal configuration with absent analysis interpreter (27 names),
BUILD_TESTING=OFF configuration, full-mode rejection of BUILD_TESTING=OFF, and all
optional tiers together (37 exact names). Generated CTest fixtures confirmed
missing, extra and duplicate diagnostics through the command-line checker itself.
No optional stress/extended workload was rerun merely to check registration.

Raw logs, commands, source patch/hash inventory, start/end timestamps and summaries
are retained locally under ignored `results/validation/phase5c3b1/`. The first
negative harness attempt rejected a correct missing-package failure because
CMake wrapped its diagnostic; that evidence is retained in `negative/`. The
corrected whitespace-normalized harness passed in `negative-v2/`. No configuration
or acceptance-suite failure was silently retried. A future clean committed-revision
run without --include-working-tree remains distinct from this pre-commit result.

## Phase 5C-3B-1R: strict acceptance and snapshot repair

The independent audit blocked approval of the original tooling, despite the actual
31/31 runs above: name-only checks could accept disabled registrations, exit 0
could accept skipped/incomplete execution, and untracked symlinks were silently
dereferenced. Historical logs and conclusions remain in `phase5c3b1/`; the new
repair evidence is separate. The original in-repository output command in the
research log is historical and is now deliberately rejected.

Registration validation requires `kind=ctestInfo`, version 1.0, a list of named
entries and valid property records. Missing/extra/duplicate names, disabled tests,
unknown DISABLED encodings and malformed metadata fail. Configure-time names are
a separately identified CMake-produced array, never treated as CTest JSON; CMake
also rejects disabled registrations. All optional names must be explicitly selected.

Execution uses CTest's `--output-junit` (demonstrated with CMake 3.28.3; the option
exists since the project's minimum CMake 3.21). Acceptance requires process exit 0,
a fresh report with valid counts, the exact expected testcase set, `status="run"`
for every testcase, finite nonnegative durations and output metadata. Disabled,
skipped, not-run, failure/error, missing, duplicate, extra and malformed results
fail even when CTest returns 0. XML DTDs/entities and non-UTF-8 input are rejected;
no external XML dependencies or entity resolution are used. Raw XML, logs, receipts,
per-test accepted results and SHA-256 evidence hashes are retained. Registration
counts are never used as a substitute for executed passing results.

The overlay supports regular text/binary files, full permission modes (including
executable bits), tracked modifications/deletions/mode changes and relative internal
symlinks. Inventory entries contain path, type, permission mode, regular-file SHA-256
or symlink target. Source and destination inventories must match before building
and remain unchanged through completion. A binary Git patch is also retained.
Symlinks are copied as links. Absolute, escaping (including intermediate hops), broken/cyclic links, links to
uncaptured targets, symlink parent directories, special files and submodules are
explicitly rejected. UTF-8 paths with spaces, apostrophes and Unicode are tested;
other filename encodings are not supported. Directory modes, ACLs and extended
attributes are not archived: this is a Git source snapshot, not a filesystem backup.

Source and evidence paths must be disjoint after canonicalization: neither may
contain the other, even through an alias. Output must not exist. The clone, new
build directories, temporary files and renderer cache all live inside that new
external evidence directory. No preexisting evidence is deleted. Snapshot checking
is not an atomic filesystem snapshot; concurrent source editing is prohibited and
detected at inventory checkpoints. Changes made and reverted between checkpoints
are outside that guarantee. Precommit overlays still are not committed revisions.

The runner records every attempted command's argv, cwd, start/end time, wall time,
exit code or launch-error/timeout classification, error message, environment
allowlist and combined stdout/stderr hash. A missing executable has a null exit
code and explicit launch-error receipt, never an executed-test claim. A bounded
command timeout terminates its process group before stopping verification.

Environment policy is recorded in `environment-policy.json`. All `PYTHON*`,
`CMAKE_*`, `CTEST_*`, `GIT_*`, `OMP_*`, `GOMP_*` and `KMP_*` variables are removed
from inherited input, as are compiler/link flags and selectors (`CC`, `CXX`,
`CFLAGS`, `CXXFLAGS`, `CPPFLAGS`, `LDFLAGS`), sanitizer options, Matplotlib controls,
loader/include/library search overrides, Make flags, shell startup overrides and
temporary-directory overrides. Only removed variable names are recorded, not
potentially sensitive values. The runner sets Python no-bytecode/no-user-site and
hash seed 0, Agg with an evidence-local cache, evidence-local TMPDIR, C.UTF-8, UTC
and Git optional locks off. Sanitizer flags/options are supplied explicitly for
the sanitizer run. CTest's per-test OpenMP environments still apply unchanged.
Other OS environment is inherited; PATH and HOME are recorded only as SHA-256.
The argv tool versions, selected interpreter and exact pins are recorded separately.
This controls known influences without claiming a hermetic OS/container or dumping
credentials. A run outside this driver must establish its own environment policy.

Focused repair verification (outside the default 31-test suite):

```sh
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-repair-focused-new
python3 -B tools/validation/test_gate.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-repair-negative-new
python3 -B tools/validation/test_compatibility.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-repair-compatibility-new
python3 -B tools/validation/clean_checkout.py --revision a6c6266 --include-working-tree --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-repair-isolated-new
```

Use fresh output names each time. Run the isolated driver outside a ptrace sandbox
when required by LeakSanitizer; it does not bypass execution permissions itself.
Original negative fixtures still simulate failures without modifying the approved
environment. The compatibility fixture configures a source path containing spaces,
an apostrophe and Unicode and checks full, minimal, library-only and optional modes.
No production source, test timeout, dependency specification or CI workflow changes.
The TSan acceptance gate remains unmet; these tests establish neither race freedom
nor general deadlock freedom. Results of the repaired run are recorded separately
below and in the research log after actual completion.

## Resumed final repair verification — 2026-10-29

The resumed final source passed 15/15 focused checks, all six negative configure
fixtures and compatibility checks (31 full / 27 minimal / 0 library / 37 optional).
Real CTest exit-zero disabled/skipped results were rejected. Additional fixtures
confirmed binary/type/target mutations and OSError launch failures cannot silently
pass. No dependency installation or production change was needed.

Fresh isolated evidence: `/tmp/dynagraph-phase5c3b1r-resume-isolated-20261029`.
Debug, Release and ASan+UBSan each produced exactly 31/31 actual accepted passes,
sequentially, with leak detection enabled; CTest process wall times were
47.393872 / 41.860162 / 80.606576 seconds. Raw JUnit, exact-name registrations,
per-test acceptance, command receipts, environment policy, typed inventory/binary
patch and verified evidence hashes are retained there. Both final inventory checks
passed. Only outcome documentation changed after completion.

Use the commands in the research log with new output names to reproduce. Prior
repair /tmp evidence cited above was absent at recovery; these fresh runs establish
the resumed result. The original results/validation evidence remains untouched.
No commit/push/PR or Phase 5C-3B-2 work occurred. Independent read-only audit is next;
the TSan gate remains unmet.

## Phase 5C-3B-2: CI contract and bounded pipeline

This phase is authorized after conditional approval of 5C-3B-1R. Historical
observations above remain historical; the implemented workflow below has not yet
been executed on GitHub. Local execution does not establish hosted CI parity.

### Registration schema closure

All registration JSON decoding (including configure-time name arrays) rejects
object-key duplication at every nesting level and nonfinite numeric values.
Duplicate DISABLED value keys cannot be overwritten by the decoder. Required
ctestInfo/version/tests/name/properties checks remain unchanged. When present,
command must be a nonempty string array with a nonempty executable; backtrace is
a nonnegative integer. Optional backtraceGraph commands/files are string arrays,
nodes are objects, and supplied command/file/parent indices must reference valid
arrays; line is a positive integer. These optional fields are not required of
legitimate pre-build CTest output.

Supported property metadata receives type validation: ENVIRONMENT, LABELS,
regular-expression lists, DEPENDS, fixture lists, RESOURCE_LOCK,
ENVIRONMENT_MODIFICATION and REQUIRED_FILES are string arrays; TIMEOUT, PROCESSORS
and COST are finite nonnegative numbers; WORKING_DIRECTORY is a string;
SKIP_RETURN_CODE is an integer; DISABLED/WILL_FAIL/RUN_SERIAL use the documented
CMake boolean encodings. Unknown properties/extensions remain opaque JSON values;
this is explicit validation of supported metadata, not a complete future CTest
schema implementation. Mandatory/optional name reconciliation is unchanged.

### Hosted CI configuration

The existing gcc Debug/Release matrix and sanitize job remain. Each uses
ubuntu-24.04 and actions/setup-python CPython 3.13, provisions a new venv outside
the checkout, installs all eleven unchanged requirements with
`--only-binary=:all:`, and runs pip check. Installation is part of the explicitly
authorized hosted workflow; local verification uses the existing approved venv
without installing or upgrading anything. Install/check/freeze logs are uploaded.
Checkout fetches full history so the retained Git-overlay regression can resolve
its reviewed a6c6266 base even after newer commits are published.

The compiled dependencies publish CPython 3.13 manylinux x86_64 wheels compatible
with this runner: [NumPy](https://pypi.org/project/numpy/2.4.1/#files),
[Matplotlib](https://pypi.org/project/matplotlib/3.10.8/#files),
[ContourPy](https://pypi.org/project/contourpy/1.3.3/#files),
[kiwisolver](https://pypi.org/project/kiwisolver/1.4.9/#files) and
[Pillow](https://pypi.org/project/pillow/12.1.0/#files). Package publication is
compatibility evidence, not proof of a successful hosted installation. Pip
resolution, availability and runner setup must still succeed on GitHub.

`tools/validation/ci_verify.py` configures a fresh external build, enables full
validation and warnings as errors, requires exactly the 31 mandatory names with
all optional tiers off, builds with two jobs, and runs CTest with parallel=1 and
fresh JUnit output. The existing strict execution checker requires 31 actual
passes; exit zero alone is insufficient. Sanitizers retain matching ASan/UBSan
compile/link flags, leak detection and halt-on-error options. Existing per-test
timeouts are unchanged. gcc jobs also run the standalone repair fixtures.

Receipts preserve command argv/cwd, environment policy, output hashes, exits and
timestamps. Environment/toolchain logs and a typed source identity accompany raw
registrations, JUnit, per-test acceptance and failure diagnostics. Artifact upload
uses always(), retaining partial evidence on failure where the runner remains
available; builds and temporary directories are excluded. Release additionally
runs the smoke pipeline and negative controls. Hosted jobs may run concurrently;
CTest within each job is sequential. No CI job was removed.

Local reproduction with fresh output names:

```sh
python3 -B tools/validation/test_repair.py --output /tmp/dynagraph-3b2-focused-new
python3 -B tools/validation/test_compatibility.py --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b2-compatibility-new
python3 -B tools/validation/ci_verify.py --mode debug --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b2-debug-new
python3 -B tools/validation/ci_verify.py --mode release --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b2-release-new --smoke
python3 -B tools/validation/ci_verify.py --mode sanitize --python "$PWD/.venv-analysis/bin/python" --output /tmp/dynagraph-3b2-sanitize-new
```

Use the authorized outside-sandbox mechanism for LeakSanitizer when needed; never
turn off leak detection. No script bypasses execution permissions.

### Smoke stages and artifact provenance

The smoke uses the checked-in chain recipe: 8 vertices, 7 directed edges, 12
updates and fixed seeds. The existing generate.py generates and verifies the
canonical bundle, SHA-256 values, regenerated recipe, independent ledger replay
and final graph. Existing run.py executes all four compiled policies with full
preflight checks, four balanced blocks, one warmup, two requested workers and
16 trials in each of full-trace and per-update modes. Existing run.py validate
requires complete datasets and worker evidence. Existing analyze.py validates
both inputs, produces descriptive tables, and renders all seven requested figure
types in SVG and PDF (14 products). No generation/replay/timing/analysis logic is
reimplemented or measurement definitions changed.

```sh
.venv-analysis/bin/python -B tools/validation/smoke_pipeline.py --runner /path/to/built/dynagraph_bench --output /tmp/dynagraph-pipeline-new
.venv-analysis/bin/python -B tools/validation/test_smoke.py --pipeline /tmp/dynagraph-pipeline-new --output /tmp/dynagraph-pipeline-negative-new
```

The smoke must itself run under the approved pinned interpreter; an unpinned
interpreter fails the environment gate before generation. All products stay in
new external directories. Plans and artifact inventories use relative paths;
exact command receipts retain actual absolute paths for provenance. Source Git
revision/dirty state and typed source inventory are distinct from the executable
SHA-256 and worker-recorded build metadata. Compiler/CMake identities, Python/pins,
workload manifest hashes, both dataset hashes, analysis output digests and figure
digests are retained. No certificate linking an arbitrary externally supplied
binary to source is claimed; the CI driver builds its supplied binary freshly.

pipeline_artifacts.py checks all analysis-manifest output hashes, complete
acceptance of both inputs, and every required figure type/format. SVG checks parse
XML, require finite positive viewBox dimensions and drawn paths. PDF checks inspect
Matplotlib output signatures, page/catalog markers, EOF and cross-reference table
location; these are bounded structural checks, not general PDF conformance or
visual correctness certification. A final recursive evidence-sha256.json inventories
all files except itself and is immediately reverified. Original bundle, executable
and source inventories must remain unchanged at completion. SHA-256 supplies
integrity checks, never producer authentication.

Nine retained negative controls use disposable copies: changed workload bytes,
incorrect manifest hash, semantically incomplete preflight replay with refreshed
output hash, missing latency observation with resequenced records, invalid dataset
schema, missing figure, malformed SVG/PDF with consistent refreshed digests, and
incorrect artifact digest. A failed stage cannot produce pipeline-result.json
status complete; raw logs/failure receipts are preserved.

All smoke timings and descriptive ratios are harness-only checks. They establish
neither performance/scalability nor independent replication. The environment is
not hermetic; checkpoint snapshots are not atomic. TSan acceptance remains unmet.
Stop after local verification for independent review; Phase 5C-3B-3 is deferred.

### Actual Phase 5C-3B-2 local outcomes

On 2026-10-29 the final parser/repair suite passed 17/17; all six negative configure
fixtures passed; full/minimal/library/optional modes reconciled 31/27/0/37 names.
The final workflow passed local YAML structure and five shell syntax checks.
No actionlint or hosted execution was available. A first smoke invocation under
system Python correctly failed missing pinned matplotlib; that evidence is retained.

Fresh sequential local CI-driver legs accepted Debug 31/31, Release 31/31 and
ASan+UBSan 31/31 with leak detection enabled. Evidence roots are
`/tmp/dynagraph-phase5c3b2-ci-debug-final`,
`/tmp/dynagraph-phase5c3b2-ci-release-final` and
`/tmp/dynagraph-phase5c3b2-ci-sanitize-final`. Release's `pipeline/` contains the
successful 16-trial datasets for each timing mode and all 14 figures;
`pipeline-negative/` retains all nine rejected controls. Raw logs, JUnit, exact
commands, source identities and hash inventories were independently reconciled.
Only outcome documentation changed after verification. See the research log for
all commands, development attempts and focused evidence paths.

The chain recipe and order are deterministic; run IDs, timestamps, actual timings
and dependent output hashes vary. Local Python is 3.14.2; the hosted 3.13 environment
is still unexecuted. No hosted CI pass, cross-platform bitwise reproducibility,
producer authentication or performance claim is made. All hosted job logs and
uploaded evidence require later review after an authorized CI trigger. Stop for
independent review; no commit, push, PR or Phase 5C-3B-3 work occurred.

## Phase 5C-3B-3: portable evidence and offline review

The resumed phase is explicitly authorized by the user. Earlier stop/deferred
statements above describe historical gates. Phase 6 remains deferred.

Recovery found the Phase 5C-3B-2 implementation intact, one worker-argv wording
correction in the research log, and partial negative-diagnostic assertions with
`test_negative_diagnostics.py`. No archive implementation existed;
`pipeline_artifacts.py` predates this phase and validates smoke products only.
Stage-level argv is recorded; child worker argv is reconstructible from retained
source/configuration/identities but is not individually serialized. Worker exits
and stdout/stderr digests remain available in existing orchestration evidence.

All nine negative controls now require their intended diagnostic. The five CLI
controls also require an executed exit 2; unrelated failures and launch errors
cannot satisfy acceptance. The standalone diagnostic regression is outside CTest.

`ci_verify.py` now automatically creates a sibling `<output>.tar.gz` after a
completed leg, using `evidence_archive.py`. The archive contains selected evidence,
the complete captured source snapshot, an offline verifier kit and a complete
file/size/mode/SHA-256 manifest. Top-level build products, tmp and renderer caches are
excluded. Nested pipeline files referenced by its hash inventory, including its
renderer cache, are retained. Raw partial evidence is retained when a leg fails; failed legs do not
produce a successful validation archive. CI uploads both tarballs and raw evidence
using always(). Hosted execution and artifact-service behavior remain unverified.

```sh
python3 -B tools/validation/test_negative_diagnostics.py
python3 -B tools/validation/test_archive.py
python3 -B tools/validation/evidence_archive.py --create /tmp/completed-leg --source "$PWD" --output /tmp/completed-leg-review.tar.gz
python3 -B tools/validation/evidence_archive.py --verify /tmp/completed-leg-review.tar.gz
```

Creation requires the current source bytes and modes to match the captured source
identity; use the retained matching snapshot for historical evidence. It refuses
existing output and does not alter input evidence. This archive contract covers
completed `ci_verify.py` legs, not arbitrary historical evidence directory layouts.
The historical clean-checkout driver retains its own format.

For independent offline review, copy the verifier kit (the files listed by `KIT`
in evidence_archive.py) to a separate directory and copy the archive there. From an unrelated working directory, use the explicit isolated launcher below.
Python isolated mode does not add the script folder to sys.path; the launcher
adds only the copied verifier kit:

```sh
python3 -I -B -c 'import runpy,sys; kit=sys.argv.pop(1); sys.path.insert(0,kit); runpy.run_path(kit+"/evidence_archive.py",run_name="__main__")' /path/to/kit --verify /path/to/copied.tar.gz
```

Use a separately reviewed kit: code transported inside an archive is not a trust
anchor. Verification requires only Python >=3.8 and its standard library, no Git,
compiler, build tree, pinned rendering packages, network or original checkout.
Absolute paths in command receipts are historical strings and are never executed
or opened by the verifier. The verifier checks raw registrations and JUnit against
its mandatory-name contract, source inventory bytes/modes and canonical inventory
identity, receipts/log hashes, sanitizer options, smoke/analysis products and
intended negative-control logs. It does not rerun scientific computations or certify
that an externally supplied binary was built from the recorded source.

Archive members must be canonical relative POSIX paths without parent traversal,
backslashes, colons or control characters. Duplicate members, parent-file
collisions, symlinks, hard links, directories, devices, FIFOs, unsupported types and
special permission bits are rejected before extraction. Files are manually copied
into a new temporary directory; extractall is never used. The format supports at
most 50,000 regular members and 1 GiB total declared payload. Regular-file modes,
including executable bits, are preserved and verified. Source snapshots containing
symlinks supported by the older overlay mechanism are deliberately unsupported by
this stricter archive format. Directory modes, ACLs, xattrs and ownership are not
preserved. Archives are portable for integrity review, not bitwise reproducible
builds or authenticated distribution. Keep external archive digests when copying.

See [research-validation release-readiness checklist](research-validation-checklist.md).
Stop for independent review after local verification. TSan acceptance remains unmet.

### Phase 5C-3B-3 recovery outcomes — 2026-10-29

Focused checks passed: 17 repair tests, 3 intended-diagnostic tests, 12 archive
regressions (including unsafe/duplicate/type/link fixtures and executable modes),
six configure failures, and 31/27/0/37 full/minimal/library/optional registrations.
All validation modules parse with Python 3.8 grammar. Local YAML parsing and all
six workflow shell syntax checks passed; no hosted CI execution was performed.

Fresh sequential evidence is retained at:

- `/tmp/dynagraph-3b3-debug-final`: 31/31, CTest process wall 46.524112 s.
- `/tmp/dynagraph-3b3-release-final`: 31/31, 41.546065 s; both 16-trial datasets,
  all 14 figures and all nine intended negative-control diagnostics passed.
- `/tmp/dynagraph-3b3-sanitize-final`: 31/31, 79.471757 s, outside sandbox with
  ASan+UBSan, leak detection and halt-on-error options enabled.

The first recovery Debug leg also passed. The first recovery Release leg passed
31/31 plus smoke/controls but its archive attempt failed because staging omitted
an inventory-referenced renderer cache. That evidence is preserved at
`/tmp/dynagraph-3b3-release-recovery`; the packaging defect was fixed, a focused
regression added and fresh Debug/Release/sanitizer legs run sequentially. The first
Release evidence was also successfully repackaged using its matching source
restored from the verified first Debug archive. No suite failure was relabeled.

After the final suites, two offline-only consistency checks were added: identity
metadata must agree with raw Git receipts, and declared build mode must agree
with configure flags. The 12-test archive regression passed, and these stricter
checks were applied directly to all retained final raw evidence, without rerunning
CTest. The mandatory JUnit checker, driver, CMake, algorithms and compiled tests
were unchanged by this final strengthening. These two verifier/test file edits,
and subsequent outcome documentation, postdate the suite snapshot; they are not
claimed to have been in that snapshot.

Current stricter creator generated `/tmp/dynagraph-3b3-{debug,release,sanitize}-review.tar.gz`
from those real final evidence directories and their matching source snapshot
restored at `/tmp/dynagraph-3b3-tested-source`. These review archives contain that
actual tested source and a separately inventoried current verifier kit. Source
inventory SHA-256 is `d5044e422ff6cba438a6e9a49720276435906116eba6d1377b0da03471293922`.
All three copied review archives passed independently in `/tmp/dynagraph-3b3-offline`
with Python isolated mode, a copied kit, and an audit guard rejecting `/workspaces`
opens, network and subprocess use. The guard explicitly demonstrated checkout
access denial. A copied real archive missing its JUnit member was rejected.

`/tmp/dynagraph-3b3-focused/reconciliation.json` records archive SHA-256, member
counts, sizes, accepted results and sequential receipt reconciliation;
`/tmp/dynagraph-3b3-offline/offline-results.json` records the offline commands and
transfer hashes. Focused logs, repair/configure/compatibility fixtures and every
prior attempt remain in their separate `/tmp/dynagraph-3b3-*` directories.
Historical ignored `results/validation/` evidence remains unchanged. Previous
phase `/tmp` evidence was absent at recovery; it was not assumed to survive.
Copy these fresh external artifacts to durable storage before another Codespace
lifecycle interruption. No dependency installation, commit, push or PR occurred.

Local evidence is ready for independent review. Hosted CI provisioning, execution,
uploads and externally reviewed archive acceptance remain pending. The checklist
is an independent review gate, not an assertion that release approval is complete.
Phase 6 remains deferred and the TSan gate remains unmet.

## Phase 5C-3B-3R: repaired archive acceptance contract

The final independent Phase 5C-3B-3 audit was **BLOCKED** despite genuine passing
suites. Refreshing manifests could hide the full-trace dataset, pipeline receipts
or environment policy; a contradictory failure.json was accepted; and tar
iteration accepted a gzip stream missing its footer. Malformed-input diagnostics,
adversarial coverage, the offline command and missing digest sidecars also needed
repair. These findings and all original evidence remain historical; the repaired
contract below supersedes the earlier archive format and readiness statement.

### Profiles and mandatory evidence

Format v2 requires an object manifest with schema_version exactly integer 2,
integrity_only true, a supported profile and a complete regular-file inventory
(path, size, mode, SHA-256). Inventory equality is checked, but is never used as
the definition of mandatory evidence. Unknown schema/profile combinations fail.
The archive also requires the complete separately inventoried verifier kit.

| Profile | Required successful validation |
|---|---|
| debug-full-v1 | Debug, smoke false, all 31 mandatory registrations and actual passes |
| release-smoke-v1 | Release, smoke true, all 31 passes plus the complete bounded pipeline and nine intended controls |
| sanitize-full-v1 | Debug build with matching ASan+UBSan compile/link flags, smoke false, all 31 passes and leak/halt options |
| failed-run-v1 | Integrity review of an explicitly failed/interrupted run; never a passing validation |

Every success profile requires result.json, source-identity.json, commands.json,
environment-policy.json, evidence-sha256.json, execution.xml, acceptance.json and
all required command logs. The raw Git revision/status/file lists must reconcile
with the complete captured source inventory and its canonical identity hash.
Tracked deletions require an explicit matching D status; quoted deletion paths
are currently unsupported by this archive contract (the older overlay mechanism
is unchanged). Pinned environment output is checked against the archived source's
unchanged requirements. Configure settings must match the profile; duplicate
settings are rejected. JUnit and exact registrations are independently reconciled.

The full-leg receipt sequence is exactly:
`revision`, `status`, `source-files`, `environment`, `cmake-version`, `ctest-version`,
`g++-version`, `configure`, `registration`, `build`, `ctest`, then (Release only)
`pipeline`, `pipeline-negative`, and finally `source-files-final`.
All receipts require argv, cwd, environment, classification, exit/error, finite
ordered start/end/wall times and matching named log hashes. Success requires
executed exit 0 with no error. The top-level evidence digest inventory must cover
all selected top-level regular evidence files, except itself.

Release additionally requires pipeline-result.json, analysis-plan.json, source
identity, environment policy, commands, recursive evidence inventory, the original
bundle and both timing-mode configs/datasets. Dataset hash keys must be exactly
full-trace and per-update; bundle keys exactly graph.txt, trace.txt and manifest.json.
For each mode, require records.jsonl, executable runner with executable mode,
artifact-verification.json, the staged workload's three files, and stdout/stderr/
exit receipts for four preflights and all sixteen trials. The current trusted
copies of experiment_records.py/artifacts.py/workloads.py/deterministic.py validate
the complete datasets and independent replay offline. Workload bounds are fixed
at 8 vertices, 7 edges and 12 updates before replay computation.

The mandatory pipeline receipt sequence, derived from smoke_pipeline.py, is:
`revision`, `status`, `source-files`, `environment`, `cmake-version`, `g++-version`,
`generate`, `verify-workload`, `full-trace-run`, `full-trace-validate`, `per-update-run`,
`per-update-validate`, `analyze`, `source-files-final`. Workload verification and
both validation logs must report their actual expected completed results.
Analysis requires the existing tables/report/summaries/manifest and exactly the
fourteen expected SVG/PDF figure products. Both acceptance.jsonl entries must
accept the correct modes and reconcile their complete actual input inventories;
the analysis plan's digest must match. PDF inspection remains structural only.

Negative controls require their environment policy, five ordered CLI receipts,
all nine logs and nine intended rejection results. CLI receipts must demonstrate
executed exit 2 and intended diagnostics. The four in-process figure controls
require their intended diagnostic logs. No benchmark semantics are reimplemented.

### Terminal classifications and failed evidence

Any failure.json anywhere in success evidence contradicts a passing archive.
Profile/result mismatch, skipped/failed/incomplete mandatory results, failed stage
receipts and conflicting nested smoke classifications are rejected. Non-smoke
profiles reject unexpected pipeline directories, so relabeling cannot bypass
Release requirements.

failed-run-v1 requires a captured source identity with its initial Git receipts,
environment policy, commands/logs, complete selected top-level hash inventory and
failure.json with status failed, a nonempty diagnostic and explicit classification
command-failed, validation-rejected or interrupted. Receipts must form a supported
full-leg prefix and preserve stop-on-failure progression. command-failed needs a
failed receipt. A completed overall result contradicts this profile. A completed
pipeline is allowed only when its parent stage actually succeeded before a later
failure. Earlier valid stage results are retained as diagnostic context.

A valid failed archive returns status integrity-verified, validation_status failed
and its failure classification; it makes no passed-test-count claim. CLI exit 0
means the **failed evidence's integrity** verified, not that validation passed.
The CI driver still raises its original validation failure and exits nonzero.
Failure before source capture, source drift or contradictory/unreadable diagnostic
evidence may prevent this supported archive profile; raw evidence is still kept
and uploaded where feasible. The tool does not synthesize missing source/evidence.

### Gzip/tar policy and bounds

archive_transport.py fully drains exactly one gzip member with bounded zlib output.
Termination, CRC32 and ISIZE are checked before tar parsing. Missing trailers,
truncation, bad CRC/size and any trailing compressed bytes, including concatenated
members or zero suffixes, fail. No gzip concatenation is supported.

Expanded tar is preflighted using fixed 512-byte headers before extraction.
Header checksums, payload boundaries, zero padding, two complete zero end blocks
and block alignment are mandatory. Zero record padding after the terminator is
allowed; nonzero trailing tar data is rejected. Only regular files and bounded
local PAX path/mtime metadata are supported. Global PAX, GNU extensions, sparse
files, duplicate PAX keys and size/type overrides are rejected. Metadata is bounded
**before** reading/parsing it; untrusted archives never reach tarfile's automatic
PAX expansion or extractall. Duplicate paths, unsafe names, parent-file collisions,
links, special types and special permission bits are rejected before extraction.

Limits: 256 MiB compressed, 1 GiB expanded including headers/metadata/padding,
128 MiB per regular member, 50,000 regular members, 64 KiB per local PAX header,
4 MiB total PAX payload and 4096 UTF-8 bytes per path. JSON evidence is capped at
16 MiB and 64 levels; smoke datasets and analysis acceptance are capped at 16 MiB.
This is a documented supported-format restriction, not a claim to parse all tar
variants safely. Disk availability may cause a controlled OSError before reaching
these limits. Extraction uses a private temporary directory and regular files;
original evidence is never extracted over. POSIX regular-file modes are preserved
and checked; ownership, directory modes, ACLs and xattrs are not preserved. Tested
on Linux; Windows execution/mode compatibility is not certified.

### Sidecars and exact offline invocation

Every newly created successful or supported failed archive gets a sibling
`<archive>.sha256`, computed from the completed, reopened archive. It contains a
lowercase SHA-256, two spaces and the correct archive basename (UTF-8). Both outputs
must be new. Copy both files together and verify using standard tools:

```sh
cd /path/to/copied-artifacts
sha256sum -c evidence.tar.gz.sha256
```

The verifier can additionally check the pair with --sidecar. A mismatched digest
or basename is rejected. Sidecars detect transfer changes; they do not authenticate
the producer. CI uploads success/failed tarballs and sidecars alongside raw evidence
using always(). No actual hosted provisioning/upload success is claimed locally.

Copy the reviewed KIT files to a standalone directory (four established benchmark
validator modules are copied flat beside the validation modules). Do not execute
unreviewed code from an untrusted archive. The corrected exact command removes
the kit argument before argparse; it is covered by a focused subprocess regression:

```sh
python3 -I -B -c 'import runpy,sys; kit=sys.argv.pop(1); sys.path.insert(0,kit); runpy.run_path(kit+"/evidence_archive.py",run_name="__main__")' /path/to/kit --verify /path/to/copied-artifacts/evidence.tar.gz --sidecar /path/to/copied-artifacts/evidence.tar.gz.sha256
```

Only Python >=3.8 and its standard library are needed. The kit never executes
archived source or binaries, launches compilers/processes, installs packages or
uses a network. Absolute provenance paths remain historical strings. Worker argv
remains reconstructible, not individually serialized. SHA-256/source identity is
not a cryptographic source-to-binary certificate. Non-hermetic environment and
non-atomic snapshot limitations persist. TSan acceptance remains unmet.

### Actual Phase 5C-3B-3R local outcomes

The final implementation passed 39 diagnostic-specific archive tests, 3 diagnostic
controls and 17 repair tests. All six negative configure fixtures and registration
compatibility counts 31/27/0/37 remained intact. Exact offline-launcher, standard
sha256sum, Unicode sidecar and executable-mode regressions passed.

Genuine original Debug/Release/sanitizer evidence was repackaged without altering
it, using its matching source identity
`d5044e422ff6cba438a6e9a49720276435906116eba6d1377b0da03471293922`.
All three current-contract archives and copied sidecars passed the exact documented
launcher and a separate checkout/venv/network/subprocess-denied guard using system
Python 3.12.3 with site packages disabled. No artifact was fabricated or regenerated
to fill a missing retained requirement. Actual executable modes, including 0757
on retained worker binaries, matched the archives exactly.

Because acceptance and CI integration changed, fresh sequential full CI-driver
legs were also run with new external directories and no source edits during runs:

| Evidence directory | Actual passing tests | CTest process wall seconds |
|---|---:|---:|
| /tmp/dynagraph-3b3r-debug-final | 31/31 | 49.598802 |
| /tmp/dynagraph-3b3r-release-final | 31/31 | 50.509218 |
| /tmp/dynagraph-3b3r-sanitize-final | 31/31 | 85.042869 |

Release completed both 16-trial datasets, all 14 figures and nine intended negative
controls. Sanitizer ran outside the sandbox with leak detection and halt options.
All three captured source identity
`76a49ecd77378a0aacafc30d98f9e640b5aaeaf64d638eca8af24f228c52fceb`.
Each automatically generated/reopened its format-v2 archive and sidecar. All three
fresh copied pairs passed sha256sum -c, the exact corrected isolated command and
the independent denied-access system-Python guard. The current trusted kit bytes
match the verifier members in every fresh archive. Only outcome documentation
changed afterward; no implementation/test edit postdates this suite snapshot.

An intentional driver launch failure also produced a separately classified final
failed-run archive. The driver exited 1; offline integrity verification exited 0
with validation_status failed and no passed-count claim. It captured the same
76a49e... source identity. This infrastructure negative is distinct from the
three passing algorithm suites and remains explicitly labeled.

New ignored preservation directory `results/validation/phase5c3b3r/` retains final
and intermediate archive/sidecar pairs, copied offline kit/commands/logs, raw
configure/compatibility diagnostics, focused results, original changed-file backup
and final reconciliation. Its preservation manifests record file SHA-256 values.
Original external /tmp evidence, failed attempts and historical results/validation
remain untouched. Full build trees remain external; complete selected raw evidence
is also inside each portable archive. See the research log for exact commands and
archive hashes. Keep a durable copy before another Codespace lifecycle interruption.

Local implementation/evidence are ready for independent re-audit. Hosted CI
provisioning, all three hosted jobs and artifact-service behavior remain pending.
TSan acceptance remains unmet. No dependency installation, commit, push, PR or
Phase 6 work occurred.

## Phase 5C-3B-3R2: canonical configure receipts and bounded times

The subsequent independent 3R re-audit confirmed the original six archive defects
closed, but remained BLOCKED: the configure checker recognized joined definitions
while silently ignoring later split-form -D overrides. Native CMake could therefore
select Release, disable full validation and empty sanitizer flags while the checker
accepted the claimed profile. A 400-digit receipt timestamp also caused an uncaught
OverflowError during int-to-float conversion. This narrow repair changes offline
verification and regression fixtures only; the actual ci_verify.py producer, CI,
CMake, compiled algorithms, workload formats, pins and timeouts remain unchanged.
The previous passing raw evidence remains applicable and is reverified with the
new checker; it is not presented as a fresh execution of changed C++ code.

### Accepted configure argv

The success-profile contract is exactly the current producer's representation,
not a general CMake parser. There must be 13 argv elements for Debug/Release or
15 for sanitizer, in this order (each quoted string below is one argument):

```text
"cmake", "-S", SOURCE, "-B", BUILD, "-G", "Unix Makefiles",
"-DCMAKE_CXX_COMPILER=g++",
"-DCMAKE_BUILD_TYPE=Debug",                  # Release profile uses Release
"-DBUILD_TESTING=ON",
"-DDYNAGRAPH_WARNINGS_AS_ERRORS=ON",
"-DDYNAGRAPH_FULL_VALIDATION=ON",
"-DDYNAGRAPH_ANALYSIS_PYTHON=" + PYTHON
```

Sanitizer requires the Debug build type and exactly two additional arguments:

```text
"-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
"-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"
```

SOURCE, BUILD and PYTHON must be lexically canonical absolute POSIX path strings
without control characters, parent traversal or redundant separators/components.
SOURCE and BUILD must differ; SOURCE must equal the recorded configure cwd.
Spaces, apostrophes and Unicode are data, not shell syntax. Historical paths and
interpreter symlinks are never resolved or opened by this check, preserving offline
operation and virtual-environment interpreter identity. The executable is the
literal cmake and the generator is the literal Unix Makefiles, matching the real
producer. Other representations require an explicit future contract change.

All definitions must be joined -DKEY=value with an uppercase allowlisted key.
Every key must occur exactly once in the documented order. Identical as well as
contradictory duplicates fail. Split -D KEY=value forms, lone -D, missing values,
typed KEY:TYPE definitions, malformed tokens, unknown keys and any extra options
or positional arguments fail. No argument is silently skipped. This excludes
-C cache preloads, -U removal, presets, toolchain options, script modes, extra
-G/-S/-B options and unallowlisted cache variables such as CMAKE_CXX_FLAGS_DEBUG
or project/toolchain injection settings. Protected values are compared exactly;
sanitizer flags cannot be removed, emptied, replaced or overridden. The interpreter
path is the one variable definition value, subject to the lexical path checks.

Available retained CMakeCache.txt files may corroborate actual effective build type,
full-validation and sanitizer settings during local review. The current archives
exclude build trees and contain no cache, so the offline verifier neither invents
one nor follows recorded paths to find one. A cache is self-reported build evidence,
not independent proof or a source-to-binary certificate. Failed-run archives can
preserve an invalid configure attempt as diagnostic evidence; they still never
report successful validation and are not forced into a successful argv profile.

### Receipt time contract

start_unix, end_unix and wall_seconds must have exact JSON numeric types int or
float; booleans, strings, null and containers are rejected. Floats must be finite.
Every value must be in [0, 253402300799] seconds, inclusive: the last whole Unix
second in UTC year 9999, also used as a broad upper bound for recorded durations.
Fractional seconds within that range are accepted. Integer bounds are checked
without converting integers to float, including arbitrarily large JSON integers.
Finite/ordering checks and sequential receipt progression remain intact. This is
an evidence-data bound; no execution or CTest timeout changed.

Errors distinguish invalid numeric type, nonfinite value and out-of-range value,
including the receipt name and field. Strict JSON decoding additionally rejects
NaN/Infinity tokens before field validation. The oversized-integer CLI regression
requires exit 1 with `Archive rejected: command receipt time out of range:` and
no traceback. No blanket exception suppression was introduced.

### Narrow verification and retained evidence

The regression fixture producer now emits the same canonical argv shape as the
real producer. All original 39 archive tests pass with that fixture. Twenty added
test methods cover the three positive profiles, all four split override cases,
identical/conflicting joined duplicates, missing/malformed/typed definitions,
unsupported override mechanisms, empty/missing sanitizer flags, protected values,
canonical paths/order and ordinary/oversized/nonfinite/incorrectly typed times.
Negative archives preserve otherwise valid evidence and refresh the supplied file,
evidence and archive inventories/hashes so the intended contract check rejects them.

Historical evidence and all 29 original working-tree files remain preserved.
New local records are kept under ignored results/validation/phase5c3b3r2, separately
from every previous attempt. Exact final outcomes, source identities, cache
corroboration and the decision against unnecessary C++ reruns appear in the research
log. Hosted CI and TSan acceptance remain pending/unmet. Stop after local verification
for narrow independent re-audit; no commit, push, PR or Phase 6 is authorized here.

Recovery on 2026-10-29 confirmed both repairs and their tests already complete in
the interrupted working tree. Final reconciliation was incomplete; inspected prior
test logs all had terminal results. The recovery reran 59 archive tests and three
diagnostic controls successfully, verified all six retained successful archives
with SHA-256 sidecars, confirmed the failed archive remains classified failed,
and rejected seven retained adversarial archives with their expected diagnostics.
No C++ suite rerun or implementation change was needed. Exact commands, outputs,
archive hashes and the recovered file inventory are preserved separately under
`results/validation/phase5c3b3r2/recovery-20261029/`. Historical attempts remain
untouched. See the research log's recovery reconciliation for scope and limitations.
Local verification is complete; independent re-audit, hosted CI and the unmet
TSan gate retain their existing status. Phase 6 remains deferred.
