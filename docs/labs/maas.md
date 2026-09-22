# Laboratório — API, grupos e quotas

O assistente da Aurora Supply usa uma API comum. A plataforma decide quem pode chamar o modelo e quanto pode consumir. Uma AuthPolicy concede acesso; uma subscription define quota. As duas precisam estar válidas.

## Recursos deste repositório

| Recurso | Função |
|---|---|
| `showroom-platform-admins` | Grupo inicial contém apenas `aiadmin`; não cria um login |
| `showroom-data-scientists` | Grupo inicialmente vazio, a mapear para identidades existentes |
| `showroom-visitors` | Grupo inicialmente vazio para test drive |
| `showroom-model-access` | Autoriza os três grupos para o modelo curado |
| `showroom-test-drive` | 100 tokens/min, prioridade15, três grupos |
| `showroom-standard` | 20.000 tokens/h, prioridade20, administradores e cientistas |

Os objetos MaaS ficam em `models-as-a-service`. O profile público padrão aponta para `ai-showroom/aurora-qwen-4b`. O overlay `gitops/profiles/existing-cluster` aponta para o Llama existente em `maas-how-to`. Esse overlay não modifica `subplus`, sua AuthPolicy ou o modelo existente.

Pertencer ao grupo não cria usuário, senha ou papel de cluster-admin. Conceda acesso ao projeto com RBAC de escopo apropriado na fundação. Gerencie membros no Git ou no IdP de forma coerente; alterações manuais em um Group controlado por Argo podem ser reconciliadas.

## Instalação e descoberta

Aplique este módulo pelo fluxo GitOps da instalação, após revisar o diff. Para verificar sem gravar:

```bash
oc apply --dry-run=server -k gitops/profiles/existing-cluster
oc get maasauthpolicy showroom-model-access -n models-as-a-service
oc get maassubscriptions -n models-as-a-service
```

Na instalação nova, use o profile `interactive` depois do preflight de GPU. O profile `core` instala somente a configuração da plataforma; a referência ao modelo não ficará operacional até existir um backend pronto.

## Test drive

1. No dashboard, crie duas chaves de curta duração, selecionando **explicitamente** cada subscription. Em particular, `aiadmin` também pode pertencer à `subplus`, cuja prioridade é maior; aceitar a seleção automática invalidaria a demonstração da quota curta.
2. Guarde as chaves em um gerenciador de segredos ou variáveis de ambiente da sessão. Não cole em scripts, histórico de shell, documentos ou screenshots.
3. Envie uma chamada sem credencial: deve ser negada.
4. Com a chave de test drive, envie uma pergunta cujo input + output ultrapasse 100 tokens. A primeira resposta pode completar e exceder o limite; uma chamada subsequente deve retornar429. Essa quota não implica corte exato do texto no centésimo token.
5. Com a chave standard, confirme200 enquanto a test drive está limitada.
6. Aguarde a janela de um minuto e confirme a recuperação da test drive.
7. Abra Usage e confira a subscription correta. Aguarde a coleta das métricas antes de interpretar ausência temporária de dados.

Exemplo seguro de uma chamada (variáveis já definidas na sessão):

```bash
python3 - <<'PY'
import json, os, urllib.error, urllib.parse, urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
url = os.environ['SHOWROOM_GATEWAY'].rstrip('/') + '/v1/chat/completions'
parsed = urllib.parse.urlsplit(url)
if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
    raise ValueError('Use o endpoint HTTPS validado da instalação, sem credenciais na URL')
body = {'model': os.environ['SHOWROOM_MODEL'], 'max_tokens': 64,
        'messages': [{'role':'user','content':'Na empresa fictícia Aurora Supply, explique em cinco frases como a cota de tokens de um LLM governa o uso da API por equipes e por que uma requisição posterior pode receber HTTP 429.'}]}
request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
    'Content-Type':'application/json',
    'Authorization':'Bearer '+os.environ['SHOWROOM_API_KEY']})
try:
    with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
        value=json.load(response)
        print({'http_status':response.status,'usage':value.get('usage')})
except urllib.error.HTTPError as error:
    print({'http_status':error.code})
PY
```

Modelo novo: `publishers/ai-showroom/models/aurora-qwen-4b`. Backend compartilhado: `publishers/maas-how-to/models/redhataillama-31-8b-instruct`. Verifique o identificador no endpoint da instalação, sem presumir que todos os clusters têm o mesmo modelo.

## Aceite e limpeza

Registre códigos200/401/429, timestamps, subscription e usage, sem chaves. Confirme que uma identidade sem os grupos não acessa o modelo; uma demonstração apenas com `aiadmin` não comprova isolamento entre usuários. Recrie chaves depois de mudar grupos: a chave pode preservar o snapshot de grupos da emissão.

Ao terminar, revogue apenas as chaves da visita. Remova resources do showroom por seus nomes/labels quando necessário; não apague `subplus`, namespaces de operadores ou modelos compartilhados. A API instalada usa `maas.opendatahub.io/v1alpha1`; não copie exemplos antigos com outro grupo de API. [Guia MaaS](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service_maas).

## Credenciais da aplicação

No cluster de demonstração, `ai-showroom/showroom-maas-key` guarda `api-key`, `base-url` com `/v1` e `model-id`. A chave pertence explicitamente a `showroom-standard`, preservando `subplus`. A API instalada aceitou expiração `24h` e rejeitou `168h`; planeje renovação antes da demo e nunca publique a chave no Git, histórico do shell ou página. A Secret contém uma annotation de expiração, que pode ser consultada sem ler seus dados.

Os modelos Qwen usam subscriptions independentes: `aurora-qwen-4b-interactive` e `aurora-qwen-32b-benchmark`. Criar esses modelos não muda automaticamente o modelo da aplicação RAG nem a chave existente. Use uma chave emitida para a subscription correspondente.

### Renovação reproduzível

O helper abaixo valida contexto, identidade, subscription Active e modelo associado. Por padrão mostra apenas o plano; `--apply` emite uma chave24h e a coloca na Secret sem imprimi-la. Um arquivo privado existente e válido é reutilizado em retries. Para renovar, escolha um novo nome de arquivo, depois revogue a chave anterior no MaaS e reinicie o workload que lê a Secret via env.

```bash
python3 gitops/components/platform/credentials/provision_maas.py \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER" \
  --model-id publishers/maas-how-to/models/redhataillama-31-8b-instruct \
  --subscription showroom-standard \
  --key-file /caminho/privado/showroom-standard-NOVA-DATA.json
```

O diretório privado precisa de modo0700 e fica fora do repositório; o arquivo é criado0600. A API do Gateway é descoberta no cluster e não aceita redirects. Em outro cluster, use seu modelo correspondente e uma identidade existente autorizada (`--expected-user`). Não há chave estática embutida no GitOps.
