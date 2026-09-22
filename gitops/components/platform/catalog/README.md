# Curated shared catalog

`source.json` is a source entry, not a Kubernetes resource. `merge_catalog.py` requires PyYAML and is read-only by default. It merges only `showroom-qwen`, preserves all other entries and top-level keys, and uses a resourceVersion test before a JSON Patch.

Use the installation's Python tools environment with PyYAML installed. Run with `--expected-server "$EXPECTED_OPENSHIFT_SERVER"`, review the plan, then use `--apply` when integrating the authorized installation. A differently named source with the same id blocks the operation. A concurrent update also blocks; rerun from fresh state.

This avoids two Argo Applications overwriting a shared ConfigMap. Keep source ownership deliberate: either integrate this merge in the installation workflow, or have the cluster owner incorporate the entry in its single authoritative ConfigMap repository. Do not have both the UI and two controllers compete over the full file.

See [model catalog lab](../../../../docs/labs/model-catalog.md).
