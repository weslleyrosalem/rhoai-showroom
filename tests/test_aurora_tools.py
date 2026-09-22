"""Read-only domain and actual MCP protocol tests; no cluster or external API."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "apps" / "aurora-tools"
sys.path.insert(0, str(APP))
from business import Catalog, load_products


def test_replenishment_is_read_only():
    catalog = Catalog()
    before = catalog.list_products()
    sku = before["products"][0]["sku"]
    proposal = catalog.get_replenishment_recommendation(sku)
    assert proposal["recommended_quantity"] == 13
    assert proposal["order_created"] is False
    assert proposal["requires_human_approval"] is True
    assert catalog.list_products() == before
    proposal["stock"] = 1000
    assert catalog.get_stock(sku)["product"]["stock"] == 7


def test_caller_cannot_mutate_inventory():
    catalog = Catalog()
    listing = catalog.list_products()
    listing["products"][0]["stock"] = 999
    assert catalog.list_products()["products"][0]["stock"] == 7


def test_catalog_filters_and_bounds():
    catalog = Catalog()
    assert catalog.list_products("ACCESSORIES", 1)["total"] == 2
    assert catalog.list_products("does-not-exist")["products"] == []
    for bad in (0, 101, -1, True):
        with pytest.raises(ValueError):
            catalog.list_products(limit=bad)
    with pytest.raises(ValueError):
        catalog.get_stock("not-a-sku")


def test_external_data_schema_and_revision(tmp_path):
    fixture = tmp_path / "products.json"
    fixture.write_text(json.dumps({"products": [{"sku": "A", "name": "A", "category": "test", "stock": 0, "reorder_point": 2}]}))
    catalog = Catalog(str(fixture))
    assert catalog.get_replenishment_recommendation("A")["recommended_quantity"] == 2
    assert catalog.revision == Catalog(str(fixture)).revision
    fixture.write_text('[{"sku":"A","stock":-1}]')
    with pytest.raises(ValueError):
        load_products(str(fixture))
    with pytest.raises(FileNotFoundError):
        load_products(str(tmp_path / "missing.json"))


def test_actual_mcp_initialize_list_and_call():
    from starlette.testclient import TestClient
    from server import app
    headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        init = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "showroom-test", "version": "1.0"}}})
        assert init.status_code == 200
        assert init.json()["result"]["serverInfo"]["name"] == "aurora-supply"
        listed = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = listed.json()["result"]["tools"]
        assert {t["name"] for t in tools} == {"list_products", "get_stock", "get_replenishment_recommendation"}
        assert all(t["annotations"]["readOnlyHint"] for t in tools)
        for name, args in [("list_products", {}), ("get_stock", {"sku": "AUR-001"}), ("get_replenishment_recommendation", {"sku": "AUR-001"})]:
            response = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": args}})
            assert response.status_code == 200
            assert not response.json()["result"].get("isError", False)
        routed = client.post("/mcp", headers={**headers, "Host": "aurora-tools.mcp.internal"}, json={"jsonrpc": "2.0", "id": 9, "method": "tools/list", "params": {}})
        assert routed.status_code == 200
        denied = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "create_order", "arguments": {}}})
        assert denied.json()["result"]["isError"] is True
        invalid = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "list_products", "arguments": {"limit": 10000}}})
        assert invalid.json()["result"]["isError"] is True
        assert client.post("/mcp", headers={**headers, "Host": "untrusted.example"}, json={}).status_code == 421


def test_real_showroom_forecast_connected():
    root = Path(__file__).resolve().parents[1]
    catalog = Catalog(str(root / "data/products.json"), str(root / "data/forecasts.json"))
    first = catalog.list_products()["products"][0]
    proposal = catalog.get_replenishment_recommendation(first["sku"])
    assert proposal["forecast"]["horizon_days"] == 7
    assert proposal["recommended_quantity"] >= 0
    assert proposal["order_created"] is False
    assert proposal["recommendation_type"] == "forecast-informed inventory proposal"


def test_forecast_policy_uses_21_days_and_deterministic_approval(tmp_path):
    products = tmp_path / "products.json"
    forecast = tmp_path / "forecast.json"
    products.write_text(json.dumps([{"sku":"A","name":"Filter","category":"Filters","stock":45,"reorder_point":80,"unit_price":42}]))
    forecast.write_text(json.dumps({"synthetic":True,"horizon_days":7,"model_version":"test","mlflow_run_id":"run-123","forecasts":[{"sku":"A","forecast_7d_units":130.26}]}))
    proposal = Catalog(str(products), str(forecast)).get_replenishment_recommendation("A")
    assert proposal["target_stock"] == 391
    assert proposal["recommended_quantity"] == 346
    assert proposal["estimated_total"] == 14532
    assert proposal["approval_role"] == "operations_manager"
    assert proposal["coverage_days"] == 21
    assert proposal["mlflow_run_id"] == "run-123"
    products.write_text(json.dumps([{"sku":"A","name":"Filter","category":"Filters","stock":0,"reorder_point":10,"unit_price":500}]))
    assert Catalog(str(products)).get_replenishment_recommendation("A")["approval_role"] == "assigned_buyer"


def test_openshell_subject_gate_requires_review_and_limits_callback_paths():
    import base64
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "gitops/components/guardrails/openshell/authz.py"
    spec = importlib.util.spec_from_file_location("openshell_authz", path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    def token(payload):
        return "e30." + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=") + ".signature"

    calls = []
    def allowed_review(value, audience, subject):
        calls.append((audience, subject))
        return True

    admin_path = gate.PREFIX + "ListSandboxes"
    admin = "Bearer " + token({"iss": "https://issuer.example", "sub": gate.ADMIN})
    assert gate.authorize(admin_path, admin, allowed_review)
    assert calls[-1] == ("showroom-openshell", gate.ADMIN)
    assert not gate.authorize(admin_path, admin, lambda *args: False)
    assert not gate.authorize(admin_path, "")
    workload = "Bearer " + token({"iss": "https://issuer.example", "sub": gate.WORKLOAD})
    assert gate.authorize(gate.BOOTSTRAP, workload, allowed_review)
    assert calls[-1] == ("openshell-gateway", gate.WORKLOAD)
    native = "Bearer " + token({"iss": "openshell-gateway:example", "sub": "spiffe://openshell/sandbox/example"})
    assert not gate.authorize(admin_path, native, allowed_review)
    assert not gate.authorize(gate.PREFIX + "UnknownFutureMethod", native, allowed_review)
    # This passes only the front gate; the native gateway must verify signature,
    # audience, expiry, and same-sandbox binding before executing the callback.
    assert gate.authorize(gate.PREFIX + "GetSandboxConfig", native, lambda *args: False)
