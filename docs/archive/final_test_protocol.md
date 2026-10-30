# R2 Final-Test Protocol Entry Point

The governing lockbox specification is [`final_test_lockbox_protocol.md`](final_test_lockbox_protocol.md). It defines frozen family assignment, manifest and file hashes, manifest-only allowlists, contamination, rerun, failure, and reporting rules.

R2 does not create, read, open, or execute a formal final-test lockbox. The files under `data/r2_sanity/final/` are non-formal sanity artifacts and cannot be promoted or relabeled as final-test evidence. Final-test access requires a separately approved formal dataset, joint split preflight, immutable hashes, and an explicit execution authorization.
