# Phase 5C-2A isolated detector controls

These programs are investigation fixtures, deliberately absent from CMake,
CTest and CI. `ordinary_race.cpp` and `openmp_race.cpp` intentionally contain
undefined behavior to calibrate race detection. A normal exit is not a pass for
either positive control. `OMP_THREAD_LIMIT=1` serializes the OpenMP control and
cannot exercise its intended race.

The negative controls are `barrier_publication.cpp implicit|explicit` (vector
publication and repeated reuse, with OpenMP barriers) and
`atomic_publication.cpp` (release/acquire publication between ordinary threads).
All controls load libgomp, including the ordinary-thread controls, so their
runtime-library set matches the project. `project_work_probe.cpp 1|2` uses only
the public delta API and the existing independent Bellman–Ford helper. It checks
complete distances and reports actual team sizes after eight successful queries.

Run from the repository root with no existing investigation build/output records:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/tsan_controls/investigate.py build
PYTHONDONTWRITEBYTECODE=1 python3 tests/tsan_controls/investigate.py run --label sandbox
PYTHONDONTWRITEBYTECODE=1 python3 tests/tsan_controls/investigate.py run --label outside
PYTHONDONTWRITEBYTECODE=1 python3 tests/tsan_controls/investigate.py optional
PYTHONDONTWRITEBYTECODE=1 python3 tests/tsan_controls/investigate.py build --layout fixed
PYTHONDONTWRITEBYTECODE=1 python3 tests/tsan_controls/investigate.py run --layout fixed --label sandbox
PYTHONDONTWRITEBYTECODE=1 python3 tests/tsan_controls/investigate.py followup --layout fixed
PYTHONDONTWRITEBYTECODE=1 python3 tests/tsan_controls/summarize.py
```

`--label outside` only names records; the command must actually be launched
outside the sandbox to reproduce that execution context. It does not escape a
sandbox itself. This investigation used the execution tool's approved escalation
for that invocation. The fixed layout is a separate GCC-only diagnostic experiment
using `-fno-pie -no-pie`; the primary PIE evidence is retained. It is not a proposed
production or CI configuration and does not remove sanitizer instrumentation.

The driver refuses a preexisting build directory. Individual log files use
exclusive creation, and build failures stop the path. Commands, explicit runtime
settings, exit codes, timeouts and complete output streams are recorded separately.
Source/binary SHA-256 checks prevent running changed/stale binaries after build.
TSan startup mapping failures, signals, warnings and fixture failures are distinct
outcomes. No suppression or `ignore_noninstrumented_modules` option is used.

The 81-process matrix uses three repetitions, `OMP_DYNAMIC=FALSE`, and
`OMP_NUM_THREADS/OMP_THREAD_LIMIT` pairs `1/1`, `1/2`, `2/2`. Each setting runs
five control variants, the existing delta tests, both explicit-worker probes and
system correctness case 3/source 0. Timeouts are 15 seconds for controls/probes
and 30 seconds for existing tests. The existing delta fixture requires two actual
workers and therefore fails when constrained to one; that is recorded without
altering the fixture. The follow-up adds the existing isolated delta allocation
failure executable and diagnostic `halt_on_error=0` runs to retain later reports.

Generated evidence is ignored by Git under `build/tsan-5c2a*` and
`results/validation/phase5c2a*`. The investigation report is
`results/validation/phase5c2a/REPORT.md`, with complete per-configuration results
in `matrix.md`, `summary.json` and the individual `.json/.stdout/.stderr` records.
Do not register the intentional-race controls as normal tests.
