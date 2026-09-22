"""Private Envoy authorization adapter; never logs request headers or tokens.

Administrative tokens require a live TokenReview and one exact subject. Native
sandbox tokens are only passed to the pinned gateway's sandbox RPC allowlist;
the gateway remains responsible for their signature, audience, expiry, and
same-sandbox validation. Parsing a JWT here is never proof of authentication.
"""
import base64
import json
import os
import ssl
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ADMIN = "system:serviceaccount:ai-showroom-sandbox:showroom-openshell-client"
WORKLOAD = "system:serviceaccount:ai-showroom-sandbox:showroom-openshell-sandbox"
PREFIX = "/openshell.v1.OpenShell/"
BOOTSTRAP = PREFIX + "IssueSandboxToken"
CALLBACKS = {PREFIX + method for method in (
    "GetSandboxConfig", "UpdateConfig", "ReportPolicyStatus",
    "GetSandboxProviderEnvironment", "ExchangeProviderSubjectToken",
    "PushSandboxLogs", "ConnectSupervisor", "ReportMainProcessExit",
    "RelayStream", "SubmitPolicyAnalysis", "GetDraftPolicy",
    "IssueSandboxToken", "RefreshSandboxToken",
)} | {"/openshell.inference.v1.Inference/GetInferenceBundle"}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JWT claim")
        value[key] = item
    return value


def claims(token):
    if len(token) > 16384 or token.count(".") != 2:
        raise ValueError("Invalid token format")
    payload = token.split(".")[1]
    result = json.loads(base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True), object_pairs_hook=unique_object)
    if not isinstance(result, dict):
        raise ValueError("Invalid JWT claims")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Redirects are prohibited")


def review(token, audience, subject):
    root = Path("/var/run/secrets/kubernetes.io/serviceaccount")
    context = ssl.create_default_context(cafile=str(root / "ca.crt"))
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context))
    body = {"apiVersion": "authentication.k8s.io/v1", "kind": "TokenReview", "spec": {"token": token, "audiences": [audience]}}
    request = urllib.request.Request("https://kubernetes.default.svc/apis/authentication.k8s.io/v1/tokenreviews", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + (root / "token").read_text().strip(), "Content-Type": "application/json"})
    with opener.open(request, timeout=4) as response:
        status = json.load(response).get("status", {})
    return status.get("authenticated") is True and status.get("user", {}).get("username") == subject and audience in status.get("audiences", [])


def authorize(path, authorization, reviewer=review):
    if not authorization.startswith("Bearer "):
        return False
    token = authorization[7:]
    item = claims(token)
    # This branch only delegates to native workload authentication. A forged
    # token still fails the gateway's cryptographic and same-sandbox checks.
    issuer = item.get("iss", "")
    if isinstance(issuer, str) and issuer.startswith("openshell-gateway:"):
        return path in CALLBACKS and str(item.get("sub", "")).startswith("spiffe://openshell/sandbox/")
    if path == BOOTSTRAP:
        return reviewer(token, "openshell-gateway", WORKLOAD)
    return reviewer(token, "showroom-openshell", ADMIN)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            allowed = authorize(self.path, self.headers.get("Authorization", ""))
        except Exception:
            allowed = False
        self.send_response(200 if allowed else 403)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = do_POST


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 9000), Handler).serve_forever()
