# Codespaces reproduction guide

This is the current end-to-end path. Detailed schema/validation contracts remain
in [the validation runbook](reproducibility-validation.md),
[the pilot runbook](campaign-pilot.md) and [Phase F acceptance](phase-f-acceptance.md).
Do not install dependencies or change manifests to make a step pass.

## Preconditions and opening the workspace

Open the repository's existing GitHub Codespace in the browser or VS Code and open
a Bash terminal. Starting/provisioning a Codespace is a manual platform prerequisite;
it was not re-provisioned during validation. No external experimental hardware,
service or network request is needed for the commands below in the existing workspace.
A fresh clone does **not** contain ignored historical evidence or the pinned venv.
If these are absent, stop the dependent evidence/rendering steps and obtain the
original retained bytes or explicit dependency-install permission; do not synthesize
historical records or silently use unpinned packages. Build/algorithm steps can run
with their own stated prerequisites independently.

All commands below run in **one Bash terminal**, working directory
`/workspaces/Dynagraph-HPC`. Outputs use a new short `/tmp` prefix to avoid Unix
socket pathname limits. Preserve its printed path; reruns need a new directory.

```sh
cd /workspaces/Dynagraph-HPC
pwd
git status --short --branch
git rev-parse HEAD
export DG_DOC_RUN="$(mktemp -d /tmp/dgf-demo.XXXXXX)"
export DG_BUILD="$DG_DOC_RUN/b"
export DG_PY="$PWD/.venv-analysis/bin/python"
printf '%s\n' "$DG_DOC_RUN"
```

Phase F validation started clean on `feature/phase-f-final-documentation` at
`0b660ec`; later documentation commits naturally change HEAD. The generated output
directory is never an input to a scientific campaign or a replacement for old evidence.

## 1. Check the environment

Needs existing GCC/OpenMP, CMake >=3.21, Make, Python and binutils; full checks/rendering
need the existing Python >=3.11 venv and exact `benchmarks/requirements-analysis.txt`
pins. The observed venv uses Python 3.14.2; standard-library workload tooling has
its separate documented minimum. No package install command is part of this guide.

```sh
cmake --version
g++ --version
"$DG_PY" --version
command -v make
command -v readelf
MPLCONFIGDIR="$DG_DOC_RUN/mpl" "$DG_PY" -B tools/validation/check_environment.py
```

Success: zero exits, exact dependency report and a real Agg render. Stop full
validation if this gate fails. A two-logical-CPU affinity is not two physical cores.
The later `inspect`/native evidence records visible topology/cgroups and limitations.
Sanitizer/process-control tests require the approved execution mechanism supporting
LeakSanitizer thread inspection and AF_UNIX socket binding; sandbox denial is not a
passing test, and leak detection must not be disabled to work around it.

## 2. Configure, build and run CTest

These Release commands include both optional native diagnostic tiers, so the full
registered set is **33**. Without those two options the historical full set is 31.
Use `-DCMAKE_BUILD_TYPE=Debug` with another fresh build directory for Debug. The
canonical sanitizer/portable archive entry points are in the validation runbook;
there is no sanitizer preset in `CMakePresets.json`.

```sh
cmake -S . -B "$DG_BUILD" -G 'Unix Makefiles' \
  -DCMAKE_BUILD_TYPE=Release -DDYNAGRAPH_WARNINGS_AS_ERRORS=ON \
  -DDYNAGRAPH_FULL_VALIDATION=ON -DDYNAGRAPH_ANALYSIS_PYTHON="$DG_PY" \
  -DDYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS=ON \
  -DDYNAGRAPH_ENABLE_RESOURCE_DIAGNOSTICS=ON
cmake --build "$DG_BUILD" --parallel 2
"$DG_PY" -B tools/validation/check_registration.py --build "$DG_BUILD" \
  --optional workload-diagnostics --optional resource-diagnostics
ctest --test-dir "$DG_BUILD" --output-on-failure --parallel 1
"$DG_BUILD/dynagraph_cli" --help
"$DG_BUILD/dynagraph_bench" --help
```

Success: warnings clean, exact registration 33, 33 executed tests passed, CLI usage
matches the commands below. Its historical Phase 2B banner is not the current
project phase. These are correctness/harness tests, not performance
measurements. Release checks stay active with NDEBUG. Library-only builds can use
`-DBUILD_TESTING=OFF` without the full-validation options and need no Python; they
are a different configuration, not a substitute for full validation.

## 3. Generate and independently verify the demo workload

Needs only Python standard library. The checked-in recipe is a development chain,
8 vertices, 7 edges, source 0, 12 updates; seeds graph/weight/source/trace are 1/2/3/4.
Generation must use a new output directory. Python verifies canonical identities
and recipe regeneration before the C++ worker runs.

```sh
"$DG_PY" -B benchmarks/python/generate.py generate \
  --spec benchmarks/configs/chain-v1.json --output "$DG_DOC_RUN/bundle"
"$DG_PY" -B benchmarks/python/generate.py verify \
  --manifest "$DG_DOC_RUN/bundle/manifest.json"
```

Success: zero exits and the complete bundle verifies; do not modify it between
verification and execution. The library's general edge-list loader is more permissive
than the benchmark's canonical graph/trace parser; use generator output for replay.

## 4. Sequential, parallel and incremental correctness

Needs the fresh build and verified bundle. `dynagraph_cli` offers static SSSP only;
there is no incremental CLI subcommand. The benchmark `verify` command exercises
incremental repair through the real adaptive-engine API, with full per-update checks.

```sh
"$DG_BUILD/dynagraph_cli" sssp --input "$DG_DOC_RUN/bundle/graph.txt" \
  --source 0 --algorithm dijkstra > "$DG_DOC_RUN/dijkstra.json"
"$DG_BUILD/dynagraph_cli" sssp --input "$DG_DOC_RUN/bundle/graph.txt" \
  --source 0 --algorithm delta-stepping --delta 16 --threads 2 \
  > "$DG_DOC_RUN/delta.json"
"$DG_PY" -B - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ['DG_DOC_RUN'])
a = json.loads((p/'dijkstra.json').read_text())
b = json.loads((p/'delta.json').read_text())
assert a['source'] == b['source'] == 0 and a['distances'] == b['distances']
print('Full distance vectors match; requested/actual workers:', b['requested_threads'], b['actual_threads'])
PY
for policy in dijkstra delta-stepping incremental heuristic; do
  "$DG_BUILD/dynagraph_bench" verify --graph "$DG_DOC_RUN/bundle/graph.txt" \
    --trace "$DG_DOC_RUN/bundle/trace.txt" --source 0 --policy "$policy" \
    --delta 16 --threads 2 --no-effect shared_fast_path --verification full \
    > "$DG_DOC_RUN/verify-$policy.json"
done
ctest --test-dir "$DG_BUILD" -R '^incremental_(sssp|failure)$' --output-on-failure
```

Success: complete static vectors match; actual team is reported separately. All four
benchmark verification commands exit zero and emit a success record. The worker
compares every graph/distance state with fresh Dijkstra and independent edge-record
Bellman–Ford on this small graph. The focused two CTests additionally verify repair
and transactional rollback. No runtime or speedup should be inferred from terminal
execution time, test duration or a work counter.

## 5. Python campaign regressions and original manifest

Needs the build/fixture, standard-library Python and approved socket-capable execution.
The suite launches bounded synthetic/real-control **test fixtures**, not the original
campaign. Its final count remains 382; do not count skipped/failed tests as passing.

```sh
DYNAGRAPH_PILOT_TEST_RUNNER="$DG_BUILD/dynagraph_bench" \
DYNAGRAPH_WORKLOAD_TEST_FIXTURE="$DG_BUILD/tests/workload_fixture" \
  "$DG_PY" -B -m unittest discover -s tests -p 'test_campaign*.py'
"$DG_PY" -B benchmarks/python/campaign.py validate \
  --plan benchmarks/configs/campaign-development-v1.json
"$DG_PY" -B benchmarks/python/campaign.py expand \
  --plan benchmarks/configs/campaign-development-v1.json > "$DG_DOC_RUN/original-trials.json"
"$DG_PY" -B - <<'PY'
import hashlib, json, os
from pathlib import Path
m = Path(os.environ['DG_DOC_RUN'])/'original-trials.json'
r = json.loads(m.read_bytes())
assert len(r['trials']) == 104
assert r['plan_sha256'] == 'f3729f556aab4db8742e9ac6bf7acb786faa27ab8780a463e10bfde62810ea24'
assert hashlib.sha256(m.read_bytes()).hexdigest() == 'f841201155f01ba7456a0344e6ea623bf5e8886f638497c3ede55397a7aa1c8a'
print('104 rows and both canonical hashes match')
PY
```

The expected plan hash is of validated canonical JSON, not the raw pretty-printed
configuration file. The original rows are 8 diagnostic + 64 warmup + 32 measured;
its placeholder build hashes prevent execution unchanged. There is no full matrix
executor; do not batch pilots, raise limits or relabel timing selections.

## 6. Optional fresh bounded diagnostic demonstration

The Phase F request authorizes command validation of this existing development
mode. Future users must have explicit permission to execute trusted staged code.
This creates **one fresh diagnostic fixture**, not another original campaign trial
or a replacement for the historical Phase D pilot. Needs Release build, readelf,
visible supported cgroup v2/affinity, two allowed logical CPUs and socket permission.
If preflight/coverage fails, preserve the failed result and stop; no automatic retry,
alternate allocation, forged observation or relaxed gate is authorized.

```sh
"$DG_PY" -B benchmarks/python/campaign.py inspect \
  --executable "$DG_BUILD/dynagraph_bench" > "$DG_DOC_RUN/hardware.json"
"$DG_PY" -B - <<'PY'
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, 'benchmarks/python')
from artifacts import write_bundle
from campaign_contract import expand
from workloads import canonical_json
root = Path(os.environ['DG_DOC_RUN']); build = Path(os.environ['DG_BUILD'])
h = json.loads((root/'hardware.json').read_text())
p = json.loads(Path('benchmarks/configs/campaign-development-v1.json').read_text())
inputs = root/'pilot-inputs'; (inputs/'bin').mkdir(parents=True, exist_ok=False)
exe = build/'dynagraph_bench'; shutil.copyfile(exe, inputs/'bin/dynagraph_bench')
flags = (build/'CMakeFiles/dynagraph_bench.dir/flags.make').read_bytes()
assert b'-fsanitize' not in flags, 'Use the uninstrumented Release build'
assert 'CMAKE_BUILD_TYPE:STRING=Release' in (build/'CMakeCache.txt').read_text()
p['build'].update(revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    compiler_sha256=h['compiler']['value']['sha256'], openmp_sha256=h['openmp']['value']['sha256'],
    flags_sha256=hashlib.sha256(flags).hexdigest())
p['hardware']['allocated_cpus'] = h['affinity']['value'][:2]
assert len(p['hardware']['allocated_cpus']) == 2
write_bundle(p['workloads'][0]['recipe'], inputs/'workloads/chain')
m = expand(p)
t = next(t for t in m['trials'] if t['phase']=='diagnostic' and t['policy']=='delta-stepping' and t['workers']==2)
for name, value in (('plan.json',p),('trials.json',m)):
    (inputs/name).write_bytes(canonical_json(value))
(root/'selected-trial.txt').write_text(t['trial_id']+'\n')
print('Derived diagnostic identity:',t['trial_id'])
PY
"$DG_PY" -B benchmarks/python/campaign.py pilot \
  --plan "$DG_DOC_RUN/pilot-inputs/plan.json" --manifest "$DG_DOC_RUN/pilot-inputs/trials.json" \
  --root "$DG_DOC_RUN/pilot-inputs" --output "$DG_DOC_RUN/pilot" \
  --trial-id "$(cat "$DG_DOC_RUN/selected-trial.txt")" \
  --execute-development --enforce-affinity --observe-workload --observe-resources \
  --max-trials 1 --wall-seconds 60 --timeout 20 --output-limit 1048576
"$DG_PY" -B benchmarks/python/campaign.py verify-pilot --output "$DG_DOC_RUN/pilot"
"$DG_PY" -B benchmarks/python/campaign.py inspect-recovery --output "$DG_DOC_RUN/pilot"
"$DG_PY" -B - <<'PY'
import json, os
from pathlib import Path
root = Path(os.environ['DG_DOC_RUN']); tid = (root/'selected-trial.txt').read_text().strip()
d = root/'pilot'/tid
r = json.loads((d/'record.json').read_text()); w = json.loads((d/'workload-native.json').read_text())
b = json.loads((d/'resource-bound.json').read_text())
assert r['status']=='success' and b['coverage_complete'] and not b['measurement_eligible']
print('Requested workers:',r['trial']['workers'])
print('Observed teams:',sorted({t['team'] for region in w['regions'] for t in region['threads']}))
print('Resource classification:',b['classification'],'issues:',b['issues'])
PY
```

Success: pilot status complete, verifier execution_status complete, recovery settled
with one verified-complete trial; native team evidence and complete resource coverage.
Classification is an observation, **not preselected**: complete coverage can report
interference or configuration change. Incomplete/contradictory evidence cannot complete.
Timing/scientific eligibility stay false. CPU PSI is shared and includes the oracle,
observer and other processes. Serial executions without a delta region lack complete
resource coverage, so this fixture deliberately selects delta. `verify-pilot` exit
zero alone can describe intact failed evidence; always read execution_status.

## 7. Historical evidence and archives: availability gate

The raw Phase D/E/F evidence directories are ignored, not in Git. Before presenting
accepted historical findings, verify the actual retained input. A missing path is
an unavailable prerequisite, not permission to generate a substitute. No download,
remote service or regenerated historical evidence is needed/used in this workspace.

```sh
test -f results/validation/phase-d-benchmark-campaign/audit-sha256.json
"$DG_PY" -B benchmarks/python/campaign.py verify-pilot \
  --output results/validation/phase-d-benchmark-campaign/execution/pilot
"$DG_PY" -B benchmarks/python/campaign.py inspect-recovery \
  --output results/validation/phase-d-benchmark-campaign/execution/pilot
"$DG_PY" -B - <<'PY'
from pathlib import Path
import subprocess, sys
pairs = sorted(Path('results/validation/phase5-recovered-github-20261106').glob('*/*.tar.gz'))
assert len(pairs)==9, 'Original historical archives unavailable; stop this step'
for archive in pairs:
    subprocess.run([sys.executable,'-B','tools/validation/evidence_archive.py',
        '--verify',str(archive),'--sidecar',str(archive)+'.sha256'],check=True)
PY
```

Success: complete Phase D execution/recovery with two diagnostic completions; nine
original published archive/sidecar pairs verify. These verify retained historical
profiles; they are not freshly rerun historical CI jobs. Specific missing older
local-run copies remain unverified. For portable current-code archives, use
`tools/validation/ci_verify.py --python "$DG_PY" --mode debug|release|sanitize --output NEW`
(with `--smoke` required only for Release), then
`evidence_archive.py --verify ARCHIVE --sidecar ARCHIVE.sha256`. Mode alternatives
in that explanatory sentence are not a literal shell command. The full runbook
contains exact profile commands and independent offline-kit verification.

## 8. Regenerate Phase E assessment and inspect outputs

Needs **the complete original Phase D retention directory**, not just the new live
fixture. The adapter deliberately refuses to relabel a new pilot as historical Phase D.
The explicit expected inventory digest below anchors the original retained bytes;
never calculate a replacement from unverified input. Needs the pinned rendering venv.

```sh
MPLCONFIGDIR="$DG_DOC_RUN/mpl" "$DG_PY" -B benchmarks/python/analyze.py \
  --phase-d results/validation/phase-d-benchmark-campaign \
  --inventory-sha256 1e0d0c658410a53f3a5824369b9c6b0a1dd4e60bb95add79a2cd83f81cc96f06 \
  --output "$DG_DOC_RUN/phase-e"
cat "$DG_DOC_RUN/phase-e/report.md"
"$DG_PY" -B - <<'PY'
import json, os
from pathlib import Path
root = Path(os.environ['DG_DOC_RUN'])/'phase-e'
s = json.loads((root/'summary.json').read_text())
assert s['original_campaign']['unexecuted']==104 and s['derived_pilot']['verified_complete']==2
assert s['resource_classifications']=={'observed_interference':2}
assert s['performance']['sample_count']==0 and s['performance']['speedup'] is None
for name in ('summary.json','diagnostic-trials.jsonl','report.md','accounting.svg','accounting.pdf','analysis-manifest.json'):
    assert (root/name).is_file()
print('Verified diagnostic assessment; six output files:',root)
PY
```

Open the printed `accounting.svg` or PDF in the IDE file preview. The chart shows
trial counts, not runtime or speedup; overlapping pilot categories are labeled.
Both original Phase D pilot trials have observed_interference, timing null and zero
scientifically eligible observations. Numerical bootstrap tests on synthetic
fixtures do not make these data eligible. No defensible multicore speedup,
performance confidence interval or TSan acceptance follows.
