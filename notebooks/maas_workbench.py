"""A bounded MaaS API test drive with an explicit, endpoint-bound user key.

No Kubernetes token, environment credential, Secret, or output file is accessed.
Only the caller's HTTPS endpoint receives the key. Never serialize the client.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import re
import time
from urllib.parse import urlsplit, urlunsplit

import httpx

PROMPT = (
    "Aurora Supply is a synthetic showroom. A historical proposal requests 346 "
    "units at 42 demo currency units each. Totals above 5000 require an Operations "
    "manager. Explain the required approval in two sentences. No order is executed."
)
_SYSTEM = "Use only the supplied synthetic facts. Give advice, not a claim of an executed purchase."
_RESPONSE_LIMIT = 1024 * 1024


def endpoint_config(base_url: str, model_id: str) -> dict:
    """Validate editable settings before asking for a credential."""
    if not isinstance(base_url, str) or any(c.isspace() for c in base_url):
        raise ValueError("BASE_URL must be one HTTPS URL without whitespace.")
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError:
        raise ValueError("BASE_URL is not a valid HTTPS endpoint.") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or "%" in parsed.netloc or (port is not None and not 1 <= port <= 65535)
            or any(c in base_url for c in "\\\r\n\t")
            or any(part in (".", "..") for part in parsed.path.split("/"))
            or "%" in parsed.path):
        raise ValueError("Use HTTPS without URL credentials, query, fragment, or encoded path segments.")
    if parsed.hostname.endswith(".invalid") or parsed.hostname == "example.com":
        raise ValueError("Replace the example BASE_URL with your approved MaaS endpoint.")
    if (not isinstance(model_id, str) or not 1 <= len(model_id) <= 300
            or not model_id.isascii() or any(c.isspace() or ord(c) < 32 for c in model_id)):
        raise ValueError("MODEL_ID must be the exact nonempty model ID from the approved endpoint.")
    path = parsed.path.rstrip("/")
    if not path.endswith("/v1"):
        path += "/v1"
    return {"base_url": urlunsplit(("https", parsed.netloc, path, "", "")), "model_id": model_id}


def _integer(name, value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}.")


def _number(name, value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a finite number from {low} to {high}.")


@dataclass(frozen=True, repr=False)
class MaasClient:
    """Keep a user key in memory, bound to immutable endpoint/model settings."""

    base_url: str
    model_id: str
    _api_key: str = field(repr=False)
    timeout_s: float = 20

    def __post_init__(self):
        config = endpoint_config(self.base_url, self.model_id)
        _number("timeout_s", self.timeout_s, 1, 30)
        if (not isinstance(self._api_key, str) or not 1 <= len(self._api_key) <= 16384
                or not self._api_key.isascii() or any(c.isspace() or ord(c) < 32 for c in self._api_key)):
            raise ValueError("Enter one nonempty API key without whitespace; do not put it in a URL.")
        object.__setattr__(self, "base_url", config["base_url"])

    def __repr__(self):
        return "MaasClient(endpoint_bound=True, credential='[REDACTED]')"

    def _clean(self, value: str, limit: int = 8000) -> str:
        value = value.replace(self._api_key, "[REDACTED]")
        value = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED_JWT]", value)
        value = re.sub(r"(?i)Bearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
        return value[:limit]

    async def _request(self, operation: str, body=None):
        # Callers cannot supply a URL, method, arbitrary headers, or another key.
        paths = {"models": ("GET", "/models"), "chat": ("POST", "/chat/completions")}
        if operation not in paths:
            raise ValueError("Unsupported MaaS test-drive operation.")
        method, path = paths[operation]
        result = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
                  "http_status": None, "elapsed_s": None, "outcome": "request_failed",
                  "error_code": None}
        start = time.monotonic()

        async def send():
            async with httpx.AsyncClient(verify=True, follow_redirects=False, trust_env=False,
                    timeout=httpx.Timeout(self.timeout_s, connect=min(5, self.timeout_s))) as client:
                async with client.stream(method, self.base_url + path, json=body,
                        headers={"Authorization": "Bearer " + self._api_key,
                                 "Content-Type": "application/json"}) as response:
                    result["http_status"] = response.status_code
                    if response.status_code != 200:
                        result["error_code"] = f"HTTP_{response.status_code}"
                        result["outcome"] = (
                            "discovery_unsupported" if operation == "models" and response.status_code in (404, 405)
                            else "rate_limited" if response.status_code == 429 else "http_error")
                        retry = response.headers.get("Retry-After", "")
                        if retry.isdigit() and len(retry) <= 8:
                            result["retry_after_seconds"] = int(retry)
                        return None  # Never expose upstream error bodies or follow a redirect.
                    parts, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > _RESPONSE_LIMIT:
                            raise ValueError("Response too large")
                        parts.append(chunk)
                    data = json.loads(b"".join(parts))
                    if not isinstance(data, dict):
                        raise ValueError("Expected an object")
                    result["outcome"] = "completed"
                    return data

        try:
            data = await asyncio.wait_for(send(), timeout=self.timeout_s)
        except (TimeoutError, httpx.TimeoutException):
            result.update(outcome="timeout", error_code="REQUEST_TIMEOUT")
            data = None
        except asyncio.CancelledError:
            raise  # Jupyter interrupt cancels and closes the request; no background worker.
        except Exception:
            result.update(outcome="request_failed", error_code="TRANSPORT_OR_RESPONSE_ERROR")
            data = None  # Do not return exception text, headers, or traceback locals.
        finally:
            result["elapsed_s"] = round(time.monotonic() - start, 6)
        return result, data

    async def discover_models(self) -> dict:
        """Read only GET /v1/models; 404/405 is reported without endpoint guessing."""
        result, data = await self._request("models")
        result["models"] = []
        if data is not None:
            items = data.get("data")
            if not isinstance(items, list):
                result.update(outcome="invalid_response", error_code="INVALID_MODEL_LIST")
            else:
                result["models"] = [self._clean(item["id"], 300) for item in items[:1000]
                                    if isinstance(item, dict) and isinstance(item.get("id"), str)]
                result["configured_model_listed"] = self.model_id in result["models"]
        return result

    async def chat(self, prompt: str = PROMPT, max_tokens: int = 64) -> dict:
        """One non-streaming request; only a redacted answer and measured fields return."""
        _integer("max_tokens", max_tokens, 1, 256)
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
            raise ValueError("Use a synthetic prompt of 1 to 2000 characters.")
        result, data = await self._request("chat", {"model": self.model_id,
            "messages": [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": 0, "stream": False})
        result.update(answer=None, provider_usage=None)
        if data is not None:
            choices = data.get("choices")
            message = choices[0].get("message", {}) if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
            answer = message.get("content") if isinstance(message, dict) else None
            if not isinstance(answer, str) or not answer.strip():
                result.update(outcome="invalid_response", error_code="NO_ANSWER")
            else:
                result["answer"] = self._clean(answer)
            usage = data.get("usage")
            if isinstance(usage, dict):
                keys = ("prompt_tokens", "completion_tokens", "total_tokens")
                values = [usage.get(k) for k in keys]
                if all(type(v) is int and v >= 0 for v in values) and values[0] + values[1] == values[2]:
                    result["provider_usage"] = dict(zip(keys, values))
        return result

    async def quota_probe(self, max_requests=3, interval_s=2, duration_s=45) -> dict:
        """Explicit opt-in only. Stop on 429, any error, interrupt, or a hard deadline."""
        _integer("max_requests", max_requests, 1, 6)
        _number("interval_s", interval_s, 1, 10)
        _number("duration_s", duration_s, 1, 60)
        rows = []
        start = time.monotonic()

        async def run():
            for number in range(1, max_requests + 1):
                request_started = time.monotonic()
                row = {"request": number, "started_at_utc": datetime.now(timezone.utc).isoformat(),
                       "http_status": None, "elapsed_s": None, "outcome": "incomplete",
                       "error_code": "CLIENT_CANCELLED", "provider_usage": None}
                rows.append(row)
                try:
                    reply = await self.chat(max_tokens=32)
                except asyncio.CancelledError:
                    row["elapsed_s"] = round(time.monotonic() - request_started, 6)
                    raise
                reply.pop("answer", None)
                row.update(reply)
                if reply["outcome"] != "completed":
                    return "stopped_after_429" if reply["http_status"] == 429 else "stopped_after_error"
                if number < max_requests:
                    await asyncio.sleep(interval_s)
            return "request_limit"

        try:
            reason = await asyncio.wait_for(run(), timeout=duration_s)
        except TimeoutError:
            reason = "duration_limit"
            if rows and rows[-1]["outcome"] == "incomplete":
                rows[-1]["error_code"] = "QUOTA_DEADLINE"
        except asyncio.CancelledError:
            reason = "interrupted"
        return {"stop_reason": reason, "elapsed_s": round(time.monotonic() - start, 6),
                "attempted_requests": len(rows),
                "incomplete_requests": sum(row["outcome"] == "incomplete" for row in rows),
                "requests": rows}
