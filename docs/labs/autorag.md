---
title: AutoRAG nativo
---
# Otimizar o corpus de políticas

AutoRAG é Technology Preview. Ele é distinto do pequeno aplicativo TF-IDF do showroom. O fluxo nativo requer OGX configurado com modelos de geração e embedding, um provedor pgvector/Milvus, conexão S3 e pipeline server com managed pipelines.

Os documentos estão em `data/documents/`; o conjunto de12 perguntas está em `data/eval/autorag.json`. Os document IDs são basenames exatos. Faça upload com `scripts/science.py upload` e use o bucket `aurora-data`.

Na página Gen AI studio → AutoRAG:

1. Selecione `ai-showroom` e a conexão OGX validada.
2. Selecione os quatro documentos e o JSON de avaliação.
3. Escolha Faster, quatro padrões e Answer faithfulness.
4. Use Llama MaaS validado e embedding multilíngue CPU, quando disponíveis no OGX.
5. Execute, abra leaderboard e baixe o notebook do padrão vencedor.

Faster requer4vCPU/16Gi; Better quality8vCPU/32Gi. Modelos vLLM precisam de tool calling habilitado com parser correto para a família. Não altere o modelo legado sem revisar o impacto; prefira um modelo dedicado no perfil expandido.

Aceite: quatro padrões executados, scores medidos, notebook que responde às perguntas e preserva IDs de fontes. Se OGX/embedding/vector provider ainda não estiver validado, o laboratório permanece pendente; a UI habilitada não conta como demonstração concluída.

[Pré-requisitos e configuração](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_autorag/creating-autorag-optimization-run_autorag), [parâmetros](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_autorag/autorag-configuration-parameters_autorag).
