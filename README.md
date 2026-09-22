# OpenShift AI Showroom · Aurora Supply

Three connected journeys on OpenShift AI 3.5.1: **security and agents**, **inference platform**, and **data science and ML engineering**. Aurora Supply is a fictional distributor. All business documents and demand records are synthetic.

**[Open the presentation and lab guide](https://weslleyrosalem.com/rhoai-showroom/)** · [Architecture](docs/architecture/story.md) · [Installation](docs/operations/install.md) · [Validation status](docs/operations/validation.md)

Start with the [inference presentation](docs/demos/inference.md), [MaaS presentation](docs/demos/maas.md), or [project plan](docs/operations/project-plan.md). Collaboration conventions live in [AGENTS.md](AGENTS.md); the reusable operations skill is in [.agents/skills/showroom-operations](.agents/skills/showroom-operations/SKILL.md).

The primary namespace is `ai-showroom`. Shared services remain in their operators' namespaces. GPU profiles enforce a ceiling of **16 physical GPUs**, counting existing pools, pending nodes, and upgrade surge. GPU workloads and expensive experiments require an explicit capacity preflight.

```bash
git clone https://github.com/weslleyrosalem/rhoai-showroom.git
cd rhoai-showroom
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-docs.txt
mkdocs serve
```

Follow [Installation](docs/operations/install.md) to deploy. Requirements include a compatible ROSA cluster, OpenShift AI 3.5.1 and its dependencies, persistent storage, valid Red Hat pull credentials, network access, and authorized capacity. Kustomize does not provision cloud infrastructure implicitly.

| Directory | Contents |
|---|---|
| `docs/` | Presenter guides, test drives, and customer instructions |
| `gitops/` | Components, profiles, Argo CD, and bootstrap configuration |
| `apps/` | Business MCP server and integrated RAG application |
| `data/`, `notebooks/` | CC0 synthetic data, Ray, MLflow, and pipelines |
| `scripts/`, `tests/` | Preflight, benchmarking, operations, and verification |

The guide identifies GA, Technology Preview, Developer Preview, and ecosystem components individually. Rendering a manifest does not demonstrate a working feature. The validation record separates deployment from functional evidence and lists remaining limitations.

Original code is licensed under Apache-2.0; synthetic data is CC0. Trademarks, models, and dependencies retain their own licenses. This community demonstration is not a Red Hat product or support commitment.
