"""Bounded GuideLLM 0.7.4 runs from the Aurora Workbench; no background traffic."""
from __future__ import annotations

import asyncio
import base64
import csv
import datetime as dt
import html
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from urllib.parse import urlsplit

VERSION = "0.7.4"
MODEL = "aurora-qwen-4b"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
TOKENIZER_ID = "Qwen/Qwen3-4B-Instruct-2507"
TOKENIZER_HASHES = {
    "config.json": "5beea1a4a34c62782bfb2f911c606741a3bab8f92d80a118fa053c28af12e8ba",
    "tokenizer.json": "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    "tokenizer_config.json": "a62ff0a2472a0fa1b8eaabcb57c59b58afa42a22831dc141400b6e0cf2b65ce3",
    "merges.txt": "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3",
    "vocab.json": "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
}
GATEWAY = "showroom-inference-maas-gateway-class.ai-showroom.svc.cluster.local"
API_PATH = "/ai-showroom/aurora-qwen-4b/v1"
TOKENIZER = Path("/opt/app-root/src/.cache/aurora-qwen-tokenizer")
RESULTS = Path("/opt/app-root/src/aurora-results/guidellm")
PREFIX = (
    "You are Aurora Supply's operations assistant. Use only the facts in this "
    "fictional showroom fixture. Product AS-001, H20 Hydraulic Filter, has 45 "
    "units on hand, a reorder point of 80, and a unit price of 42 demo currency "
    "units. A historical demo proposal requests 346 units. Totals above 5000 "
    "require Operations manager approval. Never claim that an order has been placed. Give a short "
    "answer and explain missing information. "
)
QUESTIONS = (
    "How far below the reorder point is AS-001?",
    "Explain the approval required for the historical AS-001 proposal without placing an order.",
    "What information should an operator verify before approving replenishment?",
)


def validate_limits(seconds=30, rate=0.1, concurrency=1, output_tokens=64):
    """Limit measurement to 120s and the complete process to at most 180s."""
    if type(seconds) is not int or not 20 <= seconds <= 120:
        raise ValueError("Measurement seconds must be an integer from 20 to 120.")
    if type(rate) not in (int, float) or not math.isfinite(rate) or not 0 < rate <= 0.1:
        raise ValueError("Rate must be greater than zero and at most 0.1 requests/s.")
    if type(concurrency) is not int or concurrency not in (1, 2):
        raise ValueError("Concurrency must be 1 or 2.")
    if type(output_tokens) is not int or not 16 <= output_tokens <= 128:
        raise ValueError("Output token limit must be an integer from 16 to 128.")
    return dict(seconds=seconds, rate=float(rate), concurrency=concurrency,
                output_tokens=output_tokens, max_requests=min(20, math.ceil(seconds * rate)),
                hard_wall_seconds=min(180, seconds + 60))


def validate_tokenizer(tokenizer, model_id=MODEL, tokenizer_id=TOKENIZER_ID,
                       tokenizer_revision=MODEL_REVISION, tokenizer_for_model=MODEL):
    """Verify explicit model binding and tokenizer files; never infer server weights."""
    if tokenizer_for_model != model_id:
        raise ValueError("TOKENIZER_FOR_MODEL must explicitly match MODEL_ID. Choose the matching tokenizer before running.")
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", tokenizer_id or "")
            or any(part in {".", ".."} or len(part) > 96 for part in tokenizer_id.split("/"))):
        raise ValueError("TOKENIZER_ID must be a public Hugging Face organization/model ID.")
    if not re.fullmatch(r"[a-f0-9]{40}", tokenizer_revision or ""):
        raise ValueError("TOKENIZER_REVISION must be an immutable 40-character commit SHA.")
    tokenizer = Path(tokenizer).resolve()
    provenance = json.loads((tokenizer / "showroom-provenance.json").read_text())
    if provenance.get("revision") != tokenizer_revision or provenance.get("model") != tokenizer_id:
        raise ValueError("Tokenizer provenance does not match the selected immutable tokenizer revision.")
    if tokenizer == TOKENIZER.resolve():
        if (model_id, tokenizer_id, tokenizer_revision) != (MODEL, TOKENIZER_ID, MODEL_REVISION):
            raise ValueError("The prepared Qwen preset is bound only to aurora-qwen-4b. Explicitly prepare a matching tokenizer for another model.")
        hashes = TOKENIZER_HASHES
    else:
        if provenance.get("served_model") != model_id:
            raise ValueError("Custom tokenizer provenance does not match the selected served-model binding.")
        files = provenance.get("files", {})
        if (not files or not set(files).issubset(TOKENIZER_FILES)
                or not any(name in files for name in ("tokenizer.json", "tokenizer.model", "spiece.model", "vocab.json"))):
            raise ValueError("Custom tokenizer manifest is incomplete or contains unsupported files.")
        hashes = {name: value.get("sha256") for name, value in files.items()}
    for name, digest in hashes.items():
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Tokenizer manifest contains an invalid SHA256.")
        if hashlib.sha256((tokenizer / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Pinned tokenizer integrity check failed: {name}")
    return tokenizer


TOKENIZER_FILES = frozenset({
    "config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
    "vocab.json", "merges.txt", "tokenizer.model", "spiece.model", "added_tokens.json", "chat_template.jinja",
})


def prepare_tokenizer(tokenizer_id=TOKENIZER_ID, revision=MODEL_REVISION,
                      for_model=MODEL):
    """Explicitly fetch only public tokenizer files, never model weights or credentials.

    The model-to-tokenizer association is supplied by the operator. The OpenAI
    models API does not attest that a remote server uses this tokenizer/revision.
    """
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", tokenizer_id or "")
            or any(part in {".", ".."} or len(part) > 96 for part in tokenizer_id.split("/"))):
        raise ValueError("Use a public Hugging Face organization/model tokenizer ID.")
    if not re.fullmatch(r"[a-f0-9]{40}", revision or ""):
        raise ValueError("Use an immutable 40-character tokenizer commit SHA.")
    if not isinstance(for_model, str) or not for_model or len(for_model) > 256:
        raise ValueError("An explicit served-model binding is required.")
    if (tokenizer_id, revision, for_model) == (TOKENIZER_ID, MODEL_REVISION, MODEL):
        return validate_tokenizer(TOKENIZER)
    parent = Path("/opt/app-root/src/.cache/aurora-tokenizers")
    key = hashlib.sha256((tokenizer_id + revision + for_model).encode()).hexdigest()[:24]
    destination = parent / key
    if destination.is_dir():
        return validate_tokenizer(destination, for_model, tokenizer_id, revision, for_model)
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 120

    def download(url, maximum):
        data = bytearray()
        with opener.open(url, timeout=20) as response:
            if response.status != 200 or urlsplit(response.geturl()).scheme != "https":
                raise ValueError("The public tokenizer download requires verified HTTPS and HTTP 200.")
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Tokenizer preparation exceeded its bounded download window.")
                chunk = response.read(64 * 1024)
                if not chunk:
                    return bytes(data)
                data.extend(chunk)
                if len(data) > maximum:
                    raise ValueError("Tokenizer download exceeds the allowed file size.")

    metadata = json.loads(download(f"https://huggingface.co/api/models/{tokenizer_id}/revision/{revision}", 1024 * 1024))
    if metadata.get("sha") != revision:
        raise ValueError("Hugging Face metadata did not resolve the exact requested commit.")
    names = sorted({item.get("rfilename") for item in metadata.get("siblings", [])} & TOKENIZER_FILES)
    if not any(name in names for name in ("tokenizer.json", "tokenizer.model", "spiece.model", "vocab.json")):
        raise ValueError("No supported tokenizer files are present in the selected revision.")
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=parent) as temporary:
        staged = Path(temporary)
        files = {}
        total = 0
        for name in names:
            raw = download(f"https://huggingface.co/{tokenizer_id}/resolve/{revision}/{name}", 20 * 1024 * 1024)
            total += len(raw)
            if total > 50 * 1024 * 1024:
                raise ValueError("Tokenizer files exceed the total download size limit.")
            with os.fdopen(os.open(staged / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
                stream.write(raw)
            files[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        _write(staged / "showroom-provenance.json", {
            "model": tokenizer_id, "revision": revision, "served_model": for_model,
            "binding": "Explicit operator-supplied mapping; remote server revision not attested",
            "files": files,
        })
        validate_tokenizer(staged, for_model, tokenizer_id, revision, for_model)
        os.rename(staged, destination)
    print("Tokenizer files prepared and verified; no model weights or inference were requested.")
    return destination


def sanitize(value, token="", target=""):
    """Redact in memory before any report is written to the Workbench PVC."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in {"api_key", "authorization", "request_args", "headers"}:
                result[key] = None
            elif key in {"target", "base_url"}:
                result[key] = "https://redacted-endpoint.invalid"
            else:
                result[key] = sanitize(item, token, target)
        return result
    if isinstance(value, list):
        return [sanitize(item, token, target) for item in value]
    if isinstance(value, str):
        if token:
            value = value.replace(token, "[REDACTED]")
        if target:
            value = value.replace(target, "https://redacted-endpoint.invalid")
        value = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED_JWT]", value)
        value = re.sub(r"(?i)Bearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
    return value


def _write(path, value):
    """Create private files atomically without briefly exposing their content."""
    encoded = value if isinstance(value, str) else json.dumps(value, indent=2, allow_nan=False)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def summarize(report):
    """Keep real GuideLLM totals and distinguish observed SSE from buffered output."""
    summaries = []
    requests = []
    for index, benchmark in enumerate(report.get("benchmarks", [])):
        duration = benchmark.get("duration")
        metrics = benchmark.get("metrics", {})
        totals = metrics.get("request_totals", {})
        valid_ttft = []
        for status in ("successful", "errored", "incomplete"):
            for item in benchmark.get("requests", {}).get(status, []) or []:
                timing = item.get("info", {}).get("timings", {})
                first = timing.get("first_output_token_iteration")
                last = timing.get("last_token_iteration")
                start = timing.get("request_start")
                streamed = (status == "successful" and (timing.get("token_iterations") or 0) > 1
                            and all(isinstance(v, (int, float)) for v in (start, first, last))
                            and last - first > 0.005 and first >= start)
                ttft = 1000 * (first - start) if streamed else None
                if ttft is not None:
                    valid_ttft.append(ttft)
                requests.append({"benchmark": index, "status": status,
                                 "request_id": item.get("request_id"),
                                 "latency_seconds": item.get("request_latency"),
                                 "output_tokens": item.get("output_tokens"),
                                 "stream_iterations": timing.get("token_iterations", 0),
                                 "streaming_ttft_ms": ttft,
                                 "ttft_status": "CLIENT_STREAM_OBSERVED" if streamed else "UNAVAILABLE_OR_BUFFERED"})
        output_total = metrics.get("output_token_count", {}).get("successful", {}).get("total_sum", 0)
        successful = totals.get("successful", 0)
        measured = isinstance(duration, (int, float)) and duration > 0
        latency = metrics.get("request_latency", {}).get("successful", {})
        summaries.append({"benchmark": index, "successful": successful,
                          "errored": totals.get("errored", 0), "incomplete": totals.get("incomplete", 0),
                          "duration_seconds": duration,
                          "achieved_requests_per_second": successful / duration if measured else None,
                          "output_tokens_per_second": output_total / duration if measured else None,
                          "latency_mean_seconds": latency.get("mean"),
                          "latency_p95_seconds": latency.get("percentiles", {}).get("p95"),
                          "streaming_ttft_mean_ms": statistics.mean(valid_ttft) if valid_ttft else None,
                          "streaming_ttft_samples": len(valid_ttft),
                          "ttft_status": "CLIENT_STREAM_OBSERVED" if valid_ttft else "UNAVAILABLE_OR_BUFFERED"})
    return summaries, requests


def _save_views(folder, report, settings):
    summaries, requests = summarize(report)
    _write(folder / "summary.json", {"settings": settings, "benchmarks": summaries, "requests": requests})
    for filename, rows in (("summary.csv", summaries), ("requests.csv", requests)):
        buffer = io.StringIO()
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        _write(folder / filename, buffer.getvalue())
    image = ""
    if requests:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        completed = [row for row in requests if row["status"] == "successful"]
        fig, panels = plt.subplots(2, 2, figsize=(10, 6))
        axes = panels.flatten()
        axes[0].plot(range(1, len(completed) + 1), [row["latency_seconds"] for row in completed], "o-")
        axes[0].set(xlabel="Successful request", ylabel="End-to-end latency (s)", title="Observed request latency")
        observed = [(i + 1, row["streaming_ttft_ms"]) for i, row in enumerate(completed) if row["streaming_ttft_ms"] is not None]
        if observed:
            axes[1].plot(*zip(*observed), "o-")
        else:
            axes[1].text(.5, .5, "Streaming TTFT unavailable\nor output was buffered", ha="center", va="center", transform=axes[1].transAxes)
        axes[1].set(xlabel="Successful request", ylabel="Client streaming TTFT (ms)", title="First observed content token")
        rates = [row for row in summaries if row["achieved_requests_per_second"] is not None]
        axes[2].bar([str(row["benchmark"]) for row in rates], [row["achieved_requests_per_second"] for row in rates])
        axes[2].set(xlabel="Benchmark", ylabel="Successful requests/s", title="Achieved request throughput")
        token_rates = [row for row in summaries if row["output_tokens_per_second"] is not None]
        axes[3].bar([str(row["benchmark"]) for row in token_rates], [row["output_tokens_per_second"] for row in token_rates])
        axes[3].set(xlabel="Benchmark", ylabel="Successful output tokens/s", title="Achieved output throughput")
        fig.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=130)
        plt.close(fig)
        image = '<img alt="Actual GuideLLM latency and streaming TTFT measurements" src="data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode() + '">'
    table = "<table><tr>" + "".join("<th>" + html.escape(key) + "</th>" for key in (summaries[0] if summaries else {})) + "</tr>"
    for row in summaries:
        table += "<tr>" + "".join("<td>" + html.escape(str(value)) + "</td>" for value in row.values()) + "</tr>"
    table += "</table>"
    _write(folder / "benchmarks.html", '<!doctype html><html lang="en"><meta charset="utf-8"><title>Aurora GuideLLM results</title><style>body{font:16px system-ui;margin:2rem}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:.4rem}img{max-width:100%}</style><h1>Aurora GuideLLM results</h1><p>Actual GuideLLM 0.7.4 measurements. This short run is a functional observation, not a capacity, model-quality, or routing comparison. TTFT describes client-observed SSE delivery, including gateway effects. Unavailable values are not zero.</p>' + table + image + '</html>')


async def _benchmark(payload, folder, tokenizer):
    from loguru import logger
    logger.remove()
    from showroom_workbench import connection, validate_config, bind_api_key, preflight
    from guidellm.benchmark.entrypoints import benchmark_generative_text
    from guidellm.benchmark.schemas import BenchmarkScenario
    settings = payload["settings"]
    config = validate_config(payload["config"])
    bound = bind_api_key(config, payload["api_key"]) if config["auth_mode"] == "api_key" else None
    credentials = connection(config, api_key=bound)
    target = credentials["base_url"].rstrip("/").removesuffix("/v1")
    token = credentials["api_key"]
    spec = {
        "backend": {"kind": "openai_http", "target": target, "model": config["model_id"],
                    "api_key": token, "request_format": "/v1/chat/completions",
                    "api_routes": {"/health": "v1/models"}, "stream": True,
                    "timeout": 20, "timeout_connect": 5, "http2": False,
                    "follow_redirects": False, "verify": True,
                    "max_tokens": settings["output_tokens"],
                    "extras": {"body": {"temperature": 0}, "headers": {"X-Showroom-Client": "guidellm-workbench"}}},
        "profile": {"kind": "constant", "rate": settings["rate"], "max_concurrency": settings["concurrency"]},
        "constraints": [{"kind": "max_duration", "seconds": settings["seconds"]},
                        {"kind": "max_requests", "count": settings["max_requests"]},
                        {"kind": "max_errors", "count": 2}],
        "data": [{"kind": "in_memory_dict", "data": {
            "prompt": [PREFIX + QUESTIONS[i % len(QUESTIONS)] for i in range(settings["max_requests"])],
            "output_tokens_count": [settings["output_tokens"]] * settings["max_requests"]}}],
        "data_loader": {"kind": "pytorch", "num_workers": 0},
        "tokenizer": {"kind": "huggingface_auto", "model": str(tokenizer),
                      "load_kwargs": {"local_files_only": True, "trust_remote_code": False}},
        "metrics": {"kind": "generative", "sample_size": 20},
        "outputs": [], "seed": {"kind": "static", "value": 42},
    }
    try:
        check = sanitize(await preflight(config, api_key=bound), token, target)
        _write(folder / "preflight.json", check)
        if not check.get("ok"):
            _write(folder / "status.json", {"state": "BLOCKED_PREFLIGHT", "message": check.get("message", "The selected model is unavailable or access was denied.")})
            return 2
        report, _ = await benchmark_generative_text(BenchmarkScenario(spec=spec), console=None, progress=None)
        safe = sanitize(report.model_dump(mode="json"), token, target)
        # Built-in outputs are disabled: sanitize the entire report before the first write.
        _write(folder / "benchmarks.json", safe)
        _save_views(folder, safe, settings)
        totals = [b["metrics"]["request_totals"] for b in safe.get("benchmarks", [])]
        ok = bool(totals) and sum(t.get("successful", 0) for t in totals) > 0
        failures = sum(t.get("errored", 0) + t.get("incomplete", 0) for t in totals)
        state = "FAILED_NO_SUCCESSFUL_REQUESTS" if not ok else ("COMPLETED_WITH_ERRORS" if failures else "COMPLETED")
        _write(folder / "status.json", {"state": state, "failed_or_incomplete": failures,
                                       "finished_at": dt.datetime.now(dt.timezone.utc).isoformat()})
        return 0 if ok and not failures else 2
    except Exception as exc:
        # No traceback locals, full URLs, request headers, or raw backend configuration.
        _write(folder / "status.json", {"state": "FAILED", "error_type": type(exc).__name__,
                                       "message": sanitize(str(exc), token, target)[:2000]})
        return 2


def _kill_group(process):
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run(seconds=30, rate=0.1, concurrency=1, output_tokens=64,
        tokenizer=TOKENIZER, results=RESULTS, config=None, api_key=None,
        tokenizer_id=TOKENIZER_ID, tokenizer_revision=MODEL_REVISION,
        tokenizer_for_model=MODEL):
    """Run once, synchronously; interrupt or kernel death stops the process group."""
    if sys.version_info < (3, 11):
        raise RuntimeError("Use the Aurora Inference Demo kernel with Python 3.11 or later.")
    from showroom_workbench import validate_config, connection
    config = validate_config(config)
    if config["auth_mode"] == "service_account" and api_key is not None:
        raise ValueError("Do not supply an API key when AUTH_MODE is service_account.")
    settings = validate_limits(seconds, rate, concurrency, output_tokens)
    if importlib.metadata.version("guidellm") != VERSION:
        raise RuntimeError("Select the Aurora Inference Demo kernel with guidellm==0.7.4.")
    tokenizer = validate_tokenizer(tokenizer, config["model_id"], tokenizer_id,
                                   tokenizer_revision, tokenizer_for_model)
    # Only an explicitly entered, endpoint-bound API key can cross into stdin.
    # A service-account token is read fresh inside the child, never in this parent.
    raw_key = connection(config, api_key=api_key)["api_key"] if config["auth_mode"] == "api_key" else None
    root = Path(results).resolve()
    pvc_root = Path("/opt/app-root/src").resolve()
    if not root.is_relative_to(pvc_root):
        raise ValueError("Results must stay on the Workbench PVC under /opt/app-root/src.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = root / (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    folder.mkdir(mode=0o700)
    settings.update(model=config["model_id"], auth_mode=config["auth_mode"],
                    tokenizer_id=tokenizer_id, tokenizer_revision=tokenizer_revision,
                    tokenizer_for_model=tokenizer_for_model,
                    endpoint="REDACTED", runtime_model_revision="NOT_ATTESTED_BY_MODELS_API",
                    guidellm_version=VERSION,
                    started_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    scope="Short Workbench client observation; explicit model/tokenizer mapping, no routing or capacity attribution")
    _write(folder / "settings.json", settings)
    _write(folder / "status.json", {"state": "STARTING"})
    # Do not inherit S3 credentials, MaaS keys, proxy credentials, or GuideLLM overrides.
    env = {k: v for k, v in os.environ.items() if k in {
        "HOME", "PATH", "LANG", "LC_ALL", "TZ", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE", "VIRTUAL_ENV",
    }}
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false",
               OMP_NUM_THREADS="1", HF_DATASETS_DISABLE_PROGRESS_BARS="1", MPLCONFIGDIR=str(root / ".matplotlib"))
    child = watchdog = None
    read_fd = write_fd = None
    try:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child", str(folder), str(tokenizer)],
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 text=True, env=env, start_new_session=True)
        read_fd, write_fd = os.pipe()
        watchdog_code = (
            "import os,select,signal,sys\n"
            "fd,pid,seconds=int(sys.argv[1]),int(sys.argv[2]),float(sys.argv[3])\n"
            "select.select([fd],[],[],seconds)\n"
            "try: os.killpg(pid,signal.SIGKILL)\n"
            "except ProcessLookupError: pass\n"
        )
        watchdog = subprocess.Popen([sys.executable, "-c", watchdog_code, str(read_fd), str(child.pid), str(settings["hard_wall_seconds"])],
                                    pass_fds=(read_fd,), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True, env=env)
        os.close(read_fd)
        read_fd = None
        child.stdin.write(json.dumps({"settings": settings, "config": config, "api_key": raw_key}))
        child.stdin.close()
        raw_key = None
        print(f"GuideLLM: {seconds}s measurement, at most {settings['max_requests']} requests, {rate:g} requests/s, concurrency {concurrency}.")
        code = child.wait(timeout=settings["hard_wall_seconds"] + 2)
        if code != 0:
            status = json.loads((folder / "status.json").read_text())
            if status.get("state") == "STARTING":
                _write(folder / "status.json", {"state": "STOPPED_OR_STARTUP_FAILED", "exit_code": code})
    except KeyboardInterrupt:
        _write(folder / "status.json", {"state": "INTERRUPTED"})
        print("Interrupted. Stopping all processes for this run.")
    except subprocess.TimeoutExpired:
        _write(folder / "status.json", {"state": "WALL_DEADLINE_EXCEEDED"})
    finally:
        raw_key = None
        _kill_group(child)
        if write_fd is not None:
            os.close(write_fd)
        if read_fd is not None:
            os.close(read_fd)
        if watchdog is not None:
            watchdog.wait(timeout=5)
    print(f"Finished. Private reports: {folder}")
    return folder


def display_results(folder):
    """Show actual result tables/plots; never inspect connection credentials."""
    from IPython.display import HTML, display
    import pandas as pd
    folder = Path(folder)
    display(pd.DataFrame([json.loads((folder / "status.json").read_text())]))
    if (folder / "summary.json").exists():
        summary = json.loads((folder / "summary.json").read_text())
        display(pd.DataFrame(summary["benchmarks"]))
        display(pd.DataFrame(summary["requests"]))
        display(HTML((folder / "benchmarks.html").read_text()))
    else:
        print("No completed measurement report. Inspect status.json; do not interpret this as zero latency or zero errors.")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--child":
        raise SystemExit("Import run() from the Aurora Inference Demo notebook.")
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    configuration = json.load(sys.stdin)
    limits = configuration["settings"]
    validate_limits(limits["seconds"], limits["rate"], limits["concurrency"], limits["output_tokens"])
    validate_tokenizer(Path(sys.argv[3]), limits["model"], limits["tokenizer_id"],
                       limits["tokenizer_revision"], limits["tokenizer_for_model"])
    raise SystemExit(asyncio.run(_benchmark(configuration, Path(sys.argv[2]), Path(sys.argv[3]))))
