---
hide:
  - toc
---

<div class="showroom-intro" markdown>
<div class="showroom-eyebrow">Technical presales · OpenShift AI 3.5.1</div>

# From a model endpoint to an AI platform.

<p class="lead">Serve a model. Put it behind a governed API. Use it in an application with data, tools, and a trace you can inspect.</p>

This showroom follows one company, Aurora Supply, across the platform. Start with a guided demonstration, take the controls, or deploy the labs in your own ROSA cluster.

[Prepare your presentation](operations/presenter.md){ .md-button .md-button--primary }
[Take the test drive](operations/test-drive.md){ .md-button }
</div>

<div class="showroom-agenda" markdown>
<section class="showroom-session" markdown>
<span class="session-time">8:00 a.m. · Inference</span>

## What makes a model service efficient?

Follow a request through vLLM and llm-d. Inspect local prefix-cache reuse and the history of a real load test. See where more replicas and distributed KV handling would change the architecture.

[Open the inference presentation →](demos/inference.md)
</section>
<section class="showroom-session" markdown>
<span class="session-time">10:00 a.m. · Models as a Service</span>

## Who can use the models, and how much?

Discover a model, use a scoped API key, reach a quota, and observe recovery. Connect the consumer experience to the platform administrator's view.

[Open the MaaS presentation →](demos/maas.md)
</section>
</div>

<section class="showroom-story" markdown>

## The customer story

> What should we replenish next week, how much, and under which policy?

Aurora Supply is a fictional distributor. Its assistant reads purchasing policies, calls inventory tools, and uses a demand forecast to prepare a proposal. A person reviews the result. No real order is placed.

The same question gives every component a job: RAG retrieves policy, MCP supplies stock, Ray produces a forecast, the LLM explains the proposal, and MaaS governs consumption. Guardrails and evaluation test defined behaviors; MLflow records experiments and traces.

<div class="showroom-path"><b>Question</b><span aria-hidden="true">→</span><b>Policy + inventory + forecast</b><span aria-hidden="true">→</span><b>Proposal</b><span aria-hidden="true">→</span><b>Human review</b></div>
</section>

## Choose the conversation

<div class="showroom-journey" markdown>
<span class="step" aria-hidden="true">01</span>
<div markdown>

### Platform engineering

Turn inference into a service that teams can discover, consume, measure, and operate. Follow serving, catalog, quotas, hardware, observability, and GitOps.
</div>
<div class="journey-link" markdown>[Explore the platform →](journeys/platform.md)</div>
</div>
<div class="showroom-journey" markdown>
<span class="step" aria-hidden="true">02</span>
<div markdown>

### Security and agents

Follow an allowed request and a denied request. Inspect tool access, policy checks, evaluations, and traces; challenge what the evidence actually proves.
</div>
<div class="journey-link" markdown>[Explore the controls →](journeys/security.md)</div>
</div>
<div class="showroom-journey" markdown>
<span class="step" aria-hidden="true">03</span>
<div markdown>

### Data science and ML engineering

Change a hypothesis, train with Ray, and compare results in MLflow. Explore the native AutoML and AutoRAG preview modules, then bring the result into the application.
</div>
<div class="journey-link" markdown>[Explore the experiments →](journeys/science.md)</div>
</div>

## Show the work behind the answer

Use the existing OpenShift AI 3.5.1 dashboards to connect requests with tokens, latency, cache reuse, replica activity, and subscription limits. The [native dashboard guide](operations/native-dashboards.md) names the exact tabs, filters, and charts to use during each presentation.

## Reproduce what you see

The repository contains manifests, notebooks, sample data, and acceptance criteria. Choose the appropriate cluster profile, provide credentials locally, and follow the installation guide. Labs identify product maturity and the tests completed in this showroom.

[Installation guide →](operations/install.md) · [Architecture →](architecture/story.md) · [Source repository →](https://github.com/weslleyrosalem/rhoai-showroom)

<div class="showroom-note" markdown>
**Before presenting:** read the [validation record](operations/validation.md). Tested behavior, resource readiness, and product support are separate. This community showroom uses synthetic data and compact services; it is not a production reference architecture.
</div>
