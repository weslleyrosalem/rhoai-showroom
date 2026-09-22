# Test drive

Escolha uma experiência e confirme os pré-requisitos na página do laboratório. Use o projeto `ai-showroom` e dados fictícios. O apresentador entrega uma identidade própria com os grupos necessários; não compartilhe a sessão `aiadmin` com visitantes.

## 1. Faça uma pergunta com evidências

No Playground ou na aplicação Aurora, use:

> Precisamos preparar a reposição da próxima semana. Consulte o estoque do produto AS-001, compare com a previsão e cite a política usada. Prepare somente uma proposta, sem executar uma compra.

Observe quais ferramentas foram chamadas, quais documentos sustentam a resposta e qual previsão foi usada. A resposta deve distinguir dados de estoque, previsão estatística e explicação do LLM.

**Mude uma coisa:** pergunte sobre outro SKU. Confira se a ferramenta consultou o SKU correto e se as fontes continuam relevantes. Abra a trace correspondente à nova pergunta.

## 2. Teste um limite de acesso

Siga [MCP e ferramentas](../labs/mcp.md). Faça uma consulta permitida e uma chamada sem credencial. A primeira deve funcionar; a segunda deve falhar na camada de autenticação.

Uma lista menor de ferramentas em um VirtualServer não comprova autorização. Compare descoberta e execução; o controle de acesso deve ser aplicado no caminho da chamada.

## 3. Experimente uma quota

Siga [MaaS e quotas](../labs/maas.md). Use uma chave vinculada à assinatura limitada. Observe primeira resposta, contabilização, 429 e recuperação da janela. Faça uma chamada de controle por outra assinatura.

**Mude uma coisa:** aumente o tamanho do texto em uma chamada. Observe tokens de entrada e saída. A quota conta tokens, não um número fixo de requisições.

## 4. Altere uma hipótese de treinamento

No [Workbench](../labs/workbench.md), abra o notebook Aurora. Altere um parâmetro do experimento, execute o treino pequeno e compare a métrica no conjunto de teste temporal com o baseline.

Registre parâmetros e resultados no MLflow. Não escolha um modelo somente pelo erro nos dados usados para treinar. O artefato publicado precisa indicar versão, horizonte e run de origem.

## 5. Veja uma mudança chegar por GitOps

Em uma branch do seu fork, altere uma política sintética ou um valor de demonstração. Confira o diff antes de sincronizar. Depois do sync, refaça a pergunta que depende daquele dado e verifique a versão usada.

Ao terminar, siga [restaurar o test drive](reset.md). Reverter a mudança de apresentação não deve apagar dados de experimentos, operadores ou modelos compartilhados.

## O que levar da experiência

Ao final, você deve conseguir relacionar uma pergunta a uma identidade, uma assinatura, um conjunto de fontes, ferramentas, modelo e evidência de execução. Essa cadeia é o resultado demonstrado — não apenas uma resposta convincente no chat.
