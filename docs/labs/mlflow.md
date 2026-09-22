# MLflow experiments and traces

The platform singleton runs in `redhat-ods-applications`; the workspace is `ai-showroom`. Workbench and workload identities use namespace-scoped Kubernetes authorization.

Open `notebooks/01-demand.ipynb`. Generate the synthetic dataset, inspect the chronological holdout, and publish the measured result. The model artifact is also uploaded to `s3://aurora-artifacts/models/forecast/latest.json` for the MCP backend.

The internal tracking endpoint is `https://mlflow.redhat-ods-applications.svc:8443/mlflow` with the injected service CA. `AURORA_MLFLOW_TRACKING_URI` selects this internal endpoint when the notebook webhook injects a public dashboard URI. Do not disable TLS verification.

The application records retrieval, MCP Gateway calls, and MaaS inference spans after input safety checks. It checks generated output before storing that output in a trace. MLflow workspace artifacts use S3, so this client image includes boto3 and receives credentials from a Kubernetes Secret.

Acceptance: real parent/child runs, measured metrics, a downloadable model artifact, and a trace that can be retrieved after the request completes. An experiment appearing in the UI alone does not prove artifact upload succeeded.

[Official MLflow integration documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-and-authenticating-mlflow-sdk_mlflow).

## Verified records

The distributed forecast parent run is `36ff7fb1b995454f9c6ff840ce211520`; its eight child runs and S3 model artifact were verified. Assistant trace `tr-79086e46512f7aae798803c5c358d0f0` was retrieved with `aurora_replenishment`, `retrieve_tfidf`, `mcp_gateway_tools`, and `maas_inference` spans and saved output. These are real records from the September 22, 2026 validation.

Native pipeline automatic tracking emitted a missing nested run-ID warning. The documented `native-export` helper logs the real S3 artifact index and measured metrics explicitly. EvalHub's `eval-export` helper similarly preserves the actual evaluation result; neither workaround is presented as a fix to the automatic integration.
