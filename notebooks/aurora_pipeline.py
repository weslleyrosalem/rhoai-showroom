"""Compile with: python notebooks/aurora_pipeline.py
Requires kfp==2.15.2. Pipeline code is fetched from this public repository.
The Ray lab separately runs the same training implementation on two workers.
"""
from kfp import dsl, compiler
from kfp.dsl import Dataset, Model, Metrics, Input, Output

IMAGE = "registry.redhat.io/rhoai/odh-pipeline-runtime-minimal-cpu-py312-rhel9@sha256:b65cee70b3abfa45f0e8ed4763f5c55fb48b75410184065b95b429b2b0a4717f"

@dsl.component(base_image=IMAGE)
def prepare_data(source_ref: str, demand: Output[Dataset]):
    import importlib.util
    import pathlib
    import tempfile
    import urllib.request
    import shutil
    path = pathlib.Path(tempfile.mkdtemp())
    code = path / "science.py"
    urllib.request.urlretrieve("https://raw.githubusercontent.com/weslleyrosalem/rhoai-showroom/" + source_ref + "/scripts/science.py", code)
    spec = importlib.util.spec_from_file_location("science", code)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.generate(path / "data")
    shutil.copyfile(path / "data/demand.csv", demand.path)
    demand.metadata["license"] = "CC0-1.0"
    demand.metadata["synthetic"] = True
    demand.metadata["seed"] = 351

@dsl.component(base_image=IMAGE)
def train_model(source_ref: str, demand: Input[Dataset], model: Output[Model], metrics: Output[Metrics]):
    import importlib.util
    import pathlib
    import tempfile
    import urllib.request
    import json
    code = pathlib.Path(tempfile.mkdtemp()) / "science.py"
    urllib.request.urlretrieve("https://raw.githubusercontent.com/weslleyrosalem/rhoai-showroom/" + source_ref + "/scripts/science.py", code)
    spec = importlib.util.spec_from_file_location("science", code)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    rows = module.read_rows(demand.path)
    models = [module.train_sku(rows, p["sku"]) for p in module.PRODUCTS]
    result = module.bundle(models, rows)
    pathlib.Path(model.path).write_text(json.dumps(result))
    metrics.log_metric("mean_mae", sum(m["mae"] for m in models) / len(models))
    metrics.log_metric("mean_baseline_mae", sum(m["baseline_mae"] for m in models) / len(models))
    model.metadata["version"] = result["model_version"]

@dsl.component(base_image=IMAGE)
def quality_gate(model: Input[Model], approved: Output[Model]):
    import json
    import pathlib
    import math
    import shutil
    result = json.loads(pathlib.Path(model.path).read_text())
    for prediction in result["forecasts"]:
        if not prediction["passed_quality_gate"] or not math.isfinite(prediction["mae"]):
            raise ValueError("Quality gate rejected model")
    shutil.copyfile(model.path, approved.path)
    approved.metadata["version"] = result["model_version"]
    approved.metadata["approved"] = True

@dsl.pipeline(name="aurora-demand-lifecycle", description="Synthetic demand → measured training → quality gate")
def aurora_demand(source_ref: str = "main"):
    data = prepare_data(source_ref=source_ref)
    train = train_model(source_ref=source_ref, demand=data.outputs["demand"])
    quality_gate(model=train.outputs["model"])

if __name__ == "__main__":
    compiler.Compiler().compile(aurora_demand, package_path="notebooks/aurora_pipeline.yaml")
