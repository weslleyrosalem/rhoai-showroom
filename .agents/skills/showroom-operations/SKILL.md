---
name: showroom-operations
description: Resume, rehearse, and operate the Aurora OpenShift AI showroom using its recorded validation, guarded helpers, and presentation runbooks.
---

# Showroom operations

Use this skill for this repository's live demonstration, deployment, review, and handoff work. It does not authorize access to a different cluster or unrelated cloud changes.

Locate the repository root, then read `AGENTS.md`, `docs/operations/project-plan.md`, and the relevant validation row. Load only the lab and private agent checkpoint needed for the current task. If a checkpoint is unavailable, recover state from Git, live resources, and the active agents before repeating a paid or destructive operation.

For a presentation, work backward from the session time and audience. Confirm the actual model endpoint, key lifetime, quota, metrics window, and a tested fallback. Keep measured local prefix-cache behavior distinct from distributed KV transfer or routing benefits. A Ready endpoint picker alone is not routing evidence.

For sustained load, use actual GuideLLM results with the model, hardware, version, workload, timestamps, and observed errors. Enforce a hard end time independently of an assistant session. Preserve interactive headroom and artifacts; do not rely on a laptop remaining awake.

For cloud capacity, calculate the all-pool physical GPU bound including surge first. Make a bounded ROSA/OCM attempt and use `oc` for node readiness. Do not poll the ROSA/OCM APIs or bypass their ownership through AWS changes. If capacity remains unavailable, revise the live demo scope and record the limitation.

For GitOps, choose the appropriate overlay explicitly. The existing-cluster overlay may reference an established model in another namespace; the portable overlay requires its own models and credentials. Retain only narrowly justified operator-field ignores. Verify convergence and a reversible drift correction.

For release, preserve the distinction between planned, schema-accepted, deployed, tested, and customer-ready. Run the applicable tests and strict documentation build, scan staged content for secrets/private identifiers, inspect the published experience, and update the evidence record. A sanitized public status and a detailed private checkpoint serve different purposes.
