# OpenShift AI Showroom · Aurora Supply

Três histórias conectadas em OpenShift AI 3.5.1: **segurança e agentes**, **plataforma de inferência**, **ciência de dados e ML**. A Aurora Supply é uma distribuidora fictícia; todo o conteúdo comercial e histórico de demanda é sintético.

**[Abra o guia de apresentação e laboratórios](https://weslleyrosalem.github.io/rhoai-showroom/)** · [Arquitetura](docs/architecture/story.md) · [Instalação](docs/operations/install.md) · [Validação real](docs/operations/validation.md)

O namespace principal é `ai-showroom`. Recursos compartilhados pertencem aos namespaces oficiais dos operadores. Os perfis GPU têm teto de **16 GPUs físicas**, incluindo pools existentes, nós pendentes e margem de atualização. Modelos GPU e experimentos caros são ativados explicitamente após o preflight.

```bash
git clone https://github.com/weslleyrosalem/rhoai-showroom.git
cd rhoai-showroom
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-docs.txt
mkdocs serve
```

Para implantar, siga [Instalação](docs/operations/install.md). Requer ROSA compatível, OpenShift AI 3.5.1 e seus operadores, storage persistente, pull-secret Red Hat válido, conectividade e capacidade autorizada. Não existe provisionamento cloud implícito no `kustomize`.

| Caminho | Conteúdo |
|---|---|
| `docs/` | Guias do apresentador, test drives e instruções ao cliente |
| `gitops/` | Componentes, perfis, Argo CD e bootstrap |
| `apps/` | MCP de negócio e aplicação RAG integrada |
| `data/`, `notebooks/` | Dados CC0, Ray, MLflow e pipelines |
| `scripts/`, `tests/` | Preflight, benchmark, operação e verificação |

GA, Technology Preview, Developer Preview e extensão externa são identificados por recurso no guia. Um manifesto renderizar não significa que a funcionalidade foi validada. O registro de validação separa os dois casos e informa os bloqueios restantes.

Código original sob Apache-2.0; dados sintéticos sob CC0. Marcas, modelos e dependências mantêm suas próprias licenças. Este projeto é um laboratório compartilhável, não um produto ou declaração de suporte da Red Hat.
