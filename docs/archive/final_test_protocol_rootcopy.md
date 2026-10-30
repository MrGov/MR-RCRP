# Final-Test Lockbox Protocol

This protocol defines the future final-test boundary. R2 does not open, inspect for optimization, or execute the final split.

## Freeze prerequisites

Before a formal final manifest is created, freeze and hash the objective/model version, instance schema, generator implementation and configuration, complete family matrix, family-to-split rule, instance IDs and file bytes, method conditions, prompts/providers, operator portfolio, solver seeds, run budgets, estimands, failure policy, aggregation/statistical scripts, and the pilot-artifact exclusion receipt. Missing hashes are a no-go.

## Access boundary

Final access is allowlist-only from a frozen manifest. No wildcard or recursive data discovery is permitted. Development tooling may receive development manifest records only; held-out results cannot drive method changes; final files, features, IDs, hashes, performance, failures, or subgroup results must not enter prompt design, operator generation, portfolio selection, selector training, or tuning.

## Opening and reruns

The lockbox may be opened once the three formal split manifests and integrity receipts pass joint preflight. A rerun is permitted only for a pre-declared infrastructure failure under the frozen policy, preserving the original logs and reason. A method/config/code change, exploratory rerun, or result-guided adjustment contaminates the lockbox and requires a new protocol version and test set.

## Failure and reporting

Invalid, timeout, fallback, and solver failures are recorded as outcomes under the frozen policy; they are not silently rerun until success. Manifest, split, file-identity, or contamination failures invalidate the affected formal integrity unit and are reported as inconclusive. Reports include manifest hashes, code/config hashes, scheduled and completed counts, failure categories, exclusions, and the exact frozen conditions.

The current R2 sanity final files are non-formal artifacts and cannot be promoted or relabeled as final-test evidence.
