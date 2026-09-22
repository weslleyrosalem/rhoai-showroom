# Prompt versions and review

**Customer question:** how do we make a prompt change reviewable instead of copying another string into an application?

Open **Gen AI studio → Prompts**, select **AI Showroom**, and open `aurora-replenishment-review`. The native MLflow prompt registry contains two actual versions:

| Version | Alias | Change |
|---|---|---|
| 1 | `baseline` | Summarize inventory from supplied facts and cite policy |
| 2 | `demo` | Separate inventory, forecast horizon, policy, and proposal; preserve supplied totals and identify required approval |

Both versions use synthetic inputs and explicitly leave ordering to a human. A better-written prompt is not a security boundary or a passed evaluation. Compare behavior with the same facts and retain evaluation evidence before promoting a change in a real application.

## Presenter interaction

Show the native prompt list and version number. Open the prompt, compare the wording, and explain the two variables: `sku` and `facts`. A participant can draft a new version with one additional requirement, review the difference, and decide whether to save it. Keep the original versions for comparison.

The Aurora application's existing production-of-the-demo prompt is configured separately. Registering a prompt does not silently change its runtime behavior. Use this lab to demonstrate prompt lifecycle and version selection; wire an approved version into an application explicitly.

## Reproduce the initial versions

Run the repository helper inside the `aurora-lab` Workbench, whose scoped identity has access to the showroom MLflow workspace. Review the expected service before applying:

```bash
python scripts/prompt_registry.py \
  --expected-tracking-uri https://mlflow.redhat-ods-applications.svc:8443/mlflow
```

The command prints a plan. Add `--apply` to create the two versions and aliases. It verifies the namespace and HTTPS tracking endpoint, keeps credentials in process memory, refuses conflicting existing template content, and reuses identical versions. A repeated seed was tested and retained versions 1 and 2.

Primary source: [MLflow prompt creation and versioning](https://mlflow.org/docs/latest/genai/prompt-registry/create-and-edit-prompts/).
