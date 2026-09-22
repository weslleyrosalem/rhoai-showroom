# Aurora's private matched-evaluation adapter

This small custom integration compares the **same MaaS model** before and after the deployed NeMo `showroom-safety` rules. It is not a separate model, Red Hat product component, or general purpose inference gateway. It serves only nonstreaming OpenAI-compatible chat requests for a bounded evaluation.

The adapter checks every input message, calls the fixed upstream with the original messages and parameters, and checks the response. A known block returns a deterministic refusal; unknown verdicts or unavailable dependencies deny the request with HTTP503. It never invokes tools or creates purchase orders. Existing regex rules detect synthetic identifiers and explicit override phrases; they do not provide broad semantic prompt-injection detection.

## Deployment

Review the opt-in Kustomize component at `gitops/components/guardrails/evaluation`. It creates no Route and requests no GPU. Only the EvalHub evaluation pods and the named workbench can reach its HTTPS Service. Egress permits cluster DNS, the NeMo service, and public HTTPS for the fixed MaaS endpoint. Public HTTPS egress is not a hostname-level allowlist; the application itself fixes the destination. The adapter runs with an arbitrary OpenShift UID, a read-only root filesystem, dropped capabilities, and one active request.

After independently checking `oc whoami --show-server` and the expected identity:

```bash
oc apply -k gitops/components/guardrails/evaluation
showroom_build_dir=$(mktemp -d)
cp apps/aurora-guarded-model/server.py apps/aurora-guarded-model/Containerfile "$showroom_build_dir/"
oc start-build aurora-guarded-model -n ai-showroom \
  --from-dir="$showroom_build_dir" --follow
oc rollout restart deployment/aurora-guarded-model -n ai-showroom
oc rollout status deployment/aurora-guarded-model -n ai-showroom
```

The binary build directory contains only `server.py` and `Containerfile`. Do not add credentials, virtual environments, or raw reports to it. The image base is digest-pinned; no additional packages are installed.

The caller uses the existing scoped MaaS key. `scripts/security_evaluations.py --target guarded` prepares an owned Secret with that key and the OpenShift service CA, using EvalHub's supported `ca_cert` model-auth field. Secrets and prompts are never written to the public repository or application logs. Re-run the helper and restart this Deployment after rotating the source MaaS key: the Deployment reads the source key through its environment.

See the [complete evaluation walkthrough](https://weslleyrosalem.github.io/rhoai-showroom/labs/owasp-evaluations/) for the exact probes, results, control gaps, and scoring rules.
