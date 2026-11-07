# Professor demonstration

## Prepare before the timed presentation

Use [the Codespaces reproduction guide](reproducibility-guide.md), sections 1–4
and 7–8. Build/generate/verify before starting the five-minute timer. A new Codespace
needs its own build and explicit access to the retained Phase D originals; they are
ignored, not shipped in Git. Do not substitute fabricated files if the availability
gate fails. The live pilot in section 6 is optional, separately authorized and must
finish/verify before presenting its evidence. This is not a 104-trial live run.

Keep the same Bash terminal with `DG_BUILD`, `DG_DOC_RUN` and `DG_PY` from the guide.
Run this readiness check immediately before the presentation, from the repository root:

```sh
test -x "$DG_BUILD/dynagraph_cli"
test -x "$DG_BUILD/dynagraph_bench"
"$DG_PY" -B benchmarks/python/generate.py verify --manifest "$DG_DOC_RUN/bundle/manifest.json"
"$DG_PY" -B - <<'PY'
import hashlib, json, os
from pathlib import Path
p = Path(os.environ['DG_DOC_RUN'])/'phase-e'
m = json.loads((p/'analysis-manifest.json').read_text())
assert m['status']=='complete'
assert m['source_inventory_sha256']=='1e0d0c658410a53f3a5824369b9c6b0a1dd4e60bb95add79a2cd83f81cc96f06'
for name, digest in m['output_sha256'].items():
    assert hashlib.sha256((p/name).read_bytes()).hexdigest()==digest
print('Generated report/figure hashes match; present the report created by the guide')
PY
```

Success: zero exits and verified report/figure hashes. This supplements the guide's
raw-evidence admission; an output hash alone is not authentication. If historical
inputs are absent, the algorithm portion still works, but the complete historical
evidence/analysis demonstration is **not ready**. Say so; do not show an unverified
image or claim the full demonstration was completed.

## Five-minute demonstration

| Time | Action and terminal command | Explain / expected observation |
| --- | --- | --- |
| 0:00–0:40 | Open [architecture](architecture.md#implemented-system-and-data-flow) | Fixed-topology directed SSSP; weight decreases between queries. Maintaining exact answers can avoid full recomputation, but a speed advantage has not been established here. |
| 0:40–1:30 | Run the two SSSP commands below | Complete vectors agree; worker requests and observed teams are distinct. |
| 1:30–2:30 | Run the incremental verification command below | Twelve ordered requests checked against fresh recomputation and independent small-graph Bellman–Ford; this is correctness, not a performance result. |
| 2:30–3:15 | Show original manifest count/hash using reproduction section 5 | Exactly 104 planned rows, not 104 completed experiments. Plan/identity determinism does not imply execution. |
| 3:15–4:10 | Inspect raw Phase D recovery and report as below | Two verified-complete diagnostic trials, both observed_interference; no scientific timing samples. |
| 4:10–5:00 | Open `$DG_DOC_RUN/phase-e/accounting.svg`; state limitations | Original 104 unexecuted; two separate pilot identities, zero eligible timings. No speedup/CI/scaling claim; TSan acceptance unmet. |

```sh
"$DG_BUILD/dynagraph_cli" sssp --input "$DG_DOC_RUN/bundle/graph.txt" --source 0 --algorithm dijkstra
"$DG_BUILD/dynagraph_cli" sssp --input "$DG_DOC_RUN/bundle/graph.txt" --source 0 --algorithm delta-stepping --delta 16 --threads 2
"$DG_BUILD/dynagraph_bench" verify --graph "$DG_DOC_RUN/bundle/graph.txt" \
  --trace "$DG_DOC_RUN/bundle/trace.txt" --source 0 --policy incremental \
  --delta 16 --threads 2 --no-effect shared_fast_path --verification full
"$DG_PY" -B benchmarks/python/campaign.py inspect-recovery \
  --output results/validation/phase-d-benchmark-campaign/execution/pilot
cat "$DG_DOC_RUN/phase-e/report.md"
```

The benchmark record should report success, full verification and final-state
checks, not a timed repair latency. When a backend executes, the small chain's heuristic selects Dijkstra
under the unchanged small-graph rule; it does not demonstrate every adaptive branch.
The displayed static CLI `actual_threads` is execution observation, not physical-core
ownership. Present the earlier vector-equality check if asked to verify JSON by code.

## Ten-minute technical walkthrough

Use the five-minute sequence plus these focused additions. Preparation is still
outside the timer; long full regressions are evidence to inspect, not a timed stunt.

| Minutes | Technical focus | Command or source |
| --- | --- | --- |
| 0–2 | CSR invariants, uint32 weights, uint64 distances, unreachable null, input validation | `include/dynagraph/graph/csr_graph.hpp`, static CLI output and architecture storage sections |
| 2–4 | Persistent OpenMP team, atomic min, bucket light closure/heavy scan, barriers and failure propagation | `src/algorithms/delta_stepping.cpp`; explain results are deterministic, schedules/counters need not be |
| 4–5 | RAM undo journal and rollback; distinguish disk recovery journal | Focused CTest below; `src/dynamic/incremental_sssp.cpp` |
| 5–6 | Forced policies, shared no-effect fast paths, immutable heuristic thresholds | Four-policy verification in guide section 4; `src/adaptive/adaptive_sssp.cpp` |
| 6–8 | Confirmed GO, process/thread generation, actual teams and shared cgroup counters | Raw retained Phase D evidence inspector below, or the already verified fresh fixture from guide section 6 |
| 8–9 | Deterministic 104-row plan, different derived IDs, pilot bounds and safe resume | Guide section 5 and [recovery contract](campaign-recovery.md); no automatic retry/resume in the demo |
| 9–10 | Evidence admission, reproducible report hashes and unavailable inference | Phase E report/accounting and [method assumptions](phase-e-acceptance.md#numerical-methods-and-safeguards) |

```sh
ctest --test-dir "$DG_BUILD" -R '^incremental_(sssp|failure)$' --output-on-failure
"$DG_PY" -B - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, 'benchmarks/python')
from analysis_evidence import load_phase_d
s = load_phase_d(Path('results/validation/phase-d-benchmark-campaign'),
    '1e0d0c658410a53f3a5824369b9c6b0a1dd4e60bb95add79a2cd83f81cc96f06')
for r in s['diagnostics']:
    print(r['trial_id'], 'requested:',r['requested_workers'], 'observed:',r['actual_workers'],
          'resource:',r['resource_interference'], 'coverage:',r['resource_coverage_complete'])
print('Scientific sample count:',s['performance']['sample_count'])
print('Speedup:',s['performance']['speedup'], 'reason:',s['performance']['reason'])
PY
```

Expected retained observations: requested/observed teams 1/[1] and 2/[2], complete
coverage, observed_interference twice, scientific sample count 0, speedup None with
reason. The fresh live fixture, if demonstrated instead, has a new ID and its own
observed classification; do not assert it must repeat historical counters or labels.
The Phase D reported logical CPUs are SMT siblings on one visible core, not two
independent physical cores. Missing early OpenMP runtime mapping snapshots stay
unavailable; native task/region evidence is independently checked through its gate.

## Common questions

**What is adaptive here?** A deterministic metadata heuristic selects Dijkstra,
incremental repair or delta-stepping after validation/shared fast paths. Rules use
edge count and destination degree, with fixed 4096/32/65536 thresholds and explicit
worker request. There is no learned/calibrated model, runtime-history feedback or
automatic delta tuning; a low destination degree does not bound the affected region.

**Is incremental repair parallel?** No. It is sequential, for an existing edge's
single weight decrease/equality at fixed source/topology. Delta-stepping is the
parallel recomputation backend. Storage can replace weights with any supported
nonnegative value; incremental increases/topology changes remain deferred.

**How is correctness established?** Independent hand/seeded Bellman–Ford fixtures,
fresh Dijkstra, complete-vector/graph comparisons after updates and transactional
failure controls. Passing finite suites is bounded evidence, not a formal proof for
all inputs. ASan/UBSan/LeakSanitizer pass; TSan research acceptance remains unmet.

**Why not show speedup?** The original 104-trial campaign has not run. Both accepted
pilot executions are diagnostic-only with no timing samples, observed shared CPU
pressure and no scientific admission. Two virtual/logical CPUs and affinity cannot
establish independent physical cores, exclusive ownership or uncontended scheduling.

**What do hashes prove?** Byte integrity and identity reconciliation against an
explicitly trusted inventory, not producer authentication or resource exclusivity.
A verifier never executes an archived runner. The raw journal, receipts, oracles,
workload membership and resource semantics are rechecked beyond matching hashes.

**Can a failed run resume?** Not through this safe subset. Explicit dual authorization
can reuse immutable verified completions and launch only never-launched pending
trials in one child attempt. Unknown GO, failure, interruption, unresolved ownership
or a repeated attempt must not be automatically retried.

**Are there confidence intervals?** The numerical library's IID-unit bootstrap is
synthetic-tested, with explicit assumptions, seed and insufficient-data controls.
It is not applied to the diagnostic data. Actual performance intervals and speedup
are unavailable. Ordered updates and warmups are not independent replication.

**What is still needed for a performance paper?** An authorized full executor and
qualified timing-admission contract, genuine eligible measurements, compatible
hardware/provenance and justified independent replication, plus the documented
remaining scientific/race-detector gates. Documentation/software acceptance alone
does not supply those measurements or a novelty claim.
