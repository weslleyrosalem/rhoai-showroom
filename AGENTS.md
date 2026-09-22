# Showroom collaboration rules

This repository is an OpenShift AI technical presales showroom, not a production baseline. The user's current request takes precedence over these project conventions.

## Start and resume

Read `docs/operations/project-plan.md`, `docs/operations/validation.md`, and the relevant lab before changing its implementation. Check live state before acting; a saved checkpoint is evidence from a particular time, not a current health check. Use the `showroom-operations` skill in `.agents/skills/` for deployment, rehearsal, and handoff work.

Keep a short private working-memory file and separate agent checkpoints outside this public repository. Record decisions, exact evidence locations, owners, unfinished work, and recovery commands after material changes. Never paste whole conversations or credentials into public memory files.

## Invariants

- Write all code, comments, documentation, notebooks, examples, and UI in U.S. English.
- Keep secrets, API keys, browser tokens, account IDs, private hostnames, and raw cluster evidence out of Git and published pages. Publish sanitized evidence only.
- Verify the expected cluster and identity before mutations. Use the guarded repository helpers where applicable.
- Count physical GPUs across all pool maxima and upgrade surge before changing capacity. The current showroom ceiling is 16. MIG slices do not increase this physical allowance.
- Manage ROSA capacity through Red Hat ROSA/OCM. Do not modify the underlying AWS-managed scaling machinery. Avoid repeated ROSA/OCM API polling; check registered nodes through `oc`.
- Separate product maturity, resource readiness, functional success, security results, and measured performance. Never turn an evaluation job's completion into a claim that the model passed.
- Keep current demo endpoints responsive during load tests. Bound concurrency, timeouts, quota, credential lifetime, and an absolute end time; persist results.
- Clean up identified temporary probes and failed tests after preserving useful evidence. Do not delete persistent data or unrelated workloads just to make the dashboard look green.

## Collaboration

When parallel work is requested, assign distinct ownership: platform/inference, science/application, security/agents, and integration/publication. Each agent writes its own checkpoint. The integration owner alone commits, publishes, and changes shared cloud capacity. Cross-review security boundaries and customer-facing claims before release.

## Verification and publication

Run tests appropriate to changed behavior, `python scripts/validate_repo.py`, and `mkdocs build --strict`. Include newly added files in the secret/content review. Rehearse the actual browser path with a scoped identity, inspect mobile and keyboard navigation, and record failures and corrections honestly. Check the published page after deployment; a successful build is not a usability test.
