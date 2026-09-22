# GitOps e portabilidade

O repositório versiona o estado desejado. Argo CD acompanha os componentes estáveis; execuções Ray, benchmarks, chaves e expansão cloud têm ações explícitas e evidências próprias.

## Separação de responsabilidades

| Camada | Responsável | Controle |
|---|---|---|
| ROSA, pools e GPU física | Administrador cloud | OCM/ROSA, máximos, surge, quota AWS |
| Operadores, DSC e bootstrap | Administrador plataforma | Versões fixas, patches parciais, instalação revisada |
| Serviços Aurora | Argo CD | Overlay portátil ou cluster existente |
| Credenciais | Kubernetes/gestor de segredos | Fora do Git, expiração e rotação |
| Experimentos | Participante autorizado | Job/run explícito, artifact e rollback |

## Aplicações

`gitops/argocd/project.yaml` limita repositório e namespaces. `application.yaml` usa server-side apply, self-heal e **prune desativado**. Não há finalizer de exclusão em cascata. Isso reduz o risco de remover PVCs e serviços compartilhados quando o apresentador altera um exemplo.

O controlador precisa das permissões de `gitops/bootstrap/argocd-rbac.yaml`. O label `argocd.argoproj.io/managed-by: openshift-gitops` dá acesso ao namespace de experiência; permissões em namespaces compartilhados são limitadas aos tipos necessários. Não conceda cluster-admin ao participante.

```bash
oc apply -f gitops/bootstrap/argocd-rbac.yaml
oc apply -f gitops/argocd/project.yaml
oc apply -f gitops/argocd/application.yaml
oc get application rhoai-showroom -n openshift-gitops
```

Para reusar um modelo, mude `spec.source.path` para `gitops/overlays/existing-cluster` e adapte os refs antes da sincronização. Em um fork, substitua `repoURL` e `sourceRepos`; fixe `targetRevision` em um commit de release para apresentações repetíveis.

MCP audience e os parâmetros específicos do cluster têm overlay local/gestor de configuração. A audiência TokenReview é descoberta da API daquele cluster; não reutilize a de outro ROSA. Secrets não são recursos permitidos no projeto Argo do showroom.

## Test drive de reconciliação

1. Mostre Synced/Healthy, commit e recursos pertencentes à aplicação.
2. Adicione uma anotação de demonstração a um ConfigMap próprio do showroom via commit; publique e observe a sincronização.
3. Altere temporariamente um valor não sensível gerenciado no console, sem modificar credenciais, quotas ou modelos.
4. Observe OutOfSync e self-heal. Explique que `prune: false` não remove recursos que sumiram do Git.
5. Reverta o commit do exercício para restaurar o estado documentado.

Não use upgrade de operador, remoção de namespace ou reparticionamento MIG como exercício de drift. Eles têm efeitos diferentes de uma alteração simples de configuração.

## Limites da automação

O operador GitOps não cria pools ROSA. `ResourceQuota` limita solicitações Kubernetes, não número de GPUs físicas. O guard exige inventário cloud e contabiliza nós transitórios. Mudanças globais no DSC, catálogo e ingress são tratadas por patches/merges que preservam recursos existentes, nunca por exportar todos os objetos do cluster para um repositório público.

## Publicar o guia

O guia é compilado por `mkdocs build --strict` e publicado pelo branch `gh-pages`. O modelo `ci/pages.workflow.yaml` oferece CI/CD por GitHub Actions; copie-o para `.github/workflows/pages.yaml` usando uma credencial com permissão de workflows. A publicação inicial usou Pages por branch porque a credencial disponível não tinha esse escopo. Nenhuma permissão adicional foi exigida para entregar o site.
