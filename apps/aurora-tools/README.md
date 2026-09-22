# Aurora Supply MCP tools

A real MCP server backed entirely by synthetic data. Three read-only tools expose the product catalog, inventory, and replenishment proposals. With a forecast, the proposal extrapolates seven days of demand to 21-day coverage and keeps the reorder point as a minimum target. It returns quantity, unit price, total, approval role, model provenance, and `order_created:false`. There is no purchase or inventory-update endpoint.

## Run locally

Python 3.12 is the tested runtime. From the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r apps/aurora-tools/requirements.txt pytest==8.3.5
.venv/bin/python -m pytest tests/test_aurora_tools.py -q
AURORA_PRODUCTS_PATH="$PWD/data/products.json" \
AURORA_FORECASTS_PATH="$PWD/data/forecasts.json" \
.venv/bin/python apps/aurora-tools/server.py
```

The Streamable HTTP endpoint is `http://localhost:8000/mcp`; `/health` contains no private data. User authentication belongs to Gateway/Authorino. Keep this backend private behind NetworkPolicy.

The [official MCP SDK 1.27.2](https://github.com/modelcontextprotocol/python-sdk/tree/v1.27.2) and all resolved dependencies are pinned. SDK 2 requires a new compatibility test. The UBI 9/Python 3.12 container supports an arbitrary non-root UID, a read-only root filesystem, no Kubernetes token, and no egress. Configured invalid data fails startup; the small fallback dataset is used only when no product file is configured.

## Data and builds

```sh
.venv/bin/python apps/aurora-tools/sync_data.py
oc apply --dry-run=server -k gitops/components/mcp/backend
```

The script validates and copies canonical `data/` snapshots into the backend and lifecycle Kustomize roots. The backend ConfigMap hash triggers a rollout when data changes. The lifecycle ConfigMap has a stable name; restart its managed Deployment after updating the snapshot. After training, import the approved forecast into `data/forecasts.json`, synchronize, and review the diff.

Send only these four reviewed files to the binary build:

```sh
oc apply -k gitops/components/mcp/backend
build_context=$(mktemp -d)
cp apps/aurora-tools/Containerfile apps/aurora-tools/requirements.txt \
   apps/aurora-tools/business.py apps/aurora-tools/server.py "$build_context/"
oc start-build aurora-tools -n ai-showroom --from-dir="$build_context" --follow
```

The BuildConfig does not start automatically. Do not upload `.venv`, credentials, or local files. Pin the promoted image digest in a cluster overlay.

## Validate

```sh
.venv/bin/python apps/aurora-tools/smoke_mcp.py --url "https://MCP_HOST/mcp"
.venv/bin/python apps/aurora-tools/check_guardrails.py --url "https://NEMO_HOST"
```

Helpers use `MCP_TOKEN`/`NEMO_TOKEN`, or the current `oc` token in memory; they never print credentials. HTTPS verification stays enabled and redirects are rejected. NeMo accepts a private CA through `--ca-file`. Read the [MCP lab](https://weslleyrosalem.github.io/rhoai-showroom/labs/mcp/) for observed version-specific limitations.

The catalog helper additionally requires `PyYAML==6.0.2`; it merges only the Aurora source into the shared ConfigMap and preserves unrelated entries. It checks the expected API server and user before applying.
