# Bounded resource interference diagnostics

Phase 6B-2B-3B-4 adds explicitly authorized **development diagnostics** in Linux
Codespaces. Scientific eligibility remains false. Shared cgroup observations do
not establish physical-core scaling, exclusive ownership, isolation, uncontended
execution, producer authentication or TSan acceptance.

Use the existing pilot selection and bounds, adding all three flags:

```sh
.venv-analysis/bin/python -B benchmarks/python/campaign.py pilot --help
# Add to an explicitly selected bounded diagnostic pilot:
# --execute-development --enforce-affinity --observe-workload --observe-resources
# Resume also requires --authorize-resume and renewed copies of all three flags.
```

The unchanged default and timing commands do not collect resources. Direct native
`verify` requires `--workload-observations workload-native.json`,
`--resource-observations resource-native.json` and
`--resource-cgroup-paths resource-paths.txt` together. The pipeline creates that
configuration before launch from the visible cgroup v2 ancestry, boot ID and
CLOCK_MONOTONIC nanoseconds. It is an immutable hashed staged input, not a
verifier-selected path to open offline. Existing enforcement remains the launch
authority. Resource collection adds no operation between final barrier validation
and GO.

Four in-process snapshots cover pre replay, first delta region primary-thread
entry and exit, and post replay. Every workload thread records entry/exit envelopes
in native workload v3. Workload v2 remains unchanged without resource opt-in.
Resource sample times must fit the actual primary envelopes, pre/post must enclose
all workload regions, and all observations must fit the parent's armed/completed
CLOCK_MONOTONIC interval. Serial executions without delta regions produce only
pre/post and cannot establish complete workload resource coverage.

Each snapshot records leader and sampler affinity, task/process start ticks and
status, cgroup membership/mountinfo before and after, boot identity, online CPUs
before and after, visible directory device/inode, cpu.max, effective cpuset,
cpu.stat, CPU PSI, optional schedstat, and per-affinity-CPU package/core/SMT sibling
facts. Reads use bounded regular files, O_NOFOLLOW, RAII descriptors and explicit
errno/value facts. Caps are four samples, sixteen visible ancestor paths, sixty-four
process-affinity CPUs, 16 KiB ordinary files, 64 KiB mountinfo and 1 MiB artifact.
No background sampler, privileged operation, host reconfiguration or new dependency
is used. The observer itself and correctness oracle contribute to cgroup counters.
Sampling overhead is confined to diagnostics, not scientific timing.

`dynagraph-resource-native` v1 stores raw observations. `dynagraph-resource-bound`
v1 / classification v1 binds the full enforcement request (execution/trial/attempt,
origin, command, executable digest), confirmed GO receipt, process generation and
boot ID, workload-bound digest, native resource digest, configuration bytes,
hardware and OpenMP environment digests, fixed policy and interval, classification,
coverage and counter deltas. Its evidence digest seals canonical JSON. Offline
verification recomputes the bound document and validates semantic facts after the
ordinary enforcement and workload gates; recomputed file hashes alone cannot
repair contradictory evidence. This is local consistency, not cryptographic
attestation: a party able to replace every mutually consistent observation is not
authenticated by hashes.

Classification precedence is:

| Classification | Rule |
| --- | --- |
| contradictory_evidence | Malformed or contradictory known facts, identity/generation, GO, ancestry coverage or boundary mismatch |
| observed_configuration_change | Affinity, quota, cpuset, online, cgroup view/inode, topology or workload OpenMP context changes |
| observed_interference | Positive nr_throttled/throttled_usec or CPU PSI cumulative total deltas |
| insufficient_evidence | Unavailable required facts, unsupported cgroup layout, counter resets/field changes, no sampled region or excessive gaps |
| observed_stable | Required available facts consistent, no observed change or interference in the sampled interval |

Coverage is separate: known changes/interference may coexist with insufficient
coverage and then cannot complete a diagnostic. Usage growth alone is normal;
PSI averages are context and do not establish new interval pressure. Counter
resets never count as negative interference. The fixed maximum interval is 32 s;
any sample duration or gap, including pre/post publication, over 2 s makes coverage
incomplete. Stable means observed stability at these boundaries only. Hidden
ancestors, events between snapshots, per-worker scheduling inside the region,
other users of the cgroup and host interference remain unverified.

Completion requires full correctness, verified atomic confirmed GO, workload
membership and complete resource coverage. Stable, interference and configuration
change are diagnostic outcomes, not scientific admission decisions. Missing or
failed publication cannot complete. Unknown GO, failed or interrupted launches
cannot be reused or retried. Pilot v2 and journal v1 remain unchanged; the execution
manifest adds the resource policy. Safe resume authorization v4 renews resource,
workload and affinity opt-ins, re-verifies original completed evidence read-only,
and launches only never-launched pending trials into one sibling transaction.
Versions 1–3 remain readable. An old pilot cannot be upgraded into this contract.

Opt-in regression registration:

```sh
cmake --preset debug -DDYNAGRAPH_ENABLE_WORKLOAD_DIAGNOSTICS=ON -DDYNAGRAPH_ENABLE_RESOURCE_DIAGNOSTICS=ON
cmake --build --preset debug -j2
ctest --test-dir build/debug --output-on-failure -R 'workload_instrumentation|resource_interference'
```

The historical default full-validation archive profile still requires exactly 31
tests. The two additive diagnostic tiers yield 33 when explicitly enabled. See
[Phase B acceptance](phase-b-acceptance.md) for commands, actual results and limits.
