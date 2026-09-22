# Laboratório — eficiência de engine e roteamento

Este laboratório mede a mesma tarefa sintética de reposição de estoque da Aurora Supply. Os scripts não incluem números de performance pré-fabricados. Falha, ausência de usage ou configurações diferentes aparecem explicitamente no resultado.

## Perguntas separadas

| Comparação | Manter igual | O que pode mudar |
|---|---|---|
| Transformers versus vLLM |Qwen4B/SHA, tokenizer/template, BF16, uma L40S, recursos, prompts, output cap e carga|Engine e sua implementação de batching |
| vLLM + round-robin versus vLLM + llm-d/EPP |Duas réplicas TP4, mesmos8GPUs/nós, digest vLLM, cache, modelo e carga|Roteamento |
| TP1 versus TP4;4 versus8GPUs |Modelo e carga definidos|Escala; reportar tokens/s **e** tokens/s/GPU separadamente |

A primeira comparação não comprova benefício de llm-d; a segunda não compara modelos diferentes. Duas réplicas TP4 são escala horizontal, não um modelo repartido entre nós. Em PCIe/Ethernet, mais GPUs podem aumentar overhead; o resultado medido decide.

## Metadados obrigatórios

Crie um JSON privado a partir dos recursos efetivamente executados, por exemplo:

```json
{
  "engine": "vllm",
  "model_revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
  "tokenizer_revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
  "dtype": "bfloat16",
  "gpu_product": "NVIDIA-L40S",
  "gpu_count": 1,
  "node_count": 1,
  "max_model_len": 8192,
  "chat_template_sha256": "HASH_SHA256_REAL_DO_TEMPLATE_EFETIVO",
  "cache_mode": "off",
  "tensor_parallel": 1,
  "pipeline_parallel": 1,
  "data_parallel": 1,
  "image_digest": "REGISTRY/IMAGE@sha256:DIGEST_REAL",
  "scheduling": "one GPU; endpoint continuous batching"
}
```

O script exige pins e consistência, mas não atesta automaticamente que o servidor usa os metadados informados. Confirme imagem, argumentos, GPU placement e template no workload e guarde a evidência. Metadados falsos não viram uma comparação válida por passarem no parser.

Para engine, desative prefix cache nos dois lados. Para routing, mantenha a mesma configuração de cache no vLLM dos dois caminhos. Não misture resultados dos dois experimentos.

## Cliente de medição

O cliente usa apenas Python standard library. HTTPS exige certificado válido; HTTP é permitido somente em localhost para port-forward. A chave é lida da variável `SHOWROOM_API_KEY`, nunca de argumento CLI nem do arquivo de resultados.

```bash
python3 scripts/benchmark.py run \
  --base-url "$BENCHMARK_BASE_URL" --model aurora-qwen-4b \
  --metadata /caminho/privado/vllm-metadata.json \
  --requests 30 --concurrency 4 --max-tokens 128 --warmup 5 \
  --prefix-mode repeated-prefix \
  --output /caminho/privado/vllm-run-1.json
```

O workload tem políticas e48SKUs fictícios. `repeated-prefix` mantém o prefixo; `distinct-prefix` muda um identificador no início. O comprimento em caracteres é controlado, mas os tokens reais vêm de usage. O output guarda timestamps, statusHTTP, latência, TTFT, TPOT aproximado, usage e hashes dos prompts; não guarda respostas ou credenciais.

TTFT aqui é a primeira parte **não vazia de texto/reasoning** recebida por SSE, medida do cliente. Não confundir com a latência interna do engine. TPOT divide o tempo após a primeira parte pelo número de tokens de output menos1; SSE pode agrupar tokens, portanto é uma estimativa.

Limites rígidos do cliente: até200requests,16concorrentes,256tokens de output/request,600s de duração da etapa e120s de timeout/request. Chamadas em andamento podem terminar após a duração; cada leitura continua limitada pelo timeout. Warmup é separado e limitado a10requests. Comece com os defaults pequenos para validar a API e a subscription.

## Baseline Transformers executável

O subcomando opcional `serve-transformers` precisa de PyTorch, Transformers, FastAPI e Uvicorn em um container GPU. Pode usar uma imagem de runtime previamente validada que contenha essas dependências; o cliente de benchmark não instala nada. Execute na GPU dedicada, em outra etapa, preservando o modelo anterior:

```bash
python3 scripts/benchmark.py serve-transformers \
  --model-path /mnt/models \
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --served-model aurora-qwen-4b --host 127.0.0.1 --port 8000
```

Os pesos em `/mnt/models` precisam corresponder ao SHA registrado. O baseline usa BF16, `trust_remote_code=False`, geração determinística e **batchsize1 serializado**. Ele é uma referência explícita para latência single-request e efeito de concorrência; não representa todas as otimizações possíveis em Transformers. Se fizer um baseline com batching estático maior, registre e valide essa implementação separadamente.

O streamer emite incrementos de tokens decodificados para evitar o buffering por palavras do TextIteratorStreamer. O endpoint não tem Route pública. Ao bindar um endereço diferente de localhost, exige `SHOWROOM_BENCHMARK_KEY` e autentica todas as inferências; preserve NetworkPolicy e transporte seguro na implantação.

## Comparar e repetir

Repita cada célula três vezes, alternando a ordem, depois examine percentis com o tamanho de amostra. Sem usage completo, tokens/s fica `null` em vez de estimado por caracteres. O comparador recusa diferenças em modelo, precisão, template, GPUs, topologia, cache, carga ou warmup.

```bash
python3 scripts/benchmark.py compare \
  /caminho/privado/transformers-run-1.json \
  /caminho/privado/vllm-run-1.json --kind engine \
  --output /caminho/privado/engine-comparison.json
```

Para round-robin/EPP, use `--kind routing`; o digest de vLLM também precisa ser idêntico. Execute contra o mesmo pool de backends, em etapas distintas, verificando a seleção de backend. Não execute dois conjuntos adicionais de8GPUs simultaneamente: isso ultrapassaria o teto com a GPU existente. O script mede endpoints existentes; não cria um load balancer ou altera roteamento.

## Cache e EPP

Use input longo compartilhado e sufixos novos. Compare métricas de cache por pod e TTFT contra o controle com prefixos diferentes. Uma GPU comprova reuse local; duas réplicas mais atividade real do EPP comprovam a parte de roteamento. Os nomes de métricas devem ser consultados no runtime instalado; não suponha que um gráfico vazio significa zero.

Antes do ensaio, verifique o known issue INFERENG-6962: listeners wildcard compartilhados podem desviar do Endpoint Picker. O gateway deve estar autorizado e o EPP precisa receber tráfego. Hierarchical KV offloading é Developer Preview; prefill/decode disaggregation exige uma configuração de rede/RDMA validada e não é habilitada por este benchmark. [vLLM prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/), [vLLM benchmark CLI](https://docs.vllm.ai/en/v0.23.0/cli/bench/serve/), [known issues RHOAI](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/known-issues_relnotes).

## Aceite

Exija resultados brutos, metadados confirmados, três repetições, zero falhas não explicadas e contadores de cache/EPP quando esses benefícios forem mencionados. Registre throughput absoluto e por GPU, p50/p95/p99, erros e qualidade de uma amostra. Não publique um fator de aceleração universal a partir desta carga pequena.
