# Laboratório — capacidade, topologia e MIG

O teto do showroom é **16 GPUs físicas no total**, incluindo a GPU existente, todos os pools, máquinas em criação e sobreposição de upgrades. Quotas de Kubernetes, MIG e time-slicing contam recursos lógicos; não substituem esse controle de infraestrutura.

## Perfis

| Perfil | Infraestrutura proposta, incluindo a GPU existente | Uso |
|---|---|---|
| Core |1 L40S existente| CPU + serviços compartilhados |
| Interactive |1 existente +1 L40S =2| Qwen4B e benchmark serial de engine |
| Full L40S13 |1 existente +3 nós de4 L40S =13| Qwen4B, duas réplicas Qwen32B/TP4 e margem para outros experimentos |
| MIG9 |1 existente +1 nó de8 A100 =9| Laboratório MIG |
| MIG13 |1 existente +8 A100 +4 L40S =13| MIG e inferência em nós separados |

Esses são perfis alternativos. Manter o pool Full12 e acrescentar A1008 daria21 com a GPU existente, portanto é proibido pelo preflight. Até Full13 com surge de um nó4GPU chegaria17. Ajuste o plano de manutenção ou reduza temporariamente a capacidade; o script não esconde essa sobreposição.

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

Inclua também pools CPU com `gpus_per_node: 0`. Um tipo GPU desconhecido precisa ser adicionado à tabela de tipos após verificação oficial; não marque GPU desconhecida como CPU. `complete: true` só é legítimo depois de consultar todas as páginas da API cloud. `upgrade_surge_nodes: 0` exige confirmação da política real, não é uma sugestão para omitir capacidade de upgrade.

```bash
python3 scripts/capacity.py --profile full-l40s-13 \
  --expected-server "$EXPECTED_OPENSHIFT_SERVER" \
  --inventory /caminho/privado/rosa-inventory.json \
  --output /caminho/privado/capacity-result.json
```

A validade máxima é15 minutos. Um PASS significa somente que a contagem calculada cabe no teto; não prova quota cloud, preço ou runtime pronto. O script não cria, altera ou apaga machinepools. Prefira o autoscaling gerenciado do ROSA para nós; HPA/WVA/Ray controlam outro nível, o dos workloads. [Autoscaling ROSA HCP](https://docs.redhat.com/en/documentation/red_hat_openshift_service_on_aws/4/epub/cluster_administration/rosa-enable-cluster-autoscale-cli-interactive_after_rosa-cluster-autoscaling).

## Profiles e placement

`showroom-cpu-small` oferece CPU/RAM. `showroom-l40s-1` pede uma L40S. `showroom-l40s-4` pede quatro dispositivos para tensor parallelism. Ambos exigem o label `showroom.openshift.ai/gpu-pool=true`, além de NVIDIA-L40S. Configure esse label somente nos novos pools do showroom. Assim os novos modelos não disputam o GPU reservado para a demonstração anterior.

O profile informa RAM do host separadamente da VRAM. Criar um profile não cria um node. Confirme nodes Ready, dispositivos alocáveis, taints/tolerations, PVCs e pull-secret antes de oferecer a opção de deploy ao visitante.

O módulo `qwen-32b-multinode` cria duas réplicas, cada uma TP4, com anti-affinity obrigatória em hostnames diferentes. São dois servidores completos de um mesmo modelo. **Não** é um único modelo dividido por pipeline parallelism entre nós. Um ensaio PP2×TP4 permanece separado até validar presets, LeaderWorkerSet e transporte na instalação real.

## MIG real

L40S não suporta MIG. O profile alternativo usa A10040GB; o exemplo customizado particiona somente GPU0 em sete instâncias `1g.5gb`, mantendo os outros sete dispositivos sem MIG. A geometria não serve para A10080GB ou H100. [GPUs suportadas](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html).

Em `gitops/components/platform/mig-opt-in`, o HardwareProfile está desabilitado e o ConfigMap de geometria **não está** no kustomization. Para ativar o laboratório, siga uma janela de manutenção do **novo** nó A100: confirme `mig.capable=true`, inventário físico≤16, nenhum workload usuário no alvo, estratégia mixed revisada no GPU Operator e o ConfigMap apropriado. Após reconciliar, exija `mig.config.state=success` e o recurso `nvidia.com/mig-1g.5gb` alocável antes de habilitar o profile. MIG Manager pode reiniciar pods ou o nó. [NVIDIA GPU Operator MIG](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-mig.html).

Os labels GFD podem contar instâncias MIG, não placas físicas. Para tipos EC2 conhecidos, o preflight usa a quantidade física documentada do tipo de instância. Time-slicing continua sendo compartilhamento temporal, não isolamento de memória equivalente a MIG.

## Aceite

Registre inventário cloud, contagem antes/depois, topologia e evidência de scheduling. Nenhum recurso GPU novo deve cair no nó preservado. Um ensaio Full deve mostrar os dois pods TP4 em nós diferentes. MIG só recebe status demonstrável depois de um workload usar uma partição real. Não substitua essas evidências pelo sucesso de um `oc apply`.
