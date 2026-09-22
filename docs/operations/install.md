# Instalar em outro cluster

O caminho abaixo instala a experiência Aurora em um ROSA compatível. A infraestrutura, os operadores e as credenciais são pré-requisitos explícitos; o repositório não possui acesso à conta AWS de quem o clona.

## 1. Preparar plataforma

Use OpenShift AI **3.5.1**, OpenShift **4.22+** para MCP Lifecycle, NVIDIA GPU Operator, Node Feature Discovery, OpenShift Service Mesh 3, Red Hat Connectivity Link 1.4.3/MaaS, MCP Gateway Operator 0.7.1, OpenShift GitOps 1.21, Tempo e OpenTelemetry. Confirme as combinações suportadas na documentação da sua assinatura. Um cluster ROSA com GPU, sozinho, ainda não fornece esses operadores.

O [chart oficial de instalação RHOAI](https://developers.redhat.com/articles/2026/08/26/automating-red-hat-openshift-ai-installations-with-helm-and-gitops) pode estabelecer a plataforma em clusters novos. Fixe a versão `v3.5`, leia os valores e a lógica de dependências antes de usar. Em um cluster compartilhado, preserve os operadores existentes; não substitua o DSC inteiro por um exemplo.

Pré-requisitos operacionais: `oc` autenticado como administrador de instalação, Git, Python 3.12, pull-secret com acesso a `registry.redhat.io`, StorageClass padrão e saída para registries/GitHub/Hugging Face. DNS e TLS devem funcionar. Os datasets não requerem dados privados nem chaves GPT.

## 2. Clonar e verificar

```bash
git clone https://github.com/weslleyrosalem/rhoai-showroom.git
cd rhoai-showroom
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-docs.txt
# Digite o endereço do cluster que você pretende alterar, após conferir oc whoami.
export SHOWROOM_SERVER=https://api.SEUCUSTER:6443
python scripts/showroom.py preflight --expected-server "$SHOWROOM_SERVER"
```

O preflight é somente leitura. Ele confirma a versão e APIs necessárias; não atesta que há capacidade GPU livre. Para isso, execute também o [guard de capacidade](../labs/hardware.md), com inventário recente de todos os pools ROSA.

## 3. Inicializar namespace, segredos e recursos compartilhados

```bash
python scripts/showroom.py bootstrap --expected-server "$SHOWROOM_SERVER"
oc apply -k gitops/components/storage
oc rollout status deployment/showroom-s3 -n ai-showroom --timeout=180s
oc apply -k gitops/components/mlflow
oc wait mlflow/mlflow --for=condition=Available --timeout=300s
oc apply -k gitops/components/evaluation
```

O bootstrap gera credenciais aleatórias somente no Kubernetes, reaproveita os Secrets existentes e mantém cópias locais privadas do DSC/DSCI antes dos patches. O S3 de demonstração usa PVC de20Gi; MLflow usa SQLite/PVC de5Gi, uma réplica; EvalHub usa PostgreSQL/PVC de5Gi. São escolhas de showroom, sem promessa de alta disponibilidade ou recuperação de desastre.

Se o cluster já tiver MLflow ou EvalHub compartilhado, revise o storage e os clientes existentes antes de aplicar os exemplos. Os serviços são compartilhados: duplicar um singleton não isola tenants. Os patches DSC preservam os outros componentes. `mcpGuardrailsMode` precisa permanecer `false` para habilitar EvalHub junto com NeMo.

## 4. Escolher modelo e acesso

Cluster novo: use o perfil portátil e implante Qwen4B após a capacidade estar autorizada. Cluster com endpoint pré-existente: adapte os refs do overlay `existing-cluster` para seu modelo. O nome Llama desse overlay é o do ambiente de validação, não uma dependência universal.

Siga [MaaS](../labs/maas.md) para grupos, subscriptions e chave com duração limitada. Crie o Secret `ai-showroom/showroom-maas-key` com `api-key`, `base-url` terminando em `/v1`, e `model-id`. Nunca salve a chave no Git, em notebook ou screenshot.

## 5. Conectar serviços e GitOps

Siga [MCP](../labs/mcp.md) para build, audiência TokenReview, TLS Authorino e smoke test autenticado. O backend permanece privado. Não aplique o overlay público antes de confirmar anônimo negado e chamada autorizada funcionando.

```bash
oc apply -k gitops/components/guardrails
oc apply -k gitops/components/science
```

O BuildConfig RAG clona o repositório e o Workbench inicializa uma cópia. Em um fork, altere ambos os URLs, além do AppProject e Application. Para submeter o job Ray e carregar dados, siga [Ray](../labs/ray.md) e [pipelines](../labs/pipelines.md). Jobs são ações explícitas e não são recriados continuamente pelo GitOps.

Finalize a adoção declarativa com [GitOps](gitops.md), execute os [test drives](test-drive.md) e registre o resultado em sua própria matriz de validação. O hardware opcional/MIG exige mudança coordenada dos limites de pools; não é iniciado pelo overlay padrão.

## Critério de instalação concluída

Um visitante autorizado obtém resposta do modelo, fontes RAG e ferramentas MCP; um visitante não autorizado recebe negação. Experimento Ray, artefatos MLflow e avaliação têm IDs reais. Argo mostra Synced/Healthy e um pequeno drift é corrigido. Os modelos de GPU escolhidos ficam Ready e respondem. Recursos extras só recebem selo validado quando seus testes específicos passaram.
