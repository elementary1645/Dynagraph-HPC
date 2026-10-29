# Research-validation release-readiness checklist

This checklist gates research-validation infrastructure review. It does not grant
publication, release, commit, push, PR or Phase 6 approval.

- [ ] Independently review the complete working-tree diff, including all untracked
  tools and the source inventory. Preserve prior phases and failed evidence.
- [ ] Confirm production algorithms, APIs, heuristics, timing boundaries, workload
  formats, dependency pins and existing timeouts are unchanged.
- [ ] Review focused parser/receipt/snapshot tests, intended negative diagnostics,
  adversarial archives and minimal/optional compatibility evidence.
- [ ] Reconcile exactly 31 registered and actually executed passing tests in each
  fresh sequential Debug, Release and ASan+UBSan leg. Confirm leak detection and
  halt-on-error options; inspect raw JUnit, command receipts and logs.
- [ ] Inspect Release smoke workload verification, both complete 16-trial datasets,
  analysis acceptance, all 14 figures and all nine intended negative diagnostics.
- [ ] Create and reopen evidence archives from real completed legs. Verify complete
  member inventories, modes, SHA-256, source identities, raw registrations and
  mandatory results with a separately copied verifier kit and no checkout access.
- [ ] Check explicit archive profile completeness after refreshing all inventories:
  both datasets, required hash keys, stage receipts, environment policy and replay
  evidence must remain mandatory. Reject conflicting success/failure markers.
- [ ] Enforce the exact configure argv emitted by ci_verify.py: joined ordered
  allowlisted definitions only, no split/typed definitions, duplicate keys or
  unparsed override options. Verify build type, full mode and sanitizer flags.
- [ ] Reject oversized, nonfinite and incorrectly typed receipt times with specific
  diagnostics; confirm this metadata bound changes no execution/test timeout.
- [ ] Reject truncated/corrupt gzip trailers and tar structures, trailing streams,
  unsupported metadata and resource-limit violations with intended diagnostics.
- [ ] Verify each uploaded `.tar.gz.sha256` with `sha256sum -c`; confirm the offline
  launcher removes its kit argument and uses only the copied trusted kit.
- [ ] Verify failed-run archives report integrity separately from failed validation,
  and the original failing CI command remains nonzero.
- [ ] Inspect hosted provisioning and all three hosted jobs after an authorized CI
  trigger. Check uploaded tarballs with the offline verifier, and inspect retained
  raw partial evidence on failure. Local verification cannot tick this item.
- [ ] Retain original archives and record their externally computed SHA-256 for
  transfer comparison. Digests establish integrity, not producer authentication.
- [ ] Document tested platform/tool versions and outstanding limitations. Preserve
  the unmet TSan gate and intentional-race controls outside ordinary CTest/CI.
- [ ] Obtain independent review and explicit authorization for subsequent action.

Pending hosted evidence and independent review mean release readiness remains
conditional. No performance, inferential-statistics, race-freedom or general
cross-platform reproducibility claim follows from this checklist.
