#!/usr/bin/env python3
"""Protocol smoke through the authenticated gateway; no credentials printed."""
import argparse
import asyncio
import json
import os
import subprocess
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-env", default="MCP_TOKEN")
    parser.add_argument("--sku", default="AS-001")
    parser.add_argument("--prefix", default="aurora_")
    parser.add_argument("--virtual-server", default="ai-showroom/aurora-readonly")
    args = parser.parse_args()
    url = urlsplit(args.url)
    if url.username or url.password or not url.hostname or url.fragment:
        raise SystemExit("Use a URL without credentials or fragment")
    if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise SystemExit("Use TLS, except for a local port-forward")
    token = os.environ.get(args.token_env) or subprocess.check_output(["oc", "whoami", "-t"], text=True).strip()
    headers = {"Authorization": "Bearer " + token, "X-Mcp-Virtualserver": args.virtual_server}
    async with httpx.AsyncClient(headers=headers, follow_redirects=False) as client, streamable_http_client(args.url, http_client=client) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            expected = {args.prefix + name for name in ("list_products", "get_stock", "get_replenishment_recommendation")}
            assert names == expected, f"Unexpected tool names: {sorted(names)}"
            checks = []
            for name, arguments in [("list_products", {}), ("get_stock", {"sku": args.sku}), ("get_replenishment_recommendation", {"sku": args.sku})]:
                result = await session.call_tool(args.prefix + name, arguments)
                checks.append({"tool": name, "pass": not result.isError})
            assert all(c["pass"] for c in checks), "An expected read-only tool failed"
            print(json.dumps({"pass": True, "tools": sorted(names), "checks": checks}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
