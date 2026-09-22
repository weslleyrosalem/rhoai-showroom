# Walk the platform through one business decision

Aurora Supply needs a replenishment recommendation for product **AS-001**. The inventory fixture has **45 units**, the measured Ray forecast predicts **130.26 units over seven days**, and the purchasing policy determines the approval boundary. The assistant gathers evidence and proposes an action; a person decides whether to purchase. All business data is synthetic and historical.

Use this as a route through the native dashboard. A screen earns a place in the presentation when it answers a customer question and exposes evidence the customer can inspect. The [validation record](validation.md) distinguishes browser acceptance from API tests and unresolved work.

## Start with the outcome

Open the Aurora application, ask for the AS-001 replenishment review, and inspect its sources, inventory tool, forecast, and trace. Ask the customer to change the SKU to AS-002 and explain why the recommendation changes. Then follow one of the three journeys below to inspect the platform behind the answer.

Do not equate the forecast alone with the purchase quantity: the application also applies stock, reorder point, and the 21-day coverage policy. Do not present December 2025 fixtures as current inventory.

## Platform and inference

| Native screen | Customer question and action | Evidence and interpretation |
|---|---|---|
| AI hub → Models → catalog | Which models fit this workload and hardware? Filter the curated provider and open the candidate's model card. | Inspect source, license, revision, model size, and deployment requirements. Discovery is not deployment or approval. |
| Model registry | Has this candidate passed onboarding? Open the Qwen candidate version and its metadata. | Registration records identity and provenance. Safety and performance gates remain separate decisions. |
| Model deployments | Where does inference actually run? Inspect the Ready Llama and Qwen deployment details. | GPU requests, replica count, endpoint, and runtime distinguish a deployment from a catalog card. The Qwen endpoint is private. |
| Hardware profiles | What does a team request? Open the Qwen deployment’s **Showroom L40S · 1 GPU / 48 GB** popover. | Its **Project-scoped** profile declares 4 CPU cores, 24 GiB host RAM, and one L40S per replica; 48 GB is GPU memory. Global Settings lists cluster-wide profiles. Optional four-GPU/MIG manifests are not proof of available hardware; L40S cannot provide MIG. |
| Gen AI studio → API keys | How does an application consume a model? Inspect subscription scope and expiration; issue a key only for the intended identity. | The key is a credential, not a presentation artifact. Keep it hidden. Standard, short test-drive, and sustained-load quotas have different purposes. |
| Settings → MaaS governance | How are access and consumption controlled? Read the model access and subscription policies. | Demonstrate a successful request, an intentional 429, and recovery with the documented bounded rehearsal. |
| Observe & monitor → dashboard | Is the service handling real requests? Select a time range containing the GuideLLM run. | Inspect requests, tokens, latency, errors, and GPU activity. Report the workload and observed errors; a busy GPU is not proof of comparative efficiency. |
| OpenShift GitOps | Can the setup be reproduced? Inspect the Application's source, sync state, and resource tree. | The core application converges from Git; bootstrap operators, secrets, training executions, and optional capacity have explicit workflows. |

Follow the [inference presentation](../demos/inference.md) and [MaaS presentation](../demos/maas.md) for exact commands, measured results, and recovery steps.

## Data science and machine learning

| Native screen or tab | Customer question and action | Evidence and interpretation |
|---|---|---|
| Projects → AI Showroom → Overview | What belongs to this application? Follow the workbench, pipelines, deployments, and storage links. | The same project ties the data, experiments, inference, and access model together. |
| Workbenches | Can a scientist reproduce the result? Open Aurora Lab and run a bounded notebook cell. | Use the shared dataset and the workbench's own scoped identity. The feature lookup and anonymous-denial cells produce inspectable results. |
| Feature store → Overview | Can teams share feature definitions? Open the Aurora feature project. | Read the historical timestamp and the feature contract; this is not a live warehouse feed. |
| Feature store → Entities | What identifies a row? Open `sku`. | The product key connects demand, inventory, and forecast records. |
| Feature store → Data sources | Where did these values come from? Open `aurora_historical_features`. | The source combines synthetic demand, the inventory fixture, and measured Ray forecasts. |
| Feature store → Features / Feature views | Which calculations are reused? Open `aurora_inventory`. | Inspect the five typed features, entity, timestamp, and TTL. A long demo TTL does not make old data current. |
| Feature store → Feature services | What does a consumer request? Open `aurora_replenishment_features`, then query AS-001 and AS-002 from the workbench. | The authenticated lookup is the functional test; anonymous access must fail. |
| Feature store → Datasets | Which historical snapshot was inspected? Open `aurora_replenishment_contract_2025_12_31`. | Its eight rows are a point-in-time feature-contract check with no training labels. Inspect the Parquet location, feature service, historical tag, and five feature references. |
| Develop & train → Jobs | Did the distributed work complete? Compare the RayJob and native TrainJob. | The recorded CPU TrainJob used two physical worker nodes; future placements must be checked separately. |
| Jobs → Details / Resources | What resources did training request? Inspect workers, process count, CPU, and memory. | This run requests two workers, one process and one CPU each, and 2 GiB per worker. Kueue is not enabled; queue fields are therefore empty. |
| Jobs → Pods / Logs | What did training measure? Open both workers and the rank-zero log. | Holdout MAE **0.82070**, baseline **1.33036**, 120 epochs. Native progress fields are not instrumented; the actual completed log supplies the measurements. |
| Develop & train → AutoML | Which candidate wins under this experiment's metric? Open the three-model Aurora demand run. | The full DAG and leaderboard show SeasonalNaive, RecursiveTabular, and WeightedEnsemble. The optimized score is negative MAE: closer to zero is better. |
| Gen AI studio → AutoRAG | Which retrieval configuration best answers policy questions? Open the four-pattern run. | Pattern 3 won the recorded correctness comparison, **0.8129**. Inspect other metrics and confidence intervals before choosing a deployment. |
| Pipelines → definitions / runs | How is the process repeated? Open a native AutoML or AutoRAG pipeline and its completed execution. | Parameters, graph, logs, and stored artifacts explain the result. A submitted run alone proves nothing about quality. |
| Experiments → MLflow | Can we compare and reproduce measurements? Open the Ray, native training, or explicit optimization export. | Use actual parameters, metrics, and artifacts. Automatic DSPA integration created a parent run but not complete child metrics; explicit export is identified as such. |
| Project → Cluster storage / Connections | Where do results survive a restart? Inspect persistent claims and the S3 connection metadata. | Show names, purpose, and capacity; never reveal credential values. The OGX semantic query was repeated after its restart. |
| Project → Roles / Permissions / Settings | Who may experiment or administer? Inspect the relevant group bindings. | A group is not a provisioned customer identity. Test with the intended identity rather than assuming an administrator's access is representative. |

The [Feature Store](../labs/feature-store.md), [native training](../labs/trainer.md), [AutoML](../labs/automl.md), and [AutoRAG](../labs/autorag.md) labs contain the reproducible steps and measurement limits. Their metrics use different evaluation protocols and must not be ranked against each other without a matched experiment.

## Security and agents

| Native screen or experience | Customer question and action | Evidence and interpretation |
|---|---|---|
| Projects → AI Showroom — Predictive Monitoring → Settings | Is predictive monitoring configured? Inspect **TrustyAI installed**. | The separate OVMS project avoids mixing unsupported deployment types into this monitoring namespace. |
| Predictive Monitoring → deployment → Model bias | Does changed demand change service-level outcomes? Select the named SPD and DIR metrics and inspect configuration. | Baseline0/1; promotion−0.30/0.6667. Explain the synthetic workload, group arithmetic, and distinct drift window in the [monitoring lab](../labs/model-monitoring.md). |
| AI hub → MCP servers | What can an agent do? Open the Aurora Supply server and inspect its tools. | Inventory lookup and policy retrieval support the recommendation. No purchase-execution tool is provided. |
| Gen AI studio → AI asset endpoints | Which approved assets can a builder use? Inspect models, knowledge, and MCP assets. | Catalog publication, asset discovery, authentication, and successful use are separate checks. |
| Playground → Model / Prompt | How do instructions change behavior? Ask the Aurora approval question and inspect the selected model and prompt. | The response must be useful and consistent with the application's human-approval boundary. A rendered chat box is not acceptance. |
| Playground → Knowledge | Can the answer cite policy evidence? Select the policy collection and ask about the return deadline. | Verify the actual cited source and its 30-day deadline. Do not infer retrieval merely from a plausible answer. |
| Playground → MCP | Can the model use an authorized tool? Inspect the server's tools and request inventory for AS-001. | The tool result must match the fixture. A listed server without a successful authenticated tool call is incomplete. |
| Gen AI studio → Prompts | What changed in the instructions? Compare `aurora-replenishment-review` versions 1 and 2. | `@baseline` and `@demo` show reviewable versions. The standalone prompt registry does not automatically replace the application's configured runtime prompt. |
| Develop & train → Evaluations | What was tested and why did it pass or fail? Open the named Aurora baseline and read its description before its percentage. | Attack success is a failure metric: lower is better. Inspect probe predicates, response artifacts, thresholds, and sampling limits. A DAN marker match alone does not prove harmful behavior. |
| Evaluation → metrics / artifacts / traces | Can we explain the result? Compare the metric with the actual response and detector. | Keep execution success, detector outcome, application control, and human review distinct. Missing artifacts are a validation gap. |
| MLflow traces | What happened during a recommendation? Follow retrieval, tool use, model call, and output checks. | Inspect a real trace and distinguish shared service-account attribution from individual visitor identity. |
| MLflow → Review | Can a reviewer challenge the answer before trusting it? Open **Aurora — proposal evidence review** and select **Start review**. | Two actual AS-001 traces await feedback; one contains an incorrect units-versus-currency comparison in its prose. Use **View full trace** to inspect the complete evidence, then enter a verdict and rationale. No human verdict was prefilled. See the [MLflow lab](../labs/mlflow.md). |
| Private OpenShell walkthrough | What can the agent access? Demonstrate an allowed temporary write and denied filesystem/network actions. | The tested sandbox is a private administrator-led preview. OpenShell success does not imply that NeMoClaw's unsupported external-target apply flow works. |

## Administrative screens

Use these screens to explain platform ownership rather than change settings during a customer session: cluster general settings, storage classes, workbench images, connection types, serving runtimes, catalog sources, registry settings, MCP sources, and user management. Each should point back to one deployed Aurora dependency. Do not create unused objects merely to fill a table.

The acceptance record must note which administrator pages were inspected and whether their visible names and versions match the deployed components. For options that are not supported or not configured, state the reason and show the tested alternative. Do not imply that every preview feature is production-supported.

## Rehearsal record

For each screen, record: the intended audience, exact question, action, observed content, expected content, interpretation, failure/recovery, and review date. Preserve raw private evidence outside the public repository. Publish only sanitized outcomes. A mismatch returns to the owner for correction and the same interaction is repeated before the screen is marked accepted.
