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

## R1: signal-safe cleanup and complete acknowledgement framing

The acceptance audit found two defects in 1450d47. A SIGTERM between closing a
release descriptor and untracking its integer caused an EBADF during subsequent
cleanup; barrier cleanup ran before kill/reap and could leave a workload alive.
The reader also accepted the first newline without waiting for EOF, allowing a
delayed contradictory second message to be discarded from a completed pilot.

R1 defers SIGINT/SIGTERM across descriptor acquisition/ownership transitions and
kill/reap/close, then delivers the original pending interruption. Descriptors are
untracked before a single close attempt; repeated cleanup is idempotent. EBADF
means the descriptor is already closed. A changed fstat identity is reported and
the reused descriptor is left untouched. Other close errors are reported, never
blindly retried: the kernel may already have released the integer. This ownership
model assumes externally serialized descriptor access; it cannot authenticate
arbitrary concurrent same-process descriptor manipulation.

Process-group SIGKILL and a bounded two-second wait run before barrier closure or
receipt sealing. Every remaining owned descriptor is attempted even if another
close fails. Cleanup failures remain visible; an original exception/interruption
is preserved with the secondary failure chained. A pending termination delivered
at mask restoration cannot bypass reaping. Kernel-level uninterruptible execution
or failed OS termination cannot be certified away; wait failures are errors and
cannot produce a successful completion. SIGKILL/abrupt parent death retains the
existing post-GO possible-orphan limitation; pre-GO pipe EOF never authorizes work.

The acknowledgement reader now waits for EOF within the same monotonic process
budget, with a strict 65,536-byte cap. Exactly one canonical JSON message plus its
single newline is required. Duplicate messages, delayed failure messages, extra
whitespace, trailing bytes, incomplete JSON and oversized streams reject. A valid
prefix with its writer held open does not authorize GO; deadline expiry kills the
process group. The existing child already closes its acknowledgement writer before
waiting for GO; its protocol and receipt schema do not need a version change.
Only explicit child control descriptors are inherited, and parent-side writer
copies are closed before reading. An unexpectedly inherited writer can delay EOF
only until the deadline, never grant authorization.

A receipt may retain truthful verified/released facts if interruption occurred
just after GO. The process outcome must still be interrupted/failed, with no
completed trial or unsafe resume reuse. Pre-GO invalid streams produce neither GO
nor a verified-success receipt. All measurement/scientific-authority flags remain
false. No admission promotion, retry, team instrumentation or isolation is added.
See the research log for exact before/after independent fixtures and final results.


## R2: cleanup progress and GO accounting

The R1 re-audit reproduced a signal before the cleanup context installed its mask:
its body was skipped, yet capture returned with a live workload. It also delivered
SIGTERM immediately after the GO write, before the release ledger assignment;
the workload ran while the receipt incorrectly said `released=false`.

Capture now installs non-raising SIGINT/SIGTERM recording handlers before creating
any child and retains them through termination, reaping, descriptor cleanup and
receipt sealing. Explicit execution checkpoints deliver the caller's interruption
policy. Repeated termination requests coalesce; the caller's handlers and signal
mask are restored. Handler handoff also checks requests recorded after the final
checkpoint, so a late request cannot disappear during restoration. No mask is held across Popen, so children inherit the original
mask. Ignored signals remain ignored. Handler installation is main-thread only;
worker-thread callers retain their surrounding signal policy. These temporary
handlers assume serialized main-thread capture/handler ownership.

Cleanup tracks group termination, reaping and completion separately. Interrupted
context entry runs a fallback under the already-installed recording handlers;
entry is never evidence of completion. Teardown is idempotent and uses one total
two-second monotonic reap budget. Closure/sealing failures cannot skip termination
and are surfaced, chained to an original exception when present. An incomplete
teardown cannot return a normal capture receipt. Linux status inspection uses
`waitid(WNOWAIT)` instead of reaping with poll: the session leader PID remains
reserved until group SIGKILL and wait. The child must remain a waitable child with
its original session/group. Already-reaped or changed ownership is an error and
never authorizes group signaling. This assumes exclusive ownership of child
reaping: an unrelated concurrent reaper can invalidate the check-to-signal interval;
Python cannot authenticate or serialize arbitrary external same-process actors.
Descendants that deliberately escape the owned process group are outside this
bounded group-cleanup mechanism. Portable non-Linux capture retains weaker process
inspection; affinity enforcement remains Linux-only.

New affinity receipts use schema version 2; the verifier continues to accept strict
version-1 historical receipts unchanged. Policy, pilot v2, resume headers, runtime
sidecars and journal v1 are unchanged. Version 2 adds `release`:

| State | `released` | Meaning |
| --- | --- | --- |
| `not_attempted` | false | No GO write attempted; timestamps/byte count/errno null |
| `attempted` | null | In-memory transition only; cannot pass offline verification |
| `confirmed_sent` | true | Write returned exactly one byte; no workload-completion claim |
| `not_sent` | false | Zero-byte write or known no-write EPIPE/EBADF/EAGAIN |
| `indeterminate` | null | Delivery cannot be determined, including EINTR/EIO or an exception without a known write result |

GO is a single nonblocking byte (within PIPE_BUF), after all verification and the
final deadline/interruption checkpoint, with no automatic retry. The write and
ledger update run under the recording handlers plus a restored signal mask.
`attempted_at` is recorded immediately before the write; on confirmed success it
is retained as `release_timestamp`, a pre-write bound, not an invented exact kernel
delivery time. `confirmed_at` records when successful return was observed.
`bytes_written` and `errno` retain known results. Ambiguous writes have no confirmed
or release timestamp. The verifier reconciles these fields, lifecycle and process
outcome; an unresolved `attempted` state is rejected. A post-GO interruption retains
confirmed release but fails the process/trial/journal completion gate. An uncertain
write never authorizes a successful completion or safe retry. Scientific flags
remain false for every release outcome.

These guarantees cover catchable SIGINT/SIGTERM in the main-thread ownership scope,
not unconditional asynchronous-exception safety. SIGKILL, interpreter death,
uninterruptible kernel execution, external reaping or arbitrary injected Python
exceptions can prevent cleanup; failures must remain visible. A custom caller
handler is invoked only at a safe checkpoint, rather than in the GO/cleanup
critical section. Receipt serialization failure propagates after teardown. No
claim of race freedom, external authenticity, team observation or scientific
eligibility follows from these changes.
