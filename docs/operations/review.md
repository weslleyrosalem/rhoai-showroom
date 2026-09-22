# Review, rehearsal, and feedback

The acceptance process follows the customer journey: open a screen, perform a meaningful action, inspect the result, and recover from a predictable failure. API success, a Ready pod, and a usable interface are separate checks.

## Corrections found during rehearsal

| Finding | Correction | Evidence |
|---|---|---|
| Native AutoML and AutoRAG runs existed, but navigation was disabled | Enabled the installed dashboard's native preview flags | Native module lists and completed runs visible |
| Native result screens could not read the artifact store | Used the supported internal service FQDN and a targeted network rule for native UI services | AutoML model leaderboard and AutoRAG four-pattern leaderboard rendered |
| OGX migrated its storage directory away from the mounted path | Updated the persisted runtime path and rebuilt the selected index from saved parameters | Restart acceptance is recorded in the validation page |
| Shared inference route configuration selected the wrong model's endpoint picker | Isolated the additional model's inference gateway | Correct model picker selection and actual request counters verified |
| OpenShell authenticated a token without constraining its administrative subject | Added an exact-subject TokenReview gate and restricted backend reachability | Another valid service-account token denied; authorizer outage failed closed |
| A catalog entry did not automatically populate native Playground assets | Added a separate merge-based asset configuration | Native connection still requires a scoped identity and its own tool test |
| Feature Store and Playground runtimes were Ready but absent from native discovery | Added each module's required discovery label and preserved scoped backend access | Actual native screens populated after GitOps reconciliation |
| The guide gave similar visual weight to every feature | Put presentation routes first and used clear documentation hierarchy | Published desktop and keyboard navigation passed; a 390-pixel generated-site check also passed, as scoped below |
| The test drive implied that native Playground requests created the demonstrated MLflow traces | Separated Playground citation/tool inspection from Aurora application tracing | Each exercise now names its validated application path |
| A GitOps step implied that a policy edit alone rebuilt the application | Replaced it with the documented ConfigMap annotation, self-heal, and revert exercise | The script no longer depends on an unconfigured image-build trigger |
| Tempo readiness could be mistaken for demonstrated Aurora tracing | Queried its authenticated API and qualified the architecture and validation record | The six-hour search returned no traces; the demonstrated application flow uses MLflow |

These are engineering and simulated customer reviews. They are not testimonials or feedback attributed to an actual customer.

## Presenter rehearsal

Follow the [8:00 a.m. inference script](../demos/inference.md) and [10:00 a.m. MaaS script](../demos/maas.md). Use the same identity, endpoint, and browser path planned for the session. Check that keys remain valid, a request succeeds, a predictable rejection is understandable, and metrics cover the intended time window.

The acceptance record must identify the exact claim. A local prefix-cache hit does not prove distributed KV transfer. A completed evaluation with a failed benchmark is a useful finding, not a passed safety gate. A successful administrator session does not validate visitor permissions.

## Customer feedback loop

At the end of a test drive, ask the participant to explain the result in their own words and repeat one small change without presenter help. Record the task, the step where they paused, the expected result, and the observed result. Fix the smallest demonstrated problem, repeat the same task, and preserve the before/after evidence.

[Share showroom feedback](https://github.com/weslleyrosalem/rhoai-showroom/issues/new?template=demo-feedback.yml){ .md-button }

Feedback is public. Use synthetic examples and sanitized errors. Credentials, private cluster URLs, account identifiers, and customer data must stay out of the issue.

## Website acceptance

The published guide was inspected on desktop after the September 22 release. Its keyboard skip link moves focus to the content, and Tab/Enter reaches and opens the presentation action.

The same generated site artifact was also served locally inside a **390-pixel browsing context**. Home and inference pages each measured 390 pixels for both viewport and document width, with no horizontal page overflow. The drawer opened, returned to its top-level menu, and navigated to the inference presentation. Search returned the MLflow lab, and opening that result reached the expected page. Text, headings, and search results wrapped within the narrow layout.

This verifies the tested responsive layout and navigation. It does not emulate a physical phone, touch input, or every browser. The earlier browser-wide viewport override did not take effect and was reset; it was not counted as a passed test.
