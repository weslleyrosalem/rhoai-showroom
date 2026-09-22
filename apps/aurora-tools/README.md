# Aurora Supply MCP tools

Servidor MCP real para dados inteiramente sintéticos. Expõe três ferramentas, todas de leitura: `list_products`, `get_stock` e `get_replenishment_recommendation`. A recomendação usa a previsão de sete dias quando há arquivo configurado; sem previsão usa a regra explícita de ponto de reposição. A resposta identifica método, versão dos dados e `order_created:false`. Não há endpoint de compra ou atualização do estoque.

## Executar e testar localmente

Python3.12 é a versão testada. Execute na raiz do repositório:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r apps/aurora-tools/requirements.txt pytest==8.3.5
.venv/bin/python -m pytest tests/test_aurora_tools.py -q
AURORA_PRODUCTS_PATH="$PWD/data/products.json" \
AURORA_FORECASTS_PATH="$PWD/data/forecasts.json" \
.venv/bin/python apps/aurora-tools/server.py
```

Endpoint `http://localhost:8000/mcp`, Streamable HTTP; `GET /health` não contém dados privados. O servidor local não faz autenticação de usuário: no cluster esta é responsabilidade do Gateway/Authorino e das NetworkPolicies. Não exponha o backend diretamente.

Foi fixado o [SDK oficial MCP1.27.2](https://github.com/modelcontextprotocol/python-sdk/tree/v1.27.2), API `FastMCP`, para compatibilidade com o gateway0.7.1 e protocolo2025. O SDK2 muda APIs/protocolo e exige novo ensaio. Todas as dependências resolvidas estão fixadas em `requirements.txt`. As mensagens de depreciação observadas no ambiente de teste não impediram as chamadas MCP; a validação real de Gateway permanece separada.

`Containerfile` usa UBI9/Python3.12 com digest do índice multiarquitetura. O app suporta UID arbitrário, filesystem somente leitura, sem token Kubernetes e sem egress. O backend não busca dados da internet. `AURORA_PRODUCTS_PATH`/`AURORA_FORECASTS_PATH` são parâmetros administrativos de arquivo; não podem ser controlados por argumentos MCP. Se um arquivo configurado for inválido, o processo falha; o fallback só vale quando não há arquivo de produtos configurado.

## Dados compartilhados e GitOps

```sh
.venv/bin/python apps/aurora-tools/sync_data.py
oc apply --dry-run=server -k gitops/components/mcp/backend
```

O script valida o contrato e copia as fixtures canônicas `data/` para o diretório Kustomize. A cópia evita `--load-restrictor=LoadRestrictionsNone`. O nome com hash do ConfigMap muda quando os dados mudam e o Deployment referencia a nova versão. O processo carrega o snapshot ao iniciar. Depois do treinamento, importe a previsão aprovada em `data/forecasts.json`, rode `sync_data.py` e revise o diff antes de sincronizar.

Para construir a imagem via BuildConfig binário, envie somente os quatro arquivos do contexto:

```sh
oc apply -k gitops/components/mcp/backend
build_context=$(mktemp -d)
cp apps/aurora-tools/Containerfile apps/aurora-tools/requirements.txt \
   apps/aurora-tools/business.py apps/aurora-tools/server.py "$build_context/"
oc start-build aurora-tools -n ai-showroom --from-dir="$build_context" --follow
```

O BuildConfig não inicia automaticamente; isso evita build com contexto incompleto. Para promoção por GitOps, publique a imagem em registry acessível e fixe seu digest no overlay do cluster. Não inclua `.venv`, tokens ou arquivos locais no contexto.

## Verificar integração

```sh
.venv/bin/python apps/aurora-tools/smoke_mcp.py --url "https://SEU_HOST_MCP/mcp"
.venv/bin/python apps/aurora-tools/check_guardrails.py --url "https://SEU_HOST_NEMO"
```

Os scripts usam `MCP_TOKEN`/`NEMO_TOKEN` quando presentes, caso contrário obtêm o token da sessão `oc` em memória. Não imprimem credenciais. A validação TLS fica ativa; uma CA privada pode ser informada ao script NeMo por `--ca-file`.
