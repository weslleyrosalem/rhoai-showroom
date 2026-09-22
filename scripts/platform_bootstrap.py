#!/usr/bin/env python3
"""Read-only operator bootstrap planner for a new ROSA showroom cluster.

This script has no apply mode. It preserves installed operator packages and
renders create-only OLM resources with Manual InstallPlan approval for absent
packages. Review the plan and all dependency versions before any installation.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "gitops/bootstrap/operators/operators.lock.json"
OWNER = {"app.kubernetes.io/part-of": "rhoai-showroom"}


def oc_json(*args):
    result = subprocess.run(["oc", "--request-timeout=30s", *args], text=True,
                            capture_output=True, timeout=40)
    if result.returncode:
        raise RuntimeError("Read-only cluster inspection failed; verify API access and operator catalogs")
    return json.loads(result.stdout)


def guard(server, user):
    for argument, expected in [("--show-server", server), (None, user)]:
        command = ["oc", "whoami"] + ([argument] if argument else [])
        actual = subprocess.run(command, text=True, capture_output=True, check=True, timeout=30).stdout.strip()
        if actual != expected:
            raise ValueError("Current cluster or identity differs from the explicit context guard")


def operator_resources(pin, namespace_exists, groups):
    """Return only resources absent from the current namespace inventory."""
    ns = pin["namespace"]
    target = [ns] if pin["operator_group_scope"] == "namespace" else []
    if len(groups) > 1:
        raise ValueError(f"Namespace {ns} has multiple OperatorGroups")
    if groups and (groups[0].get("spec", {}).get("selector") or
                   groups[0].get("spec", {}).get("targetNamespaces", []) != target):
        raise ValueError(f"Namespace {ns} has an incompatible existing OperatorGroup")
    resources = []
    if not namespace_exists:
        resources.append({"apiVersion": "v1", "kind": "Namespace",
                          "metadata": {"name": ns, "labels": OWNER}})
    if not groups:
        resources.append({"apiVersion": "operators.coreos.com/v1", "kind": "OperatorGroup",
            "metadata": {"name": "showroom-operators", "namespace": ns, "labels": OWNER},
            "spec": {"targetNamespaces": target} if target else {}})
    resources.append({"apiVersion": "operators.coreos.com/v1alpha1", "kind": "Subscription",
        "metadata": {"name": pin["package"], "namespace": ns, "labels": OWNER},
        "spec": {"name": pin["package"], "channel": pin["channel"],
                 "source": pin["catalog_source"], "sourceNamespace": pin["catalog_namespace"],
                 "startingCSV": pin["starting_csv"], "installPlanApproval": "Manual"}})
    return resources


def verify_pin(pin, manifest):
    status = manifest.get("status", {})
    if (status.get("catalogSource") != pin["catalog_source"] or
            status.get("catalogSourceNamespace") != pin["catalog_namespace"]):
        raise ValueError(f"Unexpected catalog source for {pin['package']}")
    channels = [c for c in status.get("channels", []) if c.get("name") == pin["channel"]]
    if len(channels) != 1:
        raise ValueError(f"Pinned channel is unavailable for {pin['package']}")
    channel = channels[0]
    available = {entry.get("name") for entry in channel.get("entries", [])}
    available.add(channel.get("currentCSV"))
    if pin["starting_csv"] not in available:
        raise ValueError(f"Pinned CSV is unavailable for {pin['package']}; no version substitution was made")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--expected-user", required=True)
    parser.add_argument("--verify-pins", action="store_true", help="Also verify catalog pins for already installed packages")
    parser.add_argument("--output", type=Path, help="Write a new JSON plan file; refuse to overwrite an existing file")
    args = parser.parse_args()
    guard(args.expected_server, args.expected_user)
    lock = json.loads(LOCK.read_text())
    subscriptions = oc_json("get", "subscriptions", "-A", "-o", "json")["items"]
    csvs = oc_json("get", "csv", "-A", "-o", "json")["items"]
    groups = oc_json("get", "operatorgroups", "-A", "-o", "json")["items"]
    namespaces = {x["metadata"]["name"] for x in oc_json("get", "namespaces", "-o", "json")["items"]}
    ocp = oc_json("get", "clusterversion", "version", "-o", "json")["status"]["desired"]["version"]
    entries, resources, blocked = [], [], []
    planned_namespaces, planned_groups = set(), set()
    for pin in lock["operators"]:
        package = pin["package"]
        existing = [s for s in subscriptions if s["spec"]["name"] == package]
        # A CSV without a Subscription may still own the operator. Never create a duplicate.
        orphan_csvs = [c for c in csvs if any(k == "operators.coreos.com/" + package + "." + c["metadata"]["namespace"]
                      for k in c["metadata"].get("labels", {})) and not c["metadata"].get("annotations", {}).get("olm.copiedFrom")]
        entry = {"package": package, "pinned_csv": pin["starting_csv"]}
        try:
            if not existing or args.verify_pins:
                verify_pin(pin, oc_json("get", "packagemanifest", package, "-n", pin["catalog_namespace"], "-o", "json"))
            if existing or orphan_csvs:
                entry.update(action="PRESERVE_EXISTING", subscriptions=[{
                    "namespace": s["metadata"]["namespace"], "name": s["metadata"]["name"],
                    "installed_csv": s.get("status", {}).get("installedCSV"),
                    "channel": s["spec"].get("channel")} for s in existing],
                    csv_without_subscription=not bool(existing))
            else:
                if ocp.split(".")[:2] != lock["observed_openshift_version"].split(".")[:2]:
                    raise ValueError("Fresh-install pins require an OpenShift minor-version compatibility review")
                ns = pin["namespace"]
                ns_groups = [g for g in groups if g["metadata"]["namespace"] == ns]
                rendered = operator_resources(pin, ns in namespaces or ns in planned_namespaces, ns_groups)
                for item in rendered:
                    if item["kind"] == "OperatorGroup" and ns in planned_groups:
                        continue
                    resources.append(item)
                    if item["kind"] == "Namespace":
                        planned_namespaces.add(ns)
                    if item["kind"] == "OperatorGroup":
                        planned_groups.add(ns)
                entry["action"] = "WOULD_CREATE_MANUAL_SUBSCRIPTION"
        except (ValueError, RuntimeError) as error:
            entry.update(action="BLOCKED", reason=str(error))
            blocked.append(package)
        entries.append(entry)
    result = {"mode": "PLAN_ONLY", "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "observed_openshift_version": ocp, "fresh_install_validation": "NOT_RUN",
        "automatic_operator_changes": False, "blocked_packages": blocked, "operators": entries,
        "create_only_resources": {"apiVersion": "v1", "kind": "List", "items": resources},
        "next_gate": "Review every OLM InstallPlan dependency/version before manual approval; then verify operator health and platform APIs."}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result, indent=2))
    return 2 if blocked else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        sys.exit(2)
