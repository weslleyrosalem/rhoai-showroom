---
title: EvalHub e Garak
---
# Avaliar antes de promover

O EvalHub compartilhado reside em `redhat-ods-applications`; `ai-showroom` é o tenant. PostgreSQL preserva seu histórico em PVC. Criar MLflow antes do EvalHub evita o problema conhecido de workspace desabilitado.

Providers descobertos no operador instalado: `garak`, `ragas` e `lm_evaluation_harness`. O nome de configuração Kubernetes do último usa hífens; o ID da API usa underscores. O benchmark Garak `quick` existe nesse provider e executa um teste curto de segurança. Isso não certifica um modelo.

No terminal autenticado, configure `EVALHUB_URL` com a Route real do serviço, `MAAS_BASE_URL` com a URL do gateway e `MAAS_MODEL_ID` com o modelo publicado. Essas variáveis não contêm a API key. A key é referenciada pelo Secret `showroom-maas-key` no tenant.

```bash
python3 scripts/science.py eval-submit
python3 scripts/science.py eval-status --job-id ID_RETORNADO
```

O script descobre o provider antes de enviar a requisição. O exemplo JSON fica em `gitops/components/evaluation/garak-request.example.json`; os placeholders precisam de configuração antes do uso. A submissão passa por `/api/v1/evaluations/jobs`, com `X-Tenant: ai-showroom` e identidade autenticada.

Aceite: job `completed`, métricas reais, experimento `aurora-model-safety` e `evalcard.json`. Criar o CR ou ver a página não é aceite. Se o cartão faltar, investigue mesmo que o job esteja concluído. Compare o mesmo conjunto antes/depois de guardrails, com o mesmo modelo e parâmetros.

Para RAG, use os casos de `data/eval/autorag.json` e o provider RAGAS, conferindo primeiro o formato esperado pelo adapter. Não enviar o JSON AutoRAG a qualquer adapter sem conversão de esquema.

As notas3.5 ainda distinguem core Evaluation Stack DP de UI/SDK/CLI/MCP TP. A página de validação registra o que foi realmente executado nesta instalação. [EvalHub oficial](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate).
