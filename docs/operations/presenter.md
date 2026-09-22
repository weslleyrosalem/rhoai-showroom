# Preparar a apresentação

A pergunta de abertura é: **“Como a Aurora transforma documentos, estoque e previsão em uma decisão de reposição que pode ser explicada e operada?”** Escolha uma jornada conforme a audiência e deixe a arquitetura comum visível.

## Na véspera

- Confirme [validação](validation.md), validade da chave MaaS, operadores e endpoints.
- Aqueça modelo/GPU necessários; download de pesos e escala de nós acontecem antes do cliente.
- Execute uma pergunta RAG, chamada MCP, teste de segurança, avaliação curta e previsão Ray.
- Verifique acesso do participante com identidade restrita. A sessão admin do apresentador não demonstra RBAC do visitante.
- Abra guia, OpenShift AI, MLflow, observabilidade e Argo CD. Limpe dados de entrada de ensaios que contenham informações reais.
- Tenha artefatos medidos de benchmark identificados por data/configuração. Se o laboratório ao vivo falhar, mostre o resultado anterior como resultado anterior.

## Três formas de contar

| Audiência | Começo | Clímax | Test drive |
|---|---|---|---|
| Segurança | Proposta com fontes e ferramentas | Pedido permitido, pedido bloqueado e trace explicável | Alterar prompt e inspecionar decisão |
| Plataforma | Consumidor com chave e quota | Mesmo endpoint, política diferente; nós/GPUs e métricas | Esgotar orçamento curto e restaurar |
| DS/MLE | Histórico de demanda e baseline | Ray, quality gate, MLflow e RAG usando previsão | Mudar cenário e comparar resultado |

Para20min, use o caminho principal de uma jornada. Para45min, acrescente comparação controlada e exploração no Workbench. Não tente passar por todas as telas sem uma decisão comercial comum.

## Frases que preservam precisão

“Este resultado foi medido neste hardware e workload.” “Esse recurso é Technology Preview na linha3.5.” “Duas réplicas distribuem requisições; tensor/pipeline parallel divide o trabalho de um modelo.” “O filtro de descoberta MCP não substitui autorização.” “L40S não faz MIG; o laboratório MIG requer hardware compatível.”

## Encerramento com o cliente

Entregue o link deste guia e um perfil de acesso com prazo adequado. O cliente pode repetir perguntas e labs autorizados, consultar os critérios de sucesso e instalar seu próprio fork. A página pública contém somente dados sintéticos e documentação; o acesso ao cluster continua autenticado.
