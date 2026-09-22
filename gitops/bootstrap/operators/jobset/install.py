#!/usr/bin/env python3
"""Install the reviewed JobSet prerequisite, then enable only RHOAI Trainer."""
import argparse
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PIN = json.loads((HERE / "pin.json").read_text())
OWNER = "showroom.aurora/owner"


def oc(*args, payload=None):
    return subprocess.check_output(
        ["oc", "--request-timeout=30s", *args], text=True,
        input=json.dumps(payload) if payload is not None else None).strip()


def get(kind, name, namespace=None):
    scope = ["-n", namespace] if namespace else []
    raw = oc("get", kind, name, *scope, "--ignore-not-found", "-o", "json")
    return json.loads(raw) if raw else None


def objects():
    ns = PIN["namespace"]
    metadata = {"name": "job-set", "namespace": ns,
                "annotations": {OWNER: "rhoai-showroom"}}
    return [
        {"apiVersion": "v1", "kind": "Namespace", "metadata": {
            "name": ns, "annotations": {OWNER: "rhoai-showroom"},
            "labels": {"openshift.io/cluster-monitoring": "true"}}},
        {"apiVersion": "operators.coreos.com/v1", "kind": "OperatorGroup",
         "metadata": metadata,
         "spec": {"targetNamespaces": [ns], "upgradeStrategy": "Default"}},
        {"apiVersion": "operators.coreos.com/v1alpha1", "kind": "Subscription",
         "metadata": metadata,
         "spec": {"name": PIN["package"], "channel": PIN["channel"],
                  "source": PIN["catalog"], "sourceNamespace": PIN["catalog_namespace"],
                  "startingCSV": PIN["csv"], "installPlanApproval": "Manual"}},
    ]


def verify_catalog():
    package = get("packagemanifest", PIN["package"], PIN["catalog_namespace"])
    if not package or package["status"].get("catalogSource") != PIN["catalog"]:
        raise SystemExit("The pinned official package is unavailable.")
    channel = next((c for c in package["status"].get("channels", [])
                    if c["name"] == PIN["channel"]), {})
    if channel.get("currentCSV") != PIN["csv"]:
        raise SystemExit("The catalog head changed; review the pin before continuing.")
    images = channel.get("currentCSVDesc", {}).get("relatedImages", [])
    if set(images) != set(PIN["related_images"]):
        raise SystemExit("The pinned package images changed; stopping.")
    if not get("crd", "certificates.cert-manager.io"):
        raise SystemExit("Install the documented cert-manager prerequisite first.")


def verify_owned(obj):
    meta = obj["metadata"]
    current = get(obj["kind"], meta["name"], meta.get("namespace"))
    if current and current["metadata"].get("annotations", {}).get(OWNER) != "rhoai-showroom":
        raise SystemExit("An existing unowned resource conflicts with this isolated installation.")
    if current and obj["kind"] != "Namespace" and current.get("spec") != obj.get("spec"):
        raise SystemExit("An existing resource differs from the pinned plan; review it first.")
    return current


def approve_plan(name, apply):
    sub = get("subscription", "job-set", PIN["namespace"])
    plan = get("installplan", name, PIN["namespace"])
    if not sub or not plan or sub.get("status", {}).get("installPlanRef", {}).get("name") != name:
        raise SystemExit("This is not the InstallPlan referenced by the owned subscription.")
    if sub["metadata"].get("annotations", {}).get(OWNER) != "rhoai-showroom":
        raise SystemExit("The subscription is not owned by this installation.")
    if plan["spec"].get("clusterServiceVersionNames") != [PIN["csv"]]:
        raise SystemExit("Unexpected CSVs or transitive operator dependencies; review manually.")
    for step in plan.get("status", {}).get("plan", []):
        resource = step.get("resource", {})
        if resource.get("catalogSource") not in (None, "", PIN["catalog"]):
            raise SystemExit("InstallPlan contains a resource from an unexpected catalog.")
    if apply and not plan["spec"].get("approved"):
        patch = [{"op": "test", "path": "/metadata/resourceVersion", "value": plan["metadata"]["resourceVersion"]},
                 {"op": "test", "path": "/spec/clusterServiceVersionNames", "value": [PIN["csv"]]},
                 {"op": "replace", "path": "/spec/approved", "value": True}]
        oc("patch", "installplan", name, "-n", PIN["namespace"], "--type=json", "-p", json.dumps(patch))
    return {"install_plan": name, "csv": PIN["csv"]}


def enable_operand(apply):
    csv = get("csv", PIN["csv"], PIN["namespace"])
    if not csv or csv.get("status", {}).get("phase") != "Succeeded":
        raise SystemExit("The pinned CSV must reach Succeeded first.")
    obj = {"apiVersion": "operator.openshift.io/v1", "kind": "JobSetOperator",
           "metadata": {"name": "cluster", "annotations": {OWNER: "rhoai-showroom"}},
           "spec": {"managementState": "Managed", "logLevel": "Normal", "operatorLogLevel": "Normal"}}
    current = verify_owned(obj)
    if apply and not current:
        oc("create", "-f", "-", payload=obj)
    return {"operand": "JobSetOperator/cluster", "managementState": "Managed"}


def enable_trainer(backup, apply):
    jobset = get("crd", "jobsets.jobset.x-k8s.io")
    if not jobset or not any(c.get("type") == "Established" and c.get("status") == "True"
                              for c in jobset.get("status", {}).get("conditions", [])):
        raise SystemExit("The JobSet CRD must be Established first.")
    operand = get("jobsetoperator", "cluster")
    if not operand or not any(c.get("type") == "Available" and c.get("status") == "True"
                               for c in operand.get("status", {}).get("conditions", [])):
        raise SystemExit("The JobSet operand must be Available first.")
    rh = get("csv", "rhods-operator." + PIN["rhoaiversion"], "redhat-ods-operator")
    if not rh or rh.get("status", {}).get("phase") != "Succeeded":
        raise SystemExit("This helper requires the reviewed RHOAI release.")
    all_dsc = json.loads(oc("get", "dsc", "-o", "json"))["items"]
    if len(all_dsc) != 1:
        raise SystemExit("Expected exactly one DataScienceCluster.")
    dsc = all_dsc[0]
    components = dsc["spec"]["components"]
    trainer = components.get("trainer", {})
    if trainer.get("managementState") not in ("Managed", "Removed"):
        raise SystemExit("Unexpected Trainer configuration; review it first.")
    before = {k: components.get(k) for k in ("kueue", "trainingoperator")}
    if apply and trainer.get("managementState") != "Managed":
        if not backup:
            raise SystemExit("A private, new backup file is required before the shared DSC change.")
        backup = backup.expanduser().resolve()
        root = HERE.parents[3]
        if backup == root or root in backup.parents:
            raise SystemExit("The private DSC backup must stay outside the public repository.")
        backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(dsc, stream, indent=2)
        patch = [{"op": "test", "path": "/metadata/resourceVersion", "value": dsc["metadata"]["resourceVersion"]},
                 {"op": "replace", "path": "/spec/components/trainer/managementState", "value": "Managed"}]
        oc("patch", "dsc", dsc["metadata"]["name"], "--type=json", "-p", json.dumps(patch))
        after = get("dsc", dsc["metadata"]["name"])["spec"]["components"]
        if any(after.get(k) != value for k, value in before.items()):
            raise SystemExit("An unrelated shared component changed concurrently; inspect its owner.")
    return {"trainer": "Managed", "kueue_preserved": True, "trainingoperator_preserved": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("subscription", "approve", "operand", "trainer"))
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--expected-user", default="aiadmin")
    parser.add_argument("--install-plan")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if oc("whoami", "--show-server") != args.expected_server or oc("whoami") != args.expected_user:
        raise SystemExit("Unexpected cluster or identity; stopping.")
    verify_catalog()
    if args.action == "subscription":
        desired = objects()
        subscriptions = json.loads(oc("get", "subscription", "-A", "-o", "json"))["items"]
        if any(o.get("spec", {}).get("name") == PIN["package"] and
               (o["metadata"]["namespace"] != PIN["namespace"] or o["metadata"]["name"] != "job-set")
               for o in subscriptions):
            raise SystemExit("JobSet already has another subscription; preserve its owner.")
        if get("namespace", PIN["namespace"]):
            groups = json.loads(oc("get", "operatorgroup", "-n", PIN["namespace"], "-o", "json"))["items"]
            if any(g["metadata"]["name"] != "job-set" for g in groups):
                raise SystemExit("An existing OperatorGroup conflicts with the single-namespace plan.")
        for obj in desired:
            current = verify_owned(obj)
            if args.apply and not current:
                oc("create", "-f", "-", payload=obj)
        result = {"csv": PIN["csv"], "approval": "Manual", "namespace": PIN["namespace"]}
    elif args.action == "approve":
        if not args.install_plan:
            raise SystemExit("Pass the exact reviewed --install-plan name.")
        result = approve_plan(args.install_plan, args.apply)
    elif args.action == "operand":
        result = enable_operand(args.apply)
    else:
        result = enable_trainer(args.backup, args.apply)
    print(json.dumps({"mode": "APPLIED" if args.apply else "PLAN", **result}))


if __name__ == "__main__":
    main()
