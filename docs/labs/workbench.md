# Aurora workbench

Open project `ai-showroom`, then workbench **Aurora Supply — Data Science Lab**. It has a persistent 10 GiB workspace, CPU resources, OpenShift authentication, the service CA, and MLflow integration.

The initialization container clones the public repository into `/opt/app-root/src/rhoai-showroom`. It does not overwrite an existing checkout. Use `git pull --ff-only` when you want an updated lab and have no conflicting local edits.

Run notebooks in order:

1. `01-demand.ipynb`: data, measured forecast, MLflow, and S3.
2. `02-rag.ipynb`: retrieval and the real assistant request.
3. `03-ray.ipynb`: inspect and launch distributed CPU training.
4. `04-evaluation.ipynb`: inspect providers and run a measured evaluation.
5. `05-native-autorag.ipynb`: inspect a completed native pattern and run semantic inference.

The notebook controller creates its own service account, `aurora-lab`. Evaluation access is explicitly bound to that account. Administrative setup commands run from the presenter's authenticated terminal, not by granting cluster administration to the notebook.

Acceptance: authenticated access, persisted files after restart, dataset execution, and a real MLflow write.

The base image uses its own Python environment. Re-run each notebook's pinned dependency cell after a workbench restart; the workspace files persist, while packages installed in the container environment do not.
