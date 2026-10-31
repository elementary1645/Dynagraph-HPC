# Development affinity enforcement runbook

Use a development plan with an explicit sorted unique `hardware.allocated_cpus`
set already permitted by current affinity, online CPUs and visible cgroup2 cpuset.
Every finite visible quota must cover requested workers. Missing evidence is a
failure to establish enforcement; it is never an unlimited-resource guarantee.

```sh
python3 -B benchmarks/python/campaign.py pilot \
  --plan PLAN --manifest MANIFEST --root INPUT_ROOT --output NEW_PILOT \
  --trial-id TRIAL_ID --execute-development --enforce-affinity
python3 -B benchmarks/python/campaign.py verify-pilot --output NEW_PILOT
python3 -B benchmarks/python/campaign.py inspect-recovery --output NEW_PILOT
```

Do not put assessment output inside original pilot evidence. Inspect the generated
`TRIAL_ID/I-KIND.affinity.json` alongside the process streams/runtime sidecars.
Offline verification never launches an archived runner. Inspect `state`,
`lifecycle`, `released`, acknowledgement errno/error, independent observation and
release timestamp. A verified receipt establishes only the pre-exec checks and
release, not workload completion or scientific eligibility.

For an interrupted pilot containing verified completions and never-launched pending
trials, after normal read-only recovery review:

```sh
python3 -B benchmarks/python/campaign.py resume-pilot --output ORIGINAL \
  --execute-development --authorize-resume --enforce-affinity
python3 -B benchmarks/python/campaign.py inspect-resume --output ORIGINAL.resume-v1
```

Enforced originals cannot silently resume with inherited affinity. Resume header
v2 binds renewed opt-in and the new attempt. Original completed trials retain their
own receipts and are never relaunched; only pending work receives new receipts.
An existing attempt reservation permanently blocks another resume. Failed,
interrupted or unresolved trials are not retried. Default legacy execution/resume
uses unchanged version-1 resume headers and inherited-affinity semantics.

Prelaunch CPU validation errors cause no child launch. A post-spawn rejection,
missing/corrupt acknowledgement, identity mismatch, OS rejection, insufficient
quota or observation failure prevents GO and kills the process group. Deadline
expiry is indeterminate; SIGTERM is interrupted. Parent death before GO causes EOF
and the launcher exits without running the target. Abrupt parent death after GO
retains the existing possible-orphan limitation and never authorizes retry.
Do not repair evidence or delete reservations to bypass these gates.

This mechanism is Linux-only and unprivileged; it changes only the child leader,
whose affinity is inherited across exec and by later threads. It neither observes
actual OpenMP teams nor prevents the workload or another permitted actor changing
placement later. Local hashes and process identities provide consistency, not
external authentication, immutable bytes, CPU ownership, isolation, contention
control or scientific eligibility. No privileged resource changes are supported.

Bounded tests:

```sh
python3 -B tests/test_campaign_enforcement.py
```

Fixtures use synthetic visible cgroups with real self-affinity and process identity
syscalls; a separate native cgroup smoke runs where supported. No scientific
campaign, heuristic/timing change or performance claim is part of this runbook.
