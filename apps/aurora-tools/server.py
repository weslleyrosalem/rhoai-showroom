"""Official MCP SDK server; expose through the authenticated showroom gateway."""
from __future__ import annotations

import os
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from business import Catalog

DEFAULT_HOSTS = ["localhost:*", "127.0.0.1:*", "[::1]:*", "testserver",
                 "aurora-tools:*", "aurora-tools.ai-showroom.svc:*",
                 "aurora-tools.ai-showroom.svc.cluster.local:*", "aurora-tools.mcp.internal:*"]
allowed_hosts = [h.strip() for h in os.environ.get("AURORA_ALLOWED_HOSTS", ",".join(DEFAULT_HOSTS)).split(",") if h.strip()]
allowed_origins = [h.strip() for h in os.environ.get("AURORA_ALLOWED_ORIGINS", "http://localhost:*,http://127.0.0.1:*").split(",") if h.strip()]
catalog = Catalog()
mcp = FastMCP("aurora-supply", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
              stateless_http=True, json_response=True,
              instructions="Read-only synthetic Aurora Supply catalog and inventory. Proposals do not create orders.",
              transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                                          allowed_hosts=allowed_hosts, allowed_origins=allowed_origins))
annotations = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@mcp.tool(annotations=annotations)
def list_products(category: Annotated[str | None, Field(max_length=160)] = None,
                  limit: Annotated[int, Field(ge=1, le=100)] = 50) -> dict:
    """List synthetic products. Use exact returned SKUs for stock and replenishment calls."""
    return catalog.list_products(category, limit)


@mcp.tool(annotations=annotations)
def get_stock(sku: Annotated[str, Field(min_length=1, max_length=160)]) -> dict:
    """Read current synthetic stock and reorder point for one exact SKU."""
    return catalog.get_stock(sku)


@mcp.tool(annotations=annotations)
def get_replenishment_recommendation(sku: Annotated[str, Field(min_length=1, max_length=160)]) -> dict:
    """Propose replenishment from versioned inventory and optional seven-day forecast. The response identifies its source. No order is created."""
    return catalog.get_replenishment_recommendation(sku)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "aurora-tools", "synthetic_data": True})


app = mcp.streamable_http_app()
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
