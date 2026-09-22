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
