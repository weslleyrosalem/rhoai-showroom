#!/usr/bin/env python3
"""Create candidate metadata in a native RHOAI registry, without overwriting entries.

PLAN is the default. This helper never downloads weights, deploys a model,
changes registry permissions, or promotes a candidate. Tokens stay in memory.
"""
import argparse
import datetime
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "/api/model_registry/v1alpha3"
OWNER = "rhoai-showroom"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def oc(*args):
    result = subprocess.run(["oc", "--request-timeout=30s", *args],
                            capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise RuntimeError("oc command failed; inspect the named resource with your administrator")
    return result.stdout.strip()


def resource(kind, name, namespace=None):
    args = ["get", kind, name, "-o", "json"]
    if namespace:
        args += ["-n", namespace]
    return json.loads(oc(*args))


def properties(values):
    return {key: {"metadataType": "MetadataStringValue", "string_value": str(value)}
            for key, value in values.items()}


def validate_candidate(candidate):
    required = {"registered_model_name", "version_name", "artifact_name", "model", "revision",
                "license", "source", "catalog_source", "uri", "runtime_image", "hardware_profile",
                "deployment_manifest", "lifecycle", "runtime_validation", "safety_evaluation",
                "performance_evaluation"}
    if candidate.get("schema_version") != 1 or not required <= candidate.keys():
        raise ValueError("Candidate file is missing required provenance fields")
    if any(not isinstance(candidate[k], str) or not candidate[k].strip() or len(candidate[k]) > 2048
           for k in required):
        raise ValueError("Candidate fields must be bounded nonempty strings")
    if not re.fullmatch(r"[0-9a-f]{40}", candidate["revision"]):
        raise ValueError("Use the full immutable Hugging Face revision")
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", candidate["runtime_image"]):
        raise ValueError("Pin the runtime image by digest")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", candidate["model"]):
        raise ValueError("Use a Hugging Face organization/model identifier")
    if candidate["uri"] != f"hf://{candidate['model']}:{candidate['revision']}":
        raise ValueError("Artifact URI must match the immutable model revision")
    if candidate["source"] != f"https://huggingface.co/{candidate['model']}":
        raise ValueError("Source must identify the same public model")
    if candidate["lifecycle"] != "candidate" or any(candidate[k] != "NOT_RUN" for k in
            ["runtime_validation", "safety_evaluation", "performance_evaluation"]):
        raise ValueError("This onboarding helper only creates unvalidated candidates")
    return candidate


def assert_matches(existing, desired):
    """Never adopt a same-name entry or rewrite measured lifecycle evidence."""
    if existing.get("customProperties", {}).get("showroom.owner", {}).get("string_value") != OWNER:
        raise ValueError("Same-name registry entry is not owned by this showroom; refusing to adopt it")
    for key, value in desired.items():
        if key == "customProperties":
            for prop, expected in value.items():
                # A later, separately audited evaluation can change these states.
                if prop in {"showroom.lifecycle", "showroom.runtime_validation",
                            "showroom.safety_evaluation", "showroom.performance_evaluation"}:
                    continue
                if existing.get(key, {}).get(prop) != expected:
                    raise ValueError(f"Existing registry provenance differs: {prop}")
        elif key == 'description' and 'registeredModelId' in desired:
            continue  # Version summaries can evolve with separately audited runtime evidence.
        elif existing.get(key) != value:
            raise ValueError(f"Existing registry field differs: {key}")


class RegistryClient:
    def __init__(self, endpoint, token):
        self.endpoint = endpoint
        self.token = token
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def request(self, path, body=None, method=None):
        if not path.startswith(API + "/") or ".." in path:
            raise ValueError("Registry API path is invalid")
        request = urllib.request.Request(self.endpoint + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise ValueError("Registry response exceeds the bounded response size")
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Registry API returned HTTP {error.code}; no response body was logged") from None

    def items(self, path):
        output = []
        token = ""
        seen = set()
        for _ in range(100):
            query = urllib.parse.urlencode({"pageSize": "100", "nextPageToken": token})
            page = self.request(path + "?" + query)
            output.extend(page.get("items", []))
            token = page.get("nextPageToken", "")
            if not token:
                return output
            if token in seen:
                raise RuntimeError("Registry pagination did not advance")
            seen.add(token)
        raise RuntimeError("Registry exceeds the bounded inventory size")


def ensure_entry(client, path, desired, apply):
    matches = [item for item in client.items(path) if item.get("name") == desired["name"]]
    if len(matches) > 1:
        raise ValueError("Registry returned duplicate names; resolve the ambiguity before onboarding")
    if matches:
        assert_matches(matches[0], desired)
        if not re.fullmatch(r"[1-9][0-9]*", str(matches[0].get("id", ""))):
            raise ValueError("Registry returned an invalid existing resource ID")
        return matches[0], "preserved"
    if not apply:
        return {"id": "PLAN", **desired}, "would_create"
    created = client.request(path, desired)
    assert_matches(created, desired)
    if not re.fullmatch(r"[1-9][0-9]*", str(created.get("id", ""))):
        raise RuntimeError("Registry did not return a valid created resource ID")
    return created, "created"


def onboard(client, candidate, apply):
    common = {"showroom.owner": OWNER}
    registered = {"name": candidate["registered_model_name"], "owner": OWNER,
                  "description": "Aurora Supply candidate model. Registration does not approve deployment or evaluation.",
                  "customProperties": properties(common)}
    model, model_action = ensure_entry(client, API + "/registered_models", registered, apply)
    metadata = {**common, **{"showroom." + k: v for k, v in candidate.items()
               if k not in {"schema_version", "registered_model_name", "version_name", "artifact_name", "uri"}}}
    version = {"name": candidate["version_name"], "registeredModelId": model["id"],
               "author": OWNER, "description": "Pinned candidate; consult lifecycle evidence. Registration does not approve runtime, safety, or performance.",
               "customProperties": properties(metadata)}
    artifact = {"name": candidate["artifact_name"], "artifactType": "model-artifact",
                "uri": candidate["uri"], "modelFormatName": "safetensors",
                "description": "Public Hugging Face weights at an immutable revision; no weights are copied by registration.",
                "customProperties": properties({**common, "showroom.revision": candidate["revision"],
                                               "showroom.license": candidate["license"]})}
    if model["id"] == "PLAN":
        version_object, version_action = {"id": "PLAN"}, "would_create"
    else:
        version_object, version_action = ensure_entry(client,
            API + f"/registered_models/{model['id']}/versions", version, apply)
    if version_object["id"] == "PLAN":
        artifact_object, artifact_action = {"id": "PLAN"}, "would_create"
    else:
        artifact_object, artifact_action = ensure_entry(client,
            API + f"/model_versions/{version_object['id']}/artifacts", artifact, apply)
    return {"registered_model": {"id": model["id"], "action": model_action},
            "model_version": {"id": version_object["id"], "action": version_action},
            "model_artifact": {"id": artifact_object["id"], "action": artifact_action}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path(__file__).parent / "registry/qwen-4b-candidate.json")
    parser.add_argument("--registry", default="aurora-registry")
    parser.add_argument("--namespace", default="rhoai-model-registries")
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--expected-user", required=True)
    parser.add_argument("--apply", action="store_true", help="Create absent metadata entries; never overwrite or promote")
    args = parser.parse_args()
    candidate = validate_candidate(json.loads(args.candidate.read_text()))
    if oc("whoami", "--show-server") != args.expected_server or oc("whoami") != args.expected_user:
        raise ValueError("Current cluster or identity does not match the explicit guard")
    registry = resource("modelregistries.modelregistry.opendatahub.io", args.registry, args.namespace)
    if not any(c.get("type") == "Available" and c.get("status") == "True"
               for c in registry.get("status", {}).get("conditions", [])):
        raise ValueError("The namespaced registry instance is not Available")
    route = resource("route", args.registry + "-https", args.namespace)
    if (route.get("spec", {}).get("to", {}).get("name") != args.registry or
            route.get("spec", {}).get("tls", {}).get("termination") != "reencrypt"):
        raise ValueError("Expected an authenticated registry service behind a reencrypt Route")
    if not any(owner.get("uid") == registry["metadata"]["uid"] for owner in route["metadata"].get("ownerReferences", [])):
        raise ValueError("The Route is not owned by this registry instance")
    if not registry["spec"].get("kubeRBACProxy"):
        raise ValueError("This helper requires the registry kube-rbac-proxy")
    host = route["spec"]["host"]
    domain = resource("ingress.config.openshift.io", "cluster")["spec"]["domain"]
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", host) or not host.endswith("." + domain):
        raise ValueError("The registry Route host is outside the current cluster ingress domain")
    client = RegistryClient("https://" + host, oc("whoami", "-t"))
    result = onboard(client, candidate, args.apply)
    print(json.dumps({"mode": "APPLY" if args.apply else "PLAN",
                      "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      "registry": args.registry, "namespace": args.namespace,
                      "model": candidate["model"], "revision": candidate["revision"],
                      "registration_is_not_approval": True, "result": result}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        sys.exit(2)
