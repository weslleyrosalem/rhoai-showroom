#!/usr/bin/env python3
"""Synthetic Aurora data and reproducible CPU demand models (standard library).

The Ray command adds Ray/MLflow/boto3; local generate/train need no packages.
No external customer data, credentials or network are needed for local tests.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import random
import socket

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = [
    dict(sku="AS-001", name="H20 Hydraulic Filter", category="Filters", stock=45, reorder_point=80, unit_price=42.0, lead_time_days=5),
    dict(sku="AS-002", name="P10 Pressure Sensor", category="Sensors", stock=120, reorder_point=35, unit_price=125.0, lead_time_days=7),
    dict(sku="AS-003", name="V30 Control Valve", category="Valves", stock=18, reorder_point=30, unit_price=210.0, lead_time_days=10),
    dict(sku="AS-004", name="M15 Industrial Hose", category="Hoses", stock=240, reorder_point=70, unit_price=32.0, lead_time_days=4),
    dict(sku="AS-005", name="O25 O-ring Seal", category="Seals", stock=75, reorder_point=100, unit_price=8.5, lead_time_days=3),
    dict(sku="AS-006", name="C40 Quick Connector", category="Connectors", stock=90, reorder_point=50, unit_price=18.0, lead_time_days=6),
    dict(sku="AS-007", name="B50 Compact Pump", category="Pumps", stock=8, reorder_point=12, unit_price=650.0, lead_time_days=14),
    dict(sku="AS-008", name="F60 Flow Meter", category="Meters", stock=35, reorder_point=15, unit_price=290.0, lead_time_days=8),
]


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def generate(destination, seed=351):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "products.json", PRODUCTS)
    rng = random.Random(seed)
    rows = []
    first = dt.date(2025, 1, 1)
    for index, product in enumerate(PRODUCTS):
        base = [12, 5, 4, 14, 20, 9, 2, 3][index]
        for day in range(365):
            date = first + dt.timedelta(days=day)
            promotion = int(140 <= day % 180 < 152)
            weekly = 1.0 + 0.22 * math.sin(2 * math.pi * date.weekday() / 7)
            mean = base * weekly * (1 + 0.0015 * day) + promotion * base * 0.35
            units = max(0, round(mean + rng.gauss(0, base * 0.08)))
            rows.append(dict(date=date.isoformat(), sku=product["sku"], units=units,
                             promotion=promotion, unit_price=product["unit_price"],
                             lead_time_days=product["lead_time_days"]))
    with (destination / "demand.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    write_json(destination / "provenance.json", {
        "description": "Aurora Supply: fictional products and synthetic daily demand",
        "license": "CC0-1.0", "seed": seed, "rows": len(rows), "days": 365,
        "sha256": hashlib.sha256((destination / "demand.csv").read_bytes()).hexdigest(),
        "split": "chronological; last 28 days held out; target is next-day units",
    })
    return rows


def read_rows(path):
    with Path(path).open() as f:
        return [dict(row, units=int(row["units"]), promotion=int(row["promotion"]))
                for row in csv.DictReader(f)]


def solve(matrix, vector):
    """Gaussian elimination for the small ridge normal equation."""
    n = len(vector)
    augmented = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for i in range(n):
        pivot = max(range(i, n), key=lambda j: abs(augmented[j][i]))
        augmented[i], augmented[pivot] = augmented[pivot], augmented[i]
        if abs(augmented[i][i]) < 1e-12:
            raise ValueError("Singular model matrix")
        scale = augmented[i][i]
        augmented[i] = [v / scale for v in augmented[i]]
        for j in range(n):
            if j != i:
                scale = augmented[j][i]
                augmented[j] = [a - scale * b for a, b in zip(augmented[j], augmented[i])]
    return [row[-1] for row in augmented]


def features(date, index, promotion):
    weekday = dt.date.fromisoformat(date).weekday()
    return [1.0, index / 365.0, math.sin(2 * math.pi * weekday / 7),
            math.cos(2 * math.pi * weekday / 7), float(promotion)]


def train_sku(rows, sku):
    series = sorted([row for row in rows if row["sku"] == sku], key=lambda row: row["date"])
    if len(series) < 60:
        raise ValueError("At least 60 observations required")
    cutoff = len(series) - 28
    x = [features(row["date"], i, row["promotion"]) for i, row in enumerate(series[:cutoff])]
    y = [row["units"] for row in series[:cutoff]]
    p = len(x[0])
    xtx = [[sum(a[i] * a[j] for a in x) + (0.01 if i == j else 0) for j in range(p)] for i in range(p)]
    xty = [sum(a[i] * b for a, b in zip(x, y)) for i in range(p)]
    weights = solve(xtx, xty)
    errors, baseline_errors = [], []
    for i in range(cutoff, len(series)):
        prediction = max(0, sum(a * b for a, b in zip(weights, features(series[i]["date"], i, series[i]["promotion"]))))
        errors.append(abs(prediction - series[i]["units"]))
        # Fixed training-only seasonal baseline: avoids future test-label leakage.
        history = [series[j]["units"] for j in range(cutoff - 28, cutoff)
                   if dt.date.fromisoformat(series[j]["date"]).weekday() == dt.date.fromisoformat(series[i]["date"]).weekday()]
        baseline_errors.append(abs(sum(history) / len(history) - series[i]["units"]))
    mae = sum(errors) / len(errors)
    baseline_mae = sum(baseline_errors) / len(baseline_errors)
    denominator = sum(row["units"] for row in series[cutoff:])
    candidate_mae = mae
    selected_baseline = mae > baseline_mae
    if selected_baseline:
        mae = baseline_mae
    last = dt.date.fromisoformat(series[-1]["date"])
    future = []
    for offset in range(1, 8):
        date = (last + dt.timedelta(days=offset)).isoformat()
        amount = max(0, sum(a * b for a, b in zip(weights, features(date, len(series) - 1 + offset, 0))))
        if selected_baseline:
            seasonal = [r["units"] for r in series[cutoff-28:cutoff] if dt.date.fromisoformat(r["date"]).weekday() == dt.date.fromisoformat(date).weekday()]
            amount = sum(seasonal) / len(seasonal)
        future.append({"date": date, "units": round(amount, 2)})
    return {"sku": sku, "model_type": "seasonal-baseline" if selected_baseline else "ridge-seasonal-trend", "weights": weights,
            "mae": mae, "baseline_mae": baseline_mae, "candidate_mae": candidate_mae,
            "candidate_passed_quality_gate": not selected_baseline,
            "wape": mae * len(errors) / denominator if denominator else None,
            "train_end": series[cutoff - 1]["date"], "test_start": series[cutoff]["date"],
            "test_end": series[-1]["date"], "forecast": future,
            "forecast_7d_units": round(sum(x["units"] for x in future), 2),
            "worker": "local-reference", "passed_quality_gate": mae <= baseline_mae}


def bundle(models, rows):
    model_version = hashlib.sha256(json.dumps([{k: v for k, v in m.items() if k != "worker"} for m in models], sort_keys=True).encode()).hexdigest()[:12]
    return {"schema_version": "1", "dataset": "Aurora Supply synthetic demand; 2025 calendar year",
            "model_version": model_version, "horizon_days": 7,
            "forecast_origin": max(row["date"] for row in rows),
            "forecasts": models, "synthetic": True}


def configure_mlflow():
    if os.environ.get("AURORA_MLFLOW_TRACKING_URI"):
        os.environ["MLFLOW_TRACKING_URI"] = os.environ["AURORA_MLFLOW_TRACKING_URI"]
    import mlflow
    token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
    if token_path.exists():
        os.environ["MLFLOW_TRACKING_TOKEN"] = token_path.read_text().strip()
    os.environ.setdefault("MLFLOW_WORKSPACE", "ai-showroom")
    mlflow.set_experiment("aurora-demand")
    return mlflow


def publish(result, tracking=True):
    """Publish a measured artifact to MLflow and S3; fail when integration fails."""
    import boto3
    if not all(m["passed_quality_gate"] and math.isfinite(m["mae"]) for m in result["forecasts"]):
        raise ValueError("Quality gate rejected promotion")
    temp = Path(os.environ.get("TMPDIR", "/tmp")) / "aurora-forecast.json"
    if tracking:
        mlflow = configure_mlflow()
        with mlflow.start_run(run_name="cpu-demand-reference" if all(m["worker"] == "local-reference" for m in result["forecasts"]) else "ray-demand-forecast") as run:
            result["mlflow_run_id"] = run.info.run_id
            mlflow.log_params({"seed": 351, "holdout_days": 28, "workers": 2, "model_version": result["model_version"]})
            for model in result["forecasts"]:
                with mlflow.start_run(run_name=model["sku"], nested=True):
                    mlflow.log_params({"sku": model["sku"], "worker": model["worker"], "model_type": model["model_type"]})
                    mlflow.log_metrics({"mae": model["mae"], "baseline_mae": model["baseline_mae"]})
            write_json(temp, result)
            mlflow.log_artifact(str(temp), artifact_path="model")
    else:
        write_json(temp, result)
    client = boto3.client("s3", endpoint_url=os.environ["AWS_S3_ENDPOINT"], region_name="us-east-1")
    client.upload_file(str(temp), "aurora-artifacts", "models/forecast/latest.json")
    return result


def ray_train(rows):
    import ray
    ray.init(address="auto")
    @ray.remote(num_cpus=1)
    class Trainer:
        def fit(self, series, skus):
            return [dict(train_sku(series, sku), worker=socket.gethostname()) for sku in skus]
    workers = [Trainer.remote(), Trainer.remote()]
    outputs = ray.get([workers[i].fit.remote(rows, [p["sku"] for p in PRODUCTS[i::2]]) for i in range(2)])
    models = sorted([model for group in outputs for model in group], key=lambda x: x["sku"])
    if len({m["worker"] for m in models}) < 2:
        raise RuntimeError("Expected two distinct Ray worker pods")
    result = publish(bundle(models, rows))
    print(json.dumps({"status": "completed", "workers": sorted({m["worker"] for m in models}),
                      "model_version": result["model_version"], "mlflow_run_id": result["mlflow_run_id"]}))
    ray.shutdown()
    return result


def eval_request(path, body=None):
    import subprocess
    import ssl
    import urllib.request
    token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
    token = token_path.read_text().strip() if token_path.exists() else subprocess.check_output(["oc", "whoami", "-t"], text=True).strip()
    base = os.environ["EVALHUB_URL"].rstrip("/")
    headers = {"Authorization": "Bearer " + token, "X-Tenant": "ai-showroom", "Content-Type": "application/json"}
    ca = os.environ.get("EVALHUB_CA")
    context = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()
    request = urllib.request.Request(base + path, data=json.dumps(body).encode() if body else None, headers=headers)
    with urllib.request.urlopen(request, context=context, timeout=60) as response:
        return json.load(response)


def eval_submit():
    provider = eval_request("/api/v1/evaluations/providers/garak")
    if not any(b.get("id") == "quick" for b in provider.get("benchmarks", [])):
        raise ValueError("Installed Garak provider does not expose the quick benchmark")
    base = os.environ["MAAS_BASE_URL"].rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    request = {"name": "aurora-garak-smoke", "model": {"url": base, "name": os.environ["MAAS_MODEL_ID"],
               "auth": {"secret_ref": "showroom-maas-key"}},
               "benchmarks": [{"provider_id": "garak", "id": "quick"}],
               "experiment": {"name": "aurora-model-safety"}}
    result = eval_request("/api/v1/evaluations/jobs", request)
    print(json.dumps({"job_id": result.get("resource", {}).get("id"), "status": result.get("status")}))
    return result


def eval_export(job_id):
    """Persist the actual EvalHub result through the workspace-aware MLflow SDK."""
    result = eval_request("/api/v1/evaluations/jobs/" + job_id)
    mlflow = configure_mlflow()
    client = mlflow.MlflowClient()
    run_ids = sorted({b["mlflow_run_id"] for b in result.get("results", {}).get("benchmarks", []) if b.get("mlflow_run_id")})
    if not run_ids:
        raise ValueError("No completed benchmark MLflow run is available")
    for run_id in run_ids:
        client.log_dict(run_id, result, "evaluation/evalhub-result.json")
    print(json.dumps({"job_id": job_id, "mlflow_runs": run_ids, "artifact": "evaluation/evalhub-result.json"}))
    return result


def ray_submit():
    """Bind only the generated Ray OAuth service account to the MLflow data role."""
    import subprocess
    import time
    namespace = "ai-showroom"
    subprocess.run(["oc", "apply", "-f", str(ROOT / "gitops/components/science/rayjob.yaml")], check=True)
    for _ in range(60):
        job = json.loads(subprocess.check_output(["oc", "get", "rayjob", "aurora-demand-train", "-n", namespace, "-o", "json"]))
        head = job.get("status", {}).get("rayClusterStatus", {}).get("head", {}).get("podName")
        if head:
            pod = json.loads(subprocess.check_output(["oc", "get", "pod", head, "-n", namespace, "-o", "json"]))
            account = pod["spec"]["serviceAccountName"]
            binding = {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding", "metadata": {
                "name": "aurora-ray-mlflow", "namespace": namespace, "ownerReferences": [{"apiVersion": "ray.io/v1", "kind": "RayJob", "name": "aurora-demand-train", "uid": job["metadata"]["uid"]}]},
                "subjects": [{"kind": "ServiceAccount", "name": account, "namespace": namespace}],
                "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "aurora-mlflow-writer"}}
            subprocess.run(["oc", "apply", "-f", "-"], input=json.dumps(binding).encode(), check=True)
            print(json.dumps({"rayjob": "aurora-demand-train", "mlflow_service_account": account}))
            return
        time.sleep(2)
    raise TimeoutError("Ray head pod was not created in 120 seconds")


def native_request(path, body=None):
    """Use the current oc identity; credentials never enter pipeline parameters."""
    import subprocess
    import urllib.request
    if not os.environ.get("KFP_URL"):
        route = json.loads(subprocess.check_output(["oc", "get", "route", "ds-pipeline-showroom-pipelines", "-n", "ai-showroom", "-o", "json"]))
        os.environ["KFP_URL"] = "https://" + route["spec"]["host"]
    token = subprocess.check_output(["oc", "whoami", "-t"], text=True).strip()
    request = urllib.request.Request(os.environ["KFP_URL"].rstrip("/") + path,
                                    data=json.dumps(body).encode() if body is not None else None,
                                    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)



def corpus_prefix(directory):
    """Content-address inputs so KFP never reuses stale document/QA cache entries."""
    directory = Path(directory)
    sources = sorted((directory / "documents").glob("*.md")) + [directory / "eval/autorag.json"]
    digest = hashlib.sha256()
    for source in sources:
        digest.update(str(source.relative_to(directory)).encode() + b"\0" + source.read_bytes())
    return "corpus/" + digest.hexdigest()[:16]


def native_submit(kind):
    """Submit the installed operator-managed 3.5.1 pipeline by name, never copied YAML."""
    names = {"automl": "autogluon-timeseries-training-pipeline", "autorag": "documents-rag-optimization-pipeline"}
    pipelines = native_request("/apis/v2beta1/pipelines?page_size=100").get("pipelines", [])
    pipeline = next((p for p in pipelines if p["display_name"] == names[kind]), None)
    if pipeline is None:
        raise ValueError("Enable managedPipelines in the showroom DSPA first")
    versions = native_request("/apis/v2beta1/pipelines/" + pipeline["pipeline_id"] + "/versions?page_size=100")["pipeline_versions"]
    version = next((v for v in versions if v["display_name"] == "3.5.1"), None)
    if version is None:
        raise ValueError("The required managed pipeline version 3.5.1 is not installed")
    parameters = json.loads((ROOT / "notebooks" / ("native-" + kind + "-parameters.json")).read_text())
    if kind == "autorag":
        import base64
        import subprocess
        model = os.environ.get("MAAS_MODEL_ID")
        if not model:
            secret = json.loads(subprocess.check_output(["oc", "get", "secret", "showroom-maas-key", "-n", "ai-showroom", "-o", "json"]))
            model = base64.b64decode(secret["data"]["model-id"]).decode()
        parameters["generation_models"] = ["aurora-maas/" + model]
        prefix = corpus_prefix(ROOT / "data")
        parameters["input_data_key"] = prefix + "/documents"
        parameters["test_data_key"] = prefix + "/eval/autorag.json"
    experiments = native_request("/apis/v2beta1/experiments?page_size=100").get("experiments", [])
    experiment = next((e for e in experiments if e["display_name"] == "Aurora Supply " + kind), None)
    if experiment is None:
        experiment = native_request("/apis/v2beta1/experiments", {"display_name": "Aurora Supply " + kind, "namespace": "ai-showroom"})
    result = native_request("/apis/v2beta1/runs", {"experiment_id": experiment["experiment_id"],
        "display_name": {"automl": "Aurora demand forecast — three-model comparison", "autorag": "Aurora policy assistant — retrieval quality comparison"}[kind], "pipeline_version_reference": {
            "pipeline_id": pipeline["pipeline_id"], "pipeline_version_id": version["pipeline_version_id"]},
        "runtime_config": {"parameters": parameters}})
    print(json.dumps({"run_id": result["run_id"], "state": result.get("state"), "pipeline": names[kind], "version": version["display_name"]}))
    return result


def native_artifacts(kind, run_id):
    import boto3
    names = {"automl": "autogluon-timeseries-training-pipeline", "autorag": "documents-rag-optimization-pipeline"}
    prefix = names[kind] + "/" + run_id + "/"
    client = boto3.client("s3", endpoint_url=os.environ["AWS_S3_ENDPOINT"], region_name="us-east-1")
    keys = [item["Key"] for page in client.get_paginator("list_objects_v2").paginate(Bucket="aurora-artifacts", Prefix=prefix)
            for item in page.get("Contents", [])]
    if not keys:
        raise ValueError("No pipeline artifacts found; check run completion and S3 configuration")
    return client, keys


def native_export(kind, run_id):
    """Explicitly log native pipeline artifacts when the automatic plugin is unavailable."""
    client, keys = native_artifacts(kind, run_id)
    mlflow = configure_mlflow()
    mlflow.set_experiment("aurora-native-" + kind)
    with mlflow.start_run(run_name=kind + "-artifact-export") as run:
        mlflow.set_tags({"pipeline_run_id": run_id, "tracking_method": "explicit-workspace-sdk-export"})
        mlflow.log_dict({"pipeline_run_id": run_id, "artifacts": ["s3://aurora-artifacts/" + key for key in keys]}, "pipeline/artifact-index.json")
        selected = [k for k in keys if k.endswith("/metrics/metrics.json") or k.endswith("/pattern.json")]
        scored_models = []
        for index, key in enumerate(selected):
            value = json.loads(client.get_object(Bucket="aurora-artifacts", Key=key)["Body"].read())
            mlflow.log_dict(value, "pipeline/result-" + str(index) + ".json")
            if kind == "automl":
                model_name = key.split("/models_artifact/")[-1].split("/")[0]
                mlflow.log_metrics({"model_" + model_name + "_autogluon_score_" + k: v
                                    for k, v in value.items() if isinstance(v, (float, int))})
                if "mean_absolute_error" in value:
                    scored_models.append((value["mean_absolute_error"], model_name))
            else:
                mlflow.log_metrics({"pattern_" + str(index) + "_" + m["name"]: m["scores"]["mean"] for m in value["evaluation"]["metrics"]})
        if scored_models:
            winning_score, winning_model = max(scored_models)
            mlflow.set_tag("selected_model", winning_model)
            mlflow.log_metric("mean_absolute_error", -winning_score)
            mlflow.log_metric("selected_autogluon_score_mean_absolute_error", winning_score)
        result = {"pipeline_run_id": run_id, "mlflow_run_id": run.info.run_id, "artifact_count": len(keys), "exported_result_count": len(selected)}
    print(json.dumps(result))
    return result


def native_infer(run_id, question, use_responses=False, vector_store_id=None):
    """Run the winning native pattern through real OGX retrieval and inference APIs."""
    import urllib.request
    client, keys = native_artifacts("autorag", run_id)
    patterns = [json.loads(client.get_object(Bucket="aurora-artifacts", Key=k)["Body"].read()) for k in keys if k.endswith("/pattern.json")]
    if not patterns:
        raise ValueError("No completed RAG pattern is available")
    def score(pattern):
        return next(m["scores"]["mean"] for m in pattern["evaluation"]["metrics"] if m.get("optimization_metric"))
    pattern = max(patterns, key=score)
    base = os.environ.get("OGX_CLIENT_BASE_URL", "http://lsd-genai-playground-service.ai-showroom.svc:8321")
    headers = {"Content-Type": "application/json"}
    if os.environ.get("OGX_CLIENT_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["OGX_CLIENT_API_KEY"]
    def request(path, body):
        req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)
    settings = pattern["settings"]
    selected_store = vector_store_id or settings["vector_store_binding"]["vector_store_id"]
    if use_responses:
        body = pattern["inference"]["responses_template"]
        body["max_output_tokens"] = 256
        for tool in body.get("tools", []):
            if tool.get("type") == "file_search":
                tool["vector_store_ids"] = [selected_store]
        for message in body["input"]:
            if message.get("role") == "user":
                message["content"] = [{"type": "input_text", "text": question}]
        result = {"api_path": "responses", "response": request("/v1/responses", body)}
    else:
        retrieval = settings["retrieval"]
        params = {"max_chunks": retrieval["number_of_chunks"], "mode": retrieval["search_mode"],
                  "reranker_type": retrieval.get("ranker_strategy", "rrf")}
        if retrieval.get("ranker_strategy") == "weighted":
            params["reranker_params"] = {"alpha": retrieval.get("ranker_alpha", 0.5)}
        elif retrieval.get("ranker_strategy") == "rrf":
            params["reranker_params"] = {"impact_factor": retrieval.get("ranker_k", 60)}
        found = request("/v1/vector-io/query", {"vector_store_id": selected_store,
                        "query": question, "params": params})
        if not found.get("chunks"):
            raise ValueError("The selected pattern returned no indexed chunks")
        generation = settings["generation"]
        context = "\n\n".join("Source " + json.dumps(chunk.get("metadata", {})) + "\n" +
                              (chunk["content"] if isinstance(chunk["content"], str) else json.dumps(chunk["content"]))
                              for chunk in found["chunks"])
        body = {"model": generation["model_id"], "temperature": generation.get("temperature", 0.2),
                "max_tokens": 256, "stream": False, "messages": [
                    {"role": "system", "content": generation["system_message_text"] +
                     " Answer in U.S. English from the provided sources. Cite the document ID. Admit missing facts."},
                    {"role": "user", "content": context + "\n\nQuestion: " + question}]}
        result = {"api_path": "vector-io/query + chat/completions", "retrieval": found,
                  "response": request("/v1/chat/completions", body)}
    result.update({"pipeline_run_id": run_id, "optimization_score": score(pattern),
                   "vector_store_id": selected_store,
                   "original_optimization_vector_store_id": settings["vector_store_binding"]["vector_store_id"]})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result



def trainer_export(path):
    """Track an actual completed TrainJob result without promoting its model."""
    result = json.loads(Path(path).read_text())
    if result.get("event") != "training_completed" or result.get("world_size") != 2:
        raise ValueError("Expected a real completed two-rank training result")
    mlflow = configure_mlflow()
    mlflow.set_experiment("aurora-native-distributed-training")
    with mlflow.start_run(run_name="Aurora demand — two-node CPU comparison") as run:
        mlflow.log_params({k: result[k] for k in ["framework", "world_size", "epochs", "train_rows", "holdout_rows", "train_end", "holdout_end"]})
        mlflow.log_metrics({k: result[k] for k in ["mae", "seasonal_naive_mae"]})
        mlflow.set_tags({"showroom.company": "Aurora Supply", "showroom.promotion": "comparison-only",
                         "showroom.trainjob": "aurora-demand-ddp", "beats_baseline": str(result["beats_baseline"]).lower()})
        mlflow.log_dict(result, "training/result.json")
        mlflow.log_artifact(str(ROOT / "notebooks/train_distributed.py"), "training")
        print(json.dumps({"mlflow_run_id": run.info.run_id, "mae": result["mae"], "promoted": False}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "train", "ray", "upload", "eval-submit", "eval-status", "native-submit", "native-status", "ray-submit", "eval-export", "native-export", "native-infer", "trainer-export"])
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--output", default=None)
    parser.add_argument("--job-id")
    parser.add_argument("--result", help="Path to the actual TrainJob result JSON")
    parser.add_argument("--pipeline", choices=["automl", "autorag"])
    parser.add_argument("--run-id")
    parser.add_argument("--vector-store-id", help="Use the store returned by the selected pattern's native indexing run")
    parser.add_argument("--use-responses", action="store_true", help="Exercise the optional generated Responses API template")
    parser.add_argument("--question", default="What is the return deadline?")
    args = parser.parse_args()
    dest = Path(args.data_dir)
    if args.command == "generate":
        generate(dest)
    elif args.command == "train":
        rows = read_rows(dest / "demand.csv")
        models = [train_sku(rows, p["sku"]) for p in PRODUCTS]
        write_json(args.output or dest / "forecasts.json", bundle(models, rows))
        print(json.dumps({"models": len(models), "quality_gates_passed": sum(m["passed_quality_gate"] for m in models)}))
    elif args.command == "ray":
        rows = generate(dest)
        ray_train(rows)
    elif args.command == "eval-submit":
        eval_submit()
    elif args.command == "eval-export":
        if not args.job_id:
            parser.error("--job-id is required")
        eval_export(args.job_id)
    elif args.command == "eval-status":
        if not args.job_id:
            parser.error("--job-id is required")
        result = eval_request("/api/v1/evaluations/jobs/" + args.job_id)
        print(json.dumps({"job_id": args.job_id, "status": result.get("status"), "results": result.get("results")}, indent=2))
    elif args.command == "trainer-export":
        if not args.result:
            parser.error("--result is required")
        trainer_export(args.result)
    elif args.command == "ray-submit":
        ray_submit()
    elif args.command == "native-export":
        if not args.run_id or not args.pipeline:
            parser.error("--run-id and --pipeline are required")
        native_export(args.pipeline, args.run_id)
    elif args.command == "native-infer":
        if not args.run_id:
            parser.error("--run-id is required")
        native_infer(args.run_id, args.question, args.use_responses, args.vector_store_id)
    elif args.command == "native-submit":
        if not args.pipeline:
            parser.error("--pipeline is required")
        native_submit(args.pipeline)
    elif args.command == "native-status":
        if not args.run_id:
            parser.error("--run-id is required")
        r = native_request("/apis/v2beta1/runs/" + args.run_id)
        print(json.dumps({"run_id": r["run_id"], "state": r.get("state"), "error": r.get("error")}, indent=2))
    elif args.command == "upload":
        import boto3
        s3 = boto3.client("s3", endpoint_url=os.environ["AWS_S3_ENDPOINT"], region_name="us-east-1")
        for file in dest.rglob("*"):
            if file.is_file():
                s3.upload_file(str(file), "aurora-data", str(file.relative_to(dest)))
        prefix = corpus_prefix(dest)
        for file in sorted((dest / "documents").glob("*.md")) + [dest / "eval/autorag.json"]:
            s3.upload_file(str(file), "aurora-data", prefix + "/" + str(file.relative_to(dest)))
        print("Synthetic dataset uploaded; immutable RAG inputs: " + prefix)

if __name__ == "__main__":
    main()
