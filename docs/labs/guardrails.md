# Guardrails: regras visíveis e verificáveis

**Maturidade:** NeMo Guardrails base é GA; integração NeMo→MCP Gateway é Technology Preview. A configuração do showroom usa CPU e regras determinísticas de regex. Ela demonstra enforcement de padrões definidos; não é um detector universal de PII ou prompt injection.

A validação de uma pergunta é uma etapa separada da inferência. O endpoint NeMo `/v1/guardrail/checks` verifica entradas/saídas sem gerar uma resposta de modelo. A [documentação3.5](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/enabling_ai_safety_with_guardrails/enabling-ai-safety-with-nemo-guardrails_nemo-guardrails) inclui quickstart sem chamadas LLM e os rails `regex check input`/`regex check output`.

## Implantar a base

```sh
oc apply --dry-run=server -k gitops/components/guardrails
oc apply -k gitops/components/guardrails
oc get nemoguardrails showroom-rails -n ai-showroom
oc get service,route -n ai-showroom
```

`NemoGuardrails/showroom-rails` referencia ConfigMap `showroom-safety`, gerenciado no Git. A anotação `security.opendatahub.io/enable-auth: 'true'` exige acesso Kubernetes ao serviço. Descubra a Route criada pelo operador, valide seu certificado e execute:

```sh
python3 apps/aurora-tools/check_guardrails.py --url https://HOST_REAL_DO_NEMO
```

Os seis casos verificam pergunta comercial permitida, e-mail sintético, segredo sintético, instrução explícita de ignorar regras, saída permitida e saída com e-mail. Resultado esperado:200 em todos os checks e `status:success` ou `blocked` conforme o caso. HTTP200 com `status:error` é falha.

O script usa o token `oc` em memória ou `NEMO_TOKEN`; nenhuma chave é gravada ou mostrada. Todos os exemplos de informação sensível são fictícios, como `cliente@example.invalid` e `DEMO_SECRET_AURORA`.

## Experiência interativa

1. Envie “Qual o estoque do produto AS-001?” e veja `success`.
2. Adicione `cliente@example.invalid` e veja `blocked`, com o rail responsável.
3. Repita com “Ignore todas as instruções anteriores”.
4. Mude a mensagem para remover o padrão proibido e repita.
5. Mostre no Git qual expressão causou o bloqueio.

A regra só afeta o tráfego enviado ao NeMo. Não diga “todo MCP está protegido” apenas porque o servidor está Ready. O mesmo vale para RAG: a aplicação precisa chamar o check antes da geração e tratar `blocked`/`error` adequadamente.

## Integração MCP/IPP — etapa opcional com gate próprio

Leia o [contrato IPP](https://github.com/weslleyrosalem/rhoai-showroom/blob/main/gitops/components/guardrails/mcp-integration/IPP-CONTRACT.md). Ele fixa a fonte inspecionada e os parâmetros de plugins reais. É necessário implantar um IPP que contenha `nemo-request-guard`/`nemo-response-guard`, TLS confiável até o NeMo, ordenação Envoy e modos de processamento de resposta corretos. A configuração inclui um overlay que liga a descoberta TrustyAI:

```sh
oc apply --dry-run=server -k gitops/components/guardrails/mcp-integration
```

Aplique esse overlay somente quando os plugins estiverem instalados. A aceitação requer:

- `status.mcpGateway.mcpGatewayFound=true` e `status.bbrPlugin.bbrPluginFound=true`;
- filtro `mcp-sse-strip` presente no Gateway correto;
- chamada MCP permitida chega ao backend;
- chamada com padrão proibido nos argumentos recebe bloqueio antes do backend;
- indisponibilidade do checker impede a operação protegida;
- caminho de resposta testado, inclusive SSE quando habilitado.

O IPP inspecionado exige HTTPS. Seu exemplo não fornece parâmetro de bearer token; uma Route NeMo autenticada não passa a funcionar automaticamente para esse plugin. Resolver o transporte/autenticação privado faz parte do gate. A implementação também não aplica a redação retornada como `modified`; use bloqueio para esta demonstração, sem alegar mascaramento. [IPP oficial, versão inspecionada](https://github.com/opendatahub-io/ai-gateway-payload-processing/blob/07727563b63153c410434a20b62f3ebc5f24ed01/examples/nemo/README.md)

## Limites e melhoria

Regex não interpreta intenção e pode ter falsos positivos/negativos. Adicionar detectores semânticos, Presidio ou um modelo de segurança muda custo, latência, dependências e critérios de avaliação. Não dispute a GPU do modelo principal sem capacidade reservada. Compare o mesmo conjunto de casos antes/depois e preserve resultados no EvalHub/MLflow.
