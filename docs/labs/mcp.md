# MCP: ferramentas reais para o assistente Aurora

**Maturidade:** MCP Gateway e MCP Lifecycle são Technology Preview no RHOAI3.5. O servidor Aurora é código demonstrativo deste repositório. O caminho validado deve incluir autenticação e chamadas MCP reais, além de pods Ready.

A pergunta “Qual produto precisa de reposição?” conecta o catálogo e estoque aos resultados da previsão de demanda. O modelo consulta ferramentas; ele não recebe liberdade para executar comandos, acessar URLs arbitrárias ou efetuar pedidos.

## O que é implantado

```text
Cliente/Playground/RAG + identidade
          |
          v
Route TLS → Gateway showroom-mcp (listener mcp8080, AuthPolicy)
          |
          v
MCP broker/router → listener privado mcps8081
          |
          v
aurora-tools:8000/mcp → produtos + previsão sintéticos versionados
```

Os CRDs locais são `mcp.kuadrant.io/v1alpha1`: `MCPGatewayExtension`, `MCPServerRegistration` e `MCPVirtualServer`. O backend usa SDK oficial, Streamable HTTP e respostas JSON; as ferramentas federadas se chamam `aurora_list_products`, `aurora_get_stock` e `aurora_get_replenishment_recommendation`.

`MCPVirtualServer/aurora-readonly` apenas organiza a descoberta. O cliente envia `X-Mcp-Virtualserver: ai-showroom/aurora-readonly`; removê-lo pode mudar a lista. **Não é uma fronteira de autorização.** A autorização efetiva deste módulo concede às identidades permitidas o conjunto de ferramentas de leitura. [Virtual servers0.7.1](https://github.com/Kuadrant/mcp-gateway/blob/v0.7.1/docs/guides/virtual-mcp-servers.md)

## Pré-requisitos

- Namespace `ai-showroom`, GatewayClass `openshift-default`, RHCL/Authorino e MCP Gateway Operator instalados.
- ServiceAccounts `showroom-visitor`, `showroom-engineer` e `aurora-science` quando usados pela jornada.
- Imagem `aurora-tools:1.0.0` construída conforme [README do app](../../apps/aurora-tools/README.md).
- TrustyAI só é necessário para a etapa guardrails, não para consulta MCP básica.

Instalar o MCP Lifecycle pelo DSC permite a experiência de deploy pelo catálogo, mas não configura Gateway/auth automaticamente. Este módulo implanta a aplicação conhecida por Deployment/Service, declarativamente; não afirma que ela foi instalada via catálogo. [Lifecycle3.5](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management)

## Instalação e gate de publicação

Execute da raiz do repositório com uma sessão de administrador no cluster destinado ao showroom:

```sh
oc apply --dry-run=server -k gitops/components/mcp
oc apply -k gitops/components/mcp
oc rollout status deployment/aurora-tools -n ai-showroom --timeout=180s
oc wait -n ai-showroom mcpgatewayextension/showroom-mcp --for=condition=Ready --timeout=180s
oc get authpolicy showroom-mcp-auth -n ai-showroom
```

As NetworkPolicies incluem o controlador0.7.1 observado em `openshift-operators`, com labels `app=mcp-controller` e `component=controller`, pois ele consulta o status de descoberta do broker. Se instalar o operador em outra namespace, ajuste esse seletor de forma restrita no overlay.

O Gateway é ClusterIP. `gitops/components/mcp` não inclui Route pública. A AuthPolicy autentica por Kubernetes TokenReview e permite `aiadmin`, grupos cujo nome começa com `showroom-` e as três ServiceAccounts indicadas. Não concede cluster-admin a essas identidades. Em um cluster de cliente, substitua a identidade nominal `aiadmin` e os grupos pelos seus valores revisados.

O audience inicial é `https://kubernetes.default.svc`; valide-o com o token real do cluster. Um token emitido com audience diferente exige ajustar a configuração, não desabilitar autenticação. Authorino precisa criar TokenReview; normalmente seu operador já concede essa permissão. Verificação read-only:

```sh
oc auth can-i create tokenreviews.authentication.k8s.io \
  --as=system:serviceaccount:kuadrant-system:authorino-authorino
```

Se retornar `no`, um administrador deve conceder somente `create` em `tokenreviews.authentication.k8s.io` ao SA real do Authorino, por ClusterRole/ClusterRoleBinding; TokenReview é cluster-scoped, portanto uma RoleBinding namespaced não resolve. Não use cluster-admin. [TokenReview/Authorino](https://docs.kuadrant.io/dev/authorino/docs/features/)

Antes de publicar, exija AuthPolicy `Enforced=True` e teste pelo listener8080 via port-forward autorizado:

1. Sem token:401.
2. Token válido de SA não permitida:403.
3. `showroom-visitor`/`aurora-science`: initialize, tools/list e as três tools/call funcionam.
4. Tentativa `create_order`: erro; nenhum estado muda.
5. Pod sem permissão de rede não alcança diretamente backend8000, broker8080 nem listener8081.

Após passar esses gates:

```sh
oc apply -k gitops/components/mcp/public
oc get route showroom-mcp -n ai-showroom -o jsonpath='{.spec.host}'
```

A Route usa certificado padrão do ingress e redireciona HTTP para HTTPS. O host é gerado pelo OpenShift. Atualize `MCPGatewayExtension.spec.publicHost` no overlay local com esse host antes de usar discovery OAuth; o endpoint básico com bearer é `/mcp`. Não exponha a porta8081 nem crie Route para `aurora-tools`.

## Test drive

No cliente MCP/Playground, use o host HTTPS, bearer token autorizado e o header do servidor virtual. Peça:

> Liste os produtos da Aurora. Consulte o estoque do AS-001 e proponha reposição, explicando a origem da previsão. Não efetue pedidos.

Abra cada retorno de ferramenta. A recomendação inclui `data_revision`, `forecast.model_version`, horizonte e `order_created:false`. Se `forecast:null`, a regra é o ponto de reposição e não um modelo treinado; não apresente esse fallback como ML.

No roteiro técnico, execute [smoke_mcp.py](../../apps/aurora-tools/smoke_mcp.py). O script verifica ferramentas e chamadas reais sem imprimir o token. `Ready=True` no registro é insuficiente porque a descoberta do broker é assíncrona. [Registro MCP](https://github.com/Kuadrant/mcp-gateway/blob/v0.7.1/docs/guides/register-mcp-servers.md)

## Diagnóstico

| Sintoma | Verificação |
|---|---|
|421 do backend|Host recebido fora da allowlist SDK; ajuste somente hosts internos esperados|
|401|Token expirado/audience incorreto; verificar TokenReview/AuthPolicy|
|403|Identidade fora da lista permitida; checar grupo/SA real|
|Lista vazia|Registro/HTTPRoute, prefixos, header virtual e descoberta assíncrona|
|Timeout backend|NetworkPolicy: labels do broker `app.kubernetes.io/name=mcp-gateway` e `managed-by=mcp-gateway-controller`|
|ImagePullBackOff|Build/push da imagem e ImageStreamTag, não credenciais MCP|

O [guia RHCL1.4](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_the_mcp_gateway/mcp-gateway-install) descreve o operador e listeners. Os manifests deste repositório foram adaptados ao schema instalado; comportamento funcional só é validado pelos testes no cluster.
