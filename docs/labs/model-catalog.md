# Laboratório — catálogo Qwen curado

A Aurora Supply oferece uma escolha pequena e compreensível, em vez de apresentar milhares de modelos sem orientação. A fonte **Aurora Supply · Qwen curated** inclui Qwen3-0.6B, Qwen3-4B-Instruct-2507 e Qwen3-32B. O primeiro serve a smoke tests, o segundo ao assistente e o terceiro ao módulo de escala.

O catálogo é compartilhado no cluster. A configuração vive em `rhoai-model-registries/model-catalog-sources`, não dentro de `ai-showroom`. O repositório conserva somente a entrada que possui; não entrega um ConfigMap que sobrescreve fontes de outras equipes.

## Curadoria pela interface

Em Settings → Model resources and operations → Model catalog settings, adicione uma fonte Hugging Face com organização `Qwen`. No campo de inclusão, use os três nomes acima **sem** `Qwen/`. Faça Preview, confirme os resultados e aguarde Connected. A documentação3.5 limita essas fontes a modelos públicos não gated e exige conectividade ao Hugging Face. Um item importado não se torna automaticamente um modelo validado/suportado pela Red Hat. [Adicionar fonte](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/manage_and_govern_model_catalog_sources/add-model-catalog-source_manage-govern-model-catalog-sources), [limitações](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/manage_and_govern_model_catalog_sources/manage-model-catalog-sources-in-dashboard_manage-govern-model-catalog-sources).

## Curadoria reproduzível

O helper requer Python e PyYAML no ambiente de ferramentas. Execute primeiro em modo leitura, passando o servidor esperado da instalação:

```bash
python3 gitops/components/platform/catalog/merge_catalog.py \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER"
```

Confira os nomes e a quantidade de fontes preservadas. `--apply` realiza somente o merge da entrada `showroom-qwen`. Um teste de `resourceVersion` evita sobrescrever uma edição concorrente feita no dashboard ou por outro processo:

```bash
python3 gitops/components/platform/catalog/merge_catalog.py \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER" --apply
```

Reexecutar com a mesma configuração retorna UNCHANGED. Se ocorrer conflito, releia o estado e revise novamente. Não reinicie o catálogo nem troque os default sources para resolver um conflito. Em GitOps, execute esse passo controlado durante a integração da instalação; não atribua a duas Applications a propriedade integral do mesmo ConfigMap.

## Do modelo ao hardware

| Modelo | Pesos BF16 aproximados | Profile inicial | Licença |
|---|---:|---|---|
| Qwen3-0.6B |1,4GiB| Smoke test GPU; CPU ainda não validado neste kit |Apache2|
| Qwen3-4B-Instruct-2507 |7,5GiB| L40S1, contexto8192 |Apache2|
| Qwen3-32B |61GiB| L40S4/TP4 |Apache2|
| Qwen2.5-72B-Instruct, opt-in separado |135,4GiB| TP4; duas réplicas usam8GPUs |Licença Qwen específica|

Esses valores representam **somente pesos**. Runtime, ativações, KV cache e concorrência precisam de memória adicional. A seleção padrão evita `trust_remote_code`. Qwen72B não está no catálogo curado padrão e não é incluído no profile full; sua licença não deve ser apresentada como Apache2. [Qwen4B](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), [Qwen32B](https://huggingface.co/Qwen/Qwen3-32B), [Qwen72B](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct).

SHAs e runtime digest estão em `gitops/components/models/models.lock.json`. O runtime vem do preset instalado de RHOAI3.5.1; pesos são públicos, mas a imagem Red Hat requer o pull-secret/entitlement válido da instalação. O schema aceito pelo Kubernetes não comprova download, startup nem qualidade de tool calling.

## Aceite

A fonte deve mostrar Connected, apenas os três modelos curados, links/licenças corretos e nenhuma remoção de fontes anteriores. Um deployment escolhido precisa carregar o SHA previsto, ficar Ready e responder pelo MaaS. O teste de ferramentas também precisa produzir um `tool_call` com schema válido antes de ser usado pelo agente Aurora. O modelo0.6B CPU permanece marcado como bloqueado até validar uma imagem CPU no hardware real.
