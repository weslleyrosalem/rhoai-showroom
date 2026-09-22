# Maturidade e limites

Maturidade do produto e resultado do teste são dimensões diferentes. A tabela identifica o que a documentação3.5 declara; o [registro de validação](../operations/validation.md) informa o que foi executado neste showroom.

| Recurso | Classificação/documentação | Limite relevante |
|---|---|---|
| MaaS core, quotas, chaves e grupos | GA | Chaves expiram e refletem acesso do consumidor |
| llm-d/vLLM core | Componentes do produto; extensões classificadas separadamente | Perfil e hardware determinam capacidade |
| vLLM via MaaS, WVA, gateway discovery | Technology Preview | Validar versão e caminho efetivo de tráfego |
| Hierarchical KV cache, roteamento LoRA/latência | Developer Preview | Um teste de prefix cache local não comprova tiering |
| MCP Gateway/Lifecycle | Technology Preview | OCP4.22+, RHCL, authN/authZ e versões compatíveis |
| Catálogo MCP por YAML na UI | Developer Preview | Catálogo não equivale a servidor ativo |
| NeMo Guardrails base | GA desde3.4 | Regras deste exemplo são determinísticas, não classificador LLM |
| NeMo + MCP IPP | Technology Preview | Plugins, TLS e teste de enforcement explícitos |
| MLflow | Integração saiu de TP em3.4 | SQLite/pod único são escolhas de laboratório |
| Tracing inline Playground | Technology Preview | Tracing MLflow e Tempo são caminhos distintos |
| Agentes salvos Playground | Developer Preview | Requer configuração funcional e maturidade indicada |
| EvalHub MCP e comparações UI | Technology Preview | Avaliar backend e UI separadamente |
| OpenShell | Extensão externa NVIDIA; Kubernetes experimental | Não é feature nativa/suportada RHOAI |
| MIG | Infraestrutura NVIDIA | L40S não suporta; A100/H100 compatíveis conforme perfil |
| Frontier externo | Integração de provedor e contrato separados | Não exige GPU local; exige credencial e orçamento próprios |

As fontes oficiais estão em [Fontes e versões](sources.md). O sufixo `v1alpha1` de um CRD não determina, sozinho, o estado de suporte comercial.

## Decisões do laboratório

- Estoque, vendas, documentos e destinatários de teste são sintéticos. A aplicação apenas recomenda e calcula; não efetua compras.
- RAG básico usa TF-IDF e cita os documentos recuperados. Embeddings/pgvector e AutoRAG são laboratórios próprios; não se usa o nome RAG para presumir que ambos são iguais.
- S3, MLflow e PostgreSQL têm persistência, mas não alta disponibilidade. O namespace tem quotas e RBAC; não é fronteira de proteção suficiente por si só para workloads hostis.
- Benchmark de engine mantém modelo/precisão/GPU iguais. Testes de escala e roteamento respondem a perguntas distintas. Ganhos não são universais e regressões também são resultados válidos.
- VirtualServer MCP filtra descoberta; não é autorização de ferramenta. O teste de acesso real é separado da lista exibida.
