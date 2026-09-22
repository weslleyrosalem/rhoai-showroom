# AI Pipelines

`showroom-pipelines` uses the showroom S3 service and enables native managed pipelines for AutoML and AutoRAG. Inspect its Ready condition before submitting work:

```bash
oc get dspa showroom-pipelines -n ai-showroom
```

The repository also includes `notebooks/aurora_pipeline.py` and its compiled YAML: generate data → train the CPU baseline → enforce the quality gate. This lightweight example demonstrates artifacts and dependencies. It is distinct from the two-worker Ray job and from native AutoML.

Compile with the pinned SDK:

```bash
pip install kfp==2.15.2
python notebooks/aurora_pipeline.py
```

For reproducible execution, pass a reviewed Git commit as `source_ref`. The default `main` is convenient for a live workshop but changes over time. The compiled component uses an operator-compatible Python runtime image.

Acceptance: a real completed pipeline run, preserved artifacts, visible task dependencies, and a quality gate failure when deliberately given an unacceptable candidate. Native AutoML/AutoRAG runs have their own capacity and validation requirements.

## Observed native runs

The native AutoML and AutoRAG pipelines completed on September 22, 2026, using the installed managed pipeline version 3.5.1 and real S3 artifacts. Their labs record the measured scores and limitations. The lightweight `aurora_pipeline.py` example is supplied and compiled; it has not been executed in the live validation.

Pipeline-level automatic MLflow tracking reported missing nested run IDs in this cluster. `science.py native-export` explicitly preserves the native run's real artifact index and metrics without claiming that the automatic integration succeeded.

The showroom disables DSPA task caching so an explicit test-drive run performs real work, including recreating external vector-store side effects when requested. Content-addressed corpus keys still record input lineage. Re-enabling caching requires reviewing which tasks have external state; a cached successful optimization alone does not prove its vector store still exists.

Managed pipeline compilation uses the verified 3.5.1 components image and its default pipeline set. An explicit name allowlist triggers a separate operator OCI-manifest validation path that lacked Red Hat Registry credentials in this cluster; the image itself still pulls through the cluster's normal authenticated image mechanism. The default set was verified through the pipeline API. No registry credentials are copied into this repository.

The current automatic MLflow integration creates and finishes the pipeline parent run. Task-level callbacks warn about a missing nested run ID and produce no child metrics. The explicit SDK export preserves the actual model/pattern result files and metrics; it does not repair the callback issue.
