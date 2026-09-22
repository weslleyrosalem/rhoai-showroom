# Laboratório — capacidade, topologia e MIG

O teto do showroom é **16 GPUs físicas no total**, incluindo a GPU existente, todos os pools, máquinas em criação e sobreposição de upgrades. Quotas de Kubernetes, MIG e time-slicing contam recursos lógicos; não substituem esse controle de infraestrutura.

## Plano ativo: active-l40s-9

O plano configurado no ROSA em 22/09/2026 preserva `aiml-node` e adiciona `showroom-l40s4`. O nome do preset descreve a experiência com uma GPU preservada e até oito novas GPUs. O teto real considera também o autoscaling do pool existente.

| Pool | Tipo | Mínimo / máximo de nós | GPUs por nó | Surge de nós | Máximo físico incluindo surge |
|---|---|---|---|---|---|
| aiml-node | g6e.4xlarge | 1 / 3 | 1 | 1 | 4 |
| showroom-l40s4 | g6e.12xlarge | 0 / 2 | 4 | 1 | 12 |
| workers | m8i.2xlarge | 1 / 4 | 0 | sem impacto GPU | 0 |

**3 + 8 + 1 + 4 = 16 GPUs físicas**, com no máximo 11 fora da sobreposição de upgrades. Não aumente nenhum máximo nem adicione um pool GPU sem recalcular o conjunto. O pool novo exige IMDSv2, o label `showroom.openshift.ai/gpu-pool=true` e a taint `nvidia.com/gpu=true:NoSchedule`.

A primeira etapa executa Qwen4B/TP1 e uma única réplica Qwen32B/TP4, mantendo o Llama existente. Para comparar duas réplicas Qwen32B em dois nós de quatro GPUs, desative primeiro o Qwen4B: oito GPUs novas ocupadas pelo benchmark não deixam uma nona GPU no pool. GPU workloads ficam fora do sincronismo automático padrão do Argo até passar o preflight.

## Perfis alternativos

| Perfil | Infraestrutura nominal incluindo uma GPU existente | Uso e condição |
|---|---|---|
| Core | 1 L40S existente | CPU + serviços compartilhados |
| Interactive | 1 existente + 1 L40S = 2 | Outro cluster ou plano próprio; não adicionar automaticamente ao plano ativo |
| Full L40S13 | 1 existente + 3 nós de 4 L40S = 13 | Desenho alternativo; **não cabe no plano ativo com seus máximos e surge** |
| MIG9 | 1 existente + 1 nó de 8 A100 = 9 | Alternativa após remover/reduzir pools incompatíveis com o teto |
| MIG13 | 1 existente + 8 A100 + 4 L40S = 13 | Alternativa que também exige revisar sobreposição de upgrades |

Esses perfis não se somam. Full13 com um nó de surge de quatro GPUs chegaria a 17 mesmo com somente uma GPU existente. Um A100 de oito GPUs com surge de um nó acrescenta mais oito; manter o L40S existente já excederia 16. O preflight bloqueia esses casos até a política real de manutenção e a capacidade restante caberem no teto. Não configure surge zero fictício no inventário para obter PASS.

AWS confirma quatro L40S no `g6e.12xlarge` e oito A100 no `p4d.24xlarge`. Ainda é necessário verificar região, oferta ROSA, quota AWS, disponibilidade e o custo da conta. [G6e](https://aws.amazon.com/ec2/instance-types/g6e/), [P4](https://aws.amazon.com/ec2/instance-types/p4/).

## Preflight físico

`scripts/capacity.py` faz somente leituras. Sem inventário cloud completo e recente retorna **BLOCKED**, pois `oc get nodes` não enxerga todas as máquinas pendentes, máximos de autoscaling e surge de ROSA HCP. O inventário precisa vir da consulta atual a ROSA/OCM, com todas as machinepools do cluster.

Formato de inventário privado — valores ilustrativos, não copiar como evidência:

```json
{
  "schema_version": 1,
  "complete": true,
  "observed_at": "TIMESTAMP_UTC_DA_CONSULTA",
  "pools": [
    {
      "id": "ID_REAL_DO_POOL",
      "instance_type": "g6e.4xlarge",
      "current_nodes": 1,
      "desired_nodes": 1,
      "max_nodes": 1,
      "upgrade_surge_nodes": 0,
      "node_names": ["NOME_REAL_DO_NODE"]
    }
  ]
}
```

Inclua também pools CPU com `gpus_per_node: 0`. Um tipo GPU desconhecido precisa ser adicionado à tabela de tipos após verificação oficial; não marque GPU desconhecida como CPU. `complete: true` só é legítimo depois de consultar todas as páginas da API cloud ou todos os pools na interface OCM. Quando a interface não fornecer current/desired exatos, use `count_semantics: "upper-bound"` e conte conservadoramente cada um como o máximo do pool. O relatório mostra explicitamente esse limite, sem apresentá-lo como número de GPUs atualmente ligadas. Registre fonte e horário reais da observação; não renove um timestamp sem consultar o estado. `upgrade_surge_nodes: 0` exige confirmação da política real, não é uma sugestão para omitir capacidade de upgrade.

```bash
python3 scripts/capacity.py --profile active-l40s-9 \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER" \
  --inventory /caminho/privado/rosa-inventory.json \
  --output /caminho/privado/capacity-result.json
```

A validade máxima é15 minutos. Um PASS significa somente que a contagem calculada cabe no teto; não prova quota cloud, preço ou runtime pronto. O script não cria, altera ou apaga machinepools. Prefira o autoscaling gerenciado do ROSA para nós; HPA/WVA/Ray controlam outro nível, o dos workloads. [Autoscaling ROSA HCP](https://docs.redhat.com/en/documentation/red_hat_openshift_service_on_aws/4/epub/cluster_administration/rosa-enable-cluster-autoscale-cli-interactive_after_rosa-cluster-autoscaling).

## Profiles e placement

`showroom-cpu-small` oferece CPU/RAM. `showroom-l40s-1` pede uma L40S. `showroom-l40s-4` pede quatro dispositivos para tensor parallelism. Ambos exigem o label `showroom.openshift.ai/gpu-pool=true`, além de NVIDIA-L40S. Configure esse label somente nos novos pools do showroom. Assim os novos modelos não disputam o GPU reservado para a demonstração anterior.

O profile informa RAM do host separadamente da VRAM. Criar um profile não cria um node. No scale-from-zero, confirme que os labels exigidos pelo seletor estão presentes também no template da machinepool; um label produzido somente depois pelo GPU Feature Discovery pode impedir o autoscaler de reconhecer o pool. Confirme nodes Ready, dispositivos alocáveis, taints/tolerations, PVCs e pull-secret antes de oferecer a opção de deploy ao visitante.

O módulo `qwen-32b-multinode` cria duas réplicas, cada uma TP4, com anti-affinity obrigatória em hostnames diferentes. São dois servidores completos de um mesmo modelo. **Não** é um único modelo dividido por pipeline parallelism entre nós. Um ensaio PP2×TP4 permanece separado até validar presets, LeaderWorkerSet e transporte na instalação real.

## MIG real

L40S não suporta MIG. O profile alternativo usa A10040GB; o exemplo customizado particiona somente GPU0 em sete instâncias `1g.5gb`, mantendo os outros sete dispositivos sem MIG. A geometria não serve para A10080GB ou H100. [GPUs suportadas](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html).

Em `gitops/components/platform/mig-opt-in`, o HardwareProfile está desabilitado e o ConfigMap de geometria **não está** no kustomization. Para ativar o laboratório, siga uma janela de manutenção do **novo** nó A100: confirme `mig.capable=true`, inventário físico≤16, nenhum workload usuário no alvo, estratégia mixed revisada no GPU Operator e o ConfigMap apropriado. Após reconciliar, exija `mig.config.state=success` e o recurso `nvidia.com/mig-1g.5gb` alocável antes de habilitar o profile. MIG Manager pode reiniciar pods ou o nó. [NVIDIA GPU Operator MIG](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-mig.html).

Os labels GFD podem contar instâncias MIG, não placas físicas. Para tipos EC2 conhecidos, o preflight usa a quantidade física documentada do tipo de instância. Time-slicing continua sendo compartilhamento temporal, não isolamento de memória equivalente a MIG.

## Aceite

Registre inventário cloud, contagem antes/depois, topologia e evidência de scheduling. Nenhum recurso GPU novo deve cair no nó preservado. Um ensaio de duas réplicas deve mostrar os dois pods TP4 em nós diferentes, após liberar o Qwen4B no plano ativo. MIG só recebe status demonstrável depois de um workload usar uma partição real. Não substitua essas evidências pelo sucesso de um `oc apply`.
