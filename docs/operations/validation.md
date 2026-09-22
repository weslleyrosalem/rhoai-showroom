# Estado de validação

Registro iniciado em **22/09/2026 UTC**, durante a montagem do showroom. Esta página distingue execução real, schema aceito e recursos opcionais. Não use o status de um Deployment como prova de toda a jornada.

| Área | Evidência já observada | Situação |
|---|---|---|
| Namespace e base | ai-showroom, quota, RBAC e storage S3 disponíveis | Implantado |
| MLflow | Available, migração concluída; versão3.14.0 | Serviço disponível; fluxo de ciência em ensaio |
| Tempo | Instância Ready, PVC e retenção168h | Serviço disponível; spans específicos em validação |
| GitOps Operator | Controlador e serviços Running | Adoção Argo em andamento |
| MaaS | Anônimo401; standard200; test-drive200→429; standard continua200 | Teste funcional passou |
| NeMo | Entradas/saídas permitidas; e-mail sintético, marcador de segredo e override bloqueados | Teste direto passou |
| MCP | Backend ativo, TLS/AuthPolicy em ajuste para audiência ROSA | Integração em ensaio |
| Ray/DSPA/Workbench | Manifests aceitos e aplicados | Execução em ensaio |
| Modelos GPU | Pool4L40S por nó criado, máximo2nós | Startup e benchmark pendentes |
| AutoRAG/AutoML/EvalHub | Guias e componentes preparados | Resultados ainda não aprovados |
| MIG/OpenShell/IPP avançado | Pré-requisitos e limitações documentados | Não chamar de validado |

O pool ativo possui teto conservador de16GPUs incluindo máximos dos pools existentes e surge. Isso não significa16GPUs ligadas continuamente nem que todos os perfis podem ser combinados.

## Critérios de aceite por jornada

**Segurança:** initialize/tools-list/tools-call via gateway autenticado; anônimo e identidade não autorizada negados; entrada permitida e bloqueada; trace e decisão visíveis. NeMo direto e enforcement IPP têm testes diferentes.

**Plataforma:** modelos respondem, quotas são aplicadas, catálogo mostra apenas modelos curados, Argo converge; benchmark contém amostras/configuração e medições reais. Multi-node precisa evidência de dois nós distintos.

**Ciência:** job Ray conclui, prevê todos os SKUs com baseline/quality gate, publica artefatos; RAG recupera documentos e chama MCP/MaaS; MLflow registra run/trace; avaliação tem resultado e não apenas job criado.

## Reexecutar verificações locais

```bash
python -m unittest discover -s tests -p 'test_capacity.py'
python -m unittest discover -s tests -p 'test_benchmark.py'
python -m unittest discover -s tests -p 'test_science.py'
python scripts/validate_repo.py
mkdocs build --strict
python scripts/showroom.py status --expected-server "$SHOWROOM_SERVER"
```

Os testes de MCP exigem suas dependências próprias, descritas em `apps/aurora-tools/README.md`. Evidências de cluster devem ser sanitizadas antes de publicação; chaves, tokens, endereços privados e dados de clientes não pertencem à página pública.
