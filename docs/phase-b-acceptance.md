# Phase B acceptance — Phase 6B-2B-3B-4

**APPROVED for bounded development resource evidence.** All mandatory local gates
passed in GitHub Codespaces, based on be3588a, on
`feature/phase6b2b3b4-resource-interference`. Scientific eligibility remains false;
TSan acceptance remains unmet. No dependency changes, scientific campaign, push,
PR or merge occurred. Stop after the authorized local commit and report.

Raw evidence is ignored, preserved locally at
`results/validation/phase6b2b3b4-resource-interference/` (called `E` below).
`E/audit-sha256.json` inventories retained bytes. Full exact argv, working directory,
environment controls, exit results and log hashes are in `E/canonical/commands.json`,
`E/final/commands.json` and nested per-profile/pipeline/negative/compatibility
`commands.json` files. Driver scripts and their complete output are retained at E.
Build trees, source checkouts and caches are excluded from that retained copy;
source inventories, native raw artifacts, staged diagnostic runners, archives,
sidecars and logs remain available. Existing historical evidence was not rewritten.

| Mandatory gate | Actual evidence | Result |
| --- | --- | --- |
| Native architecture, bounded Linux facts and identity | Resource native/bound v1; workload v3 monotonic envelopes; four snapshots, sixteen paths maximum, sixty-four affinity CPUs, 1 MiB cap | PASS |
| Debug canonical full profile | `E/canonical/debug/acceptance.json`, execution.xml and reopened debug.tar.gz + sidecar | 31/31 CTests PASS |
| Release canonical full profile | `E/canonical/release/acceptance.json`, execution.xml and reopened release.tar.gz + sidecar | 31/31 CTests PASS |
| ASan+UBSan+LeakSanitizer canonical profile | `E/canonical/sanitize/acceptance.json`, execution.xml, archive/sidecar; detect_leaks=1, halt_on_error=1 | 31/31 CTests PASS |
| Final workload and resource diagnostic CTests | `E/final/{debug,release,sanitize}-ctest/{execution.xml,acceptance.json}`; 14 workload tests + 11 resource test groups inside two additional CTests per profile | 2/2 per profile PASS |
| Complete final campaign Python regressions | `E/final/campaign-python.log`, final/commands.json | 382/382 PASS |
| Combined optional registrations | `E/final/optional-full-registration.log` | Exactly 33 PASS; historical defaults remain 31 |
| Rendering and smoke | Release pipeline-result.json; per-update + full-trace, sixteen trials each; valid_harness_only | 32 smoke trials and 14 figures PASS |
| Smoke negative controls | Release pipeline-negative/negative-results.json | 9/9 correctly rejected |
| Full-environment/registration negative controls | canonical/environment-negatives/negative-results.json | 6/6 correctly rejected |
| Compatibility configurations | canonical/compatibility/outcomes.json | Quoted full 31, minimal 27, library-only 0, optional stress/extended 37; all PASS |
| Native Codespaces diagnostics | `E/final/native-summary.json`, resources-{debug,release,sanitize}/baseline/out | Six trials, complete coverage, all observed_interference from shared CPU PSI deltas |
| Journal/recovery/resume and failure states | `E/lifecycle/` original/child trees and lifecycle-summary.json | Completed original immutable, pending-only launch, renewed opt-in required; failed publication and post-GO interruption non-reusable |
| Original campaign contract | canonical/result.json | 104 trials; both required hashes unchanged |
| Historical evidence integrity | E/historical-preservation.json | 825 indexed artifact hashes checked, zero mismatches |
| Scientific and race-detector limits | All new bound artifacts and reports retain false flags | Scientific eligibility false; no TSan acceptance claim |

## Source and command provenance

The canonical profiles used one frozen overlay of the authorized branch, preserving
its base revision and dirty-source inventory. Final review then hardened only
`campaign_interference.py`, `campaign_resume.py` and
`test_campaign_interference.py`. A second frozen inventory validates those final
Python changes with both diagnostic CTest tiers in all three configurations and the
complete 382-test campaign suite. All **56 native/build source files match exactly**
between inventories (`E/final/source-inventory.json`). No final native change was
left untested. Final acceptance documentation was written after the checks.

Exact top-level commands executed:

```sh
.venv-analysis/bin/python -B /tmp/dynagraph-phase-b-validation.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-b-final-python.py
.venv-analysis/bin/python -B /tmp/dynagraph-phase-b-final2-python.py
DYNAGRAPH_PILOT_TEST_RUNNER=/tmp/dynagraph-phase-b-20261106/release/build/dynagraph_bench .venv-analysis/bin/python -B /tmp/dynagraph-phase-b-lifecycle.py
```

The first driver runs `ci_verify.py --mode debug`, `--mode release --smoke` and
`--mode sanitize`, archive reopening, separate diagnostics, full campaign discovery,
registration, `test_gate.py` and `test_compatibility.py`. All use fresh disjoint output
directories and the unchanged pinned interpreter. The final driver records its
frozen inventory and native-source equality, runs two diagnostic CTests per build,
then `python -B -m unittest discover -s <frozen>/tests -p 'test_campaign*.py'` and
full optional registration. The lifecycle command uses real enforcement/native
processes; coordinator interruption between trials, publication error and
post-GO KeyboardInterrupt are explicit fault injections. Ordinary R1/R2 regression
signal controls also pass in the full campaign suite. These are local results,
not hosted CI results.

Canonical sanitizer flags remain exactly
`-fsanitize=address,undefined -fno-omit-frame-pointer`, with linker
`-fsanitize=address,undefined`; runtime controls are
`ASAN_OPTIONS=detect_leaks=1:halt_on_error=1` and
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`.

Python 3.14.2 and Agg rendering passed the exact environment gate. No packages were
installed or changed. Observed pinned versions:

```text
matplotlib 3.10.8     numpy 2.4.1          contourpy 1.3.3
cycler 0.12.1         fonttools 4.61.1     kiwisolver 1.4.9
packaging 25.0        pillow 12.1.0        pyparsing 3.3.2
python-dateutil 2.9.0.post0                 six 1.17.0
```

## Adversarial coverage and corrections

The eleven final resource test groups cover native/offline/recovery consistency;
a synthetic stable-counter control; throttle/PSI increases; quota/cpuset/online,
inode/topology and pre-GO configuration changes; unavailable files, cgroup v1,
resets and excessive gaps; malformed numbers and Boolean integer substitutions;
truncated samples/JSON, stale process generation, wrong session/task/boot,
incorrect boundaries, errno/value contradictions and ancestry omissions; rehashed
false stability, cross-trial substitution, wrong workload/configuration binding,
missing publication and policy downgrade; unknown GO; real-child post-GO
interruption; failed publication; immutable resume reuse and renewed authorization;
explicit opt-in/timing exclusion; missing bound fields and loosened sampling policy.
Synthetic mutations are test controls, never original runtime observations.

Initial testing rejected the kernel's valid `core_sched.force_idle_usec` cpu.stat
extension; the bounded numeric extension parser was corrected. The first complete
campaign run found a KeyError rather than ValueError for a malformed native
workload document at the new version guard; corrected before final verification.
Final review added strict bound-shape/group/session checks, pre-GO policy comparison
and rejection of Boolean IDs. Earlier pass/failure logs are retained separately;
the final suite has no remaining failures or skipped mandatory gates.

## Native observations and preserved manifest

Each of the six final baseline trials sampled `/sys/fs/cgroup` and
`/sys/fs/cgroup/init`, requesting one or two workers. Four samples produced
57,709–57,878-byte native artifacts. Raw sample durations ranged from 743,439 to
7,189,692 ns in these diagnostics; those are collection observations, not benchmark
performance or portable overhead guarantees. Both `some` and `full` CPU PSI totals
increased. Every classification was `observed_interference`, coverage complete,
with no configuration changes or issues. Counters are shared and include the
observer, oracle and other cgroup processes; no causal attribution follows.

Required canonical plan SHA-256:
`f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24`.
Required expanded manifest SHA-256:
`f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a`.
The original plan, dependency pins and legacy resource-control contracts are unchanged.
New validation archives are current checks, not fabricated historical Phase 5 archives.

## Remaining limitations and next gate

There are no unresolved mandatory blockers for this bounded development phase.
Four samples emphasize the first delta region; gaps, missing facts, counter resets,
unsupported layouts or serial execution without a sampled region prevent complete
coverage. Hidden ancestors, between-sample configuration events, exclusive CPU
ownership, worker scheduling inside regions, physical-core scaling, producer
attestation, and absence of contention remain unproved. Known change/interference
with incomplete coverage cannot authorize completion. Full scientific eligibility
and TSan acceptance remain separate unmet gates. No later phase is authorized by
this approval; stop after reporting the local commit.

## Changed files

- `AGENTS.md`
- `CMakeLists.txt`
- `apps/dynagraph_bench.cpp`
- `benchmarks/python/campaign.py`
- `benchmarks/python/campaign_interference.py`
- `benchmarks/python/campaign_pilot.py`
- `benchmarks/python/campaign_resume.py`
- `benchmarks/python/campaign_workload.py`
- `docs/campaign-pilot.md`
- `docs/campaign-recovery.md`
- `docs/experimental-protocol.md`
- `docs/phase-b-acceptance.md`
- `docs/reproducibility-validation.md`
- `docs/research-log.md`
- `docs/resource-enforcement.md`
- `docs/resource-interference.md`
- `docs/workload-instrumentation.md`
- `include/dynagraph/instrumentation/resources.hpp`
- `include/dynagraph/instrumentation/workload.hpp`
- `src/instrumentation/resources.cpp`
- `src/instrumentation/workload.cpp`
- `tests/CMakeLists.txt`
- `tests/test_campaign_interference.py`
- `tools/validation/check_registration.py`
