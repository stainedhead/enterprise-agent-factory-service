# Gateway contract: `afs-gateway` ↔ agents and the Agentic Teammates runtime

| | |
|---|---|
| **Status** | Contract **v1.2.0** (2026-11-25): team gateway per namespace, OpenAI-compatible model routes, Chat Completions → Converse on `bedrock`, provider switches including Bedrock, federated upstream auth (§12; [model endpoint gateway PRD](../../model-endpoint-gateway-PRD.md), approved by J; `-restapi` 1.2.0). v1.1.0 (2026-11-23): model admission by service, team, agent and price, and model delivery to the pod ([team orchestration agent PRD](../../team-orchestration-agent-PRD.md) MOD-4, MOD-5, approved by J; `-restapi` 1.1.0, not yet built). v1.0.0, draft for implementation (2026-11-21); root PRD decisions D28 and D57 |
| **Provider** | [enterprise-agent-factory-service-restapi](https://github.com/stainedhead/enterprise-agent-factory-service-restapi) (`afs-gateway`) |
| **Consumers** | Agents and pool workers in team namespaces; the Agentic Teammates runtime and its harnesses |
| **Requirements** | [Root PRD](../../enterprise-agent-factory-service-initial-PRD.md) BUD-2, BUD-3, AGT-4, SEC-6, TAG-4, IF-5; [orchestration PRD](../../team-orchestration-agent-PRD.md) MOD-1 to MOD-6; [database contract](database-contract.md) §4.2 for the spend functions |

## 1. Purpose

`afs-gateway` is the only path from an agent to Amazon Bedrock. It authenticates the calling pod,
checks the model is in the caller's effective model set (§2.1), reserves the worst-case cost against the team's budget,
forwards the call to the team's Bedrock application inference profile, settles to the actual cost and
records usage. Agents' own IAM roles never hold `bedrock:*`, so the gateway cannot be bypassed.

This contract fixes what an agent may rely on, so that standard Bedrock and Anthropic SDKs work with
**zero change to the agent's container** (SEC-6): the endpoint, a placeholder API key and the CA bundle
arrive as environment variables and files, and the gateway knows the caller from its pod, not from a
credential the SDK sends (D57).

## 2. Endpoints

Base URL: `AFS_GATEWAY_URL` (in-cluster, `https://afs-gateway.afs-system.svc:8443`, TLS with the
gateway's CA bundle mounted at `/var/run/secrets/afs/gateway/ca.crt`, see §3).

| Path | Compatible with | Streaming |
|---|---|---|
| `POST /model/{modelId}/converse` | Bedrock Runtime `Converse` | No |
| `POST /model/{modelId}/converse-stream` | Bedrock Runtime `ConverseStream` | Yes, AWS event stream (`application/vnd.amazon.eventstream`) |
| `POST /model/{modelId}/invoke` | Bedrock Runtime `InvokeModel` | No |
| `POST /model/{modelId}/invoke-with-response-stream` | Bedrock Runtime `InvokeModelWithResponseStream` | Yes, AWS event stream |
| `POST /anthropic/v1/messages` | Anthropic Messages API (`model` in the body) | Yes, server-sent events when `"stream": true` |
| `GET /healthz` | none | No |

`modelId` (or `model`) is the **AFS model id** from `ListModels`. The gateway maps it to the team's
application inference profile for that model. A model outside the caller's effective set → `403 AccessDenied` (§2.1).
Request and response bodies are passed through unchanged except that the gateway sets
`requestMetadata` (§6) and may cap `maxTokens` (§4). Unsupported Bedrock operations (for example
`ApplyGuardrail`, batch jobs) → `404 NotFound`.

### 2.1 Model admission (v1.1.0, MOD-5)

The gateway admits a call only for a model in the caller's **effective set**: service ∩ team ∩ agent (for a pool worker,
service ∩ team ∩ pool), and **callable** (it has an approved price in effect, because reservation needs a price, BUD-2):

| Level | Allowed models |
|---|---|
| Service | Every catalog model when `models.service_access = all`; else the models with `enabled` |
| Team | The service set when the team's `modelAccess = all`; else ∩ the team's selection |
| Agent or pool | The team set when its `models.access = all`; else ∩ its `modelIds` |
| Callable | A `model_prices` row in effect now |

Otherwise `403 AccessDenied` with `details.reason`, the first failed level in this order (CD-39):
`model_not_enabled_for_service`, `model_not_enabled_for_team`, `model_not_enabled_for_agent` (also used for a pool's
selection), `model_not_priced`; `details.modelId` names the model. The usage row has outcome `rejected_model` (§8). The
gateway reads the decision from `afs.model_admission(subject_kind, subject_id)` (database contract §7.3.5), caches it per
agent or pool for at most **60 s**, and drops a subject's entry on any change-feed notification for `teams`, `agents`,
`agent_pools`, `agent_models`, `pool_models`, `team_models`, `models`, `model_prices`, `team_inference_profiles` or the
`models.*` settings of its team or the service. Narrowing a level is therefore enforced within 60 s (MOD-6); widening it
(for example a newly priced model under *All*) is admitted within 60 s (US-41).

The model is forwarded to the team's application inference profile for that model. A model in the effective set whose
profile is not yet `active` (the reconciler creates it when the model becomes callable for the team) → `503 Unavailable`,
`details.reason = model_provisioning`, `Retry-After: 30`; nothing is reserved (CD-40). During the 7-day `retiring` grace a
profile is no longer used for new calls.

## 3. Caller identity and delivery to the pod

The gateway identifies the calling pod by its **source pod IP**, never by a credential the agent's SDK
sends (D57). This is what keeps standard SDKs working unchanged.

A team's orchestration agent (v1.1.0; the 1.0.1 collaboration agent) is an ordinary agent to the gateway: one pod, one agent id, its own model set, the same reservation and `402` rules. The harness and the collaboration tool (Paperclip AI or Buzz) share that pod's identity, so their calls are attributed to the orchestration agent (ORC-5, COL-4). When the team's budget is exhausted the tool keeps serving people and only model calls are refused.

| Item | Value |
|---|---|
| Identity | Source pod IP, mapped to namespace, ServiceAccount and pod (hence team, agent or pool, and worker pod) through the Kubernetes API (pod watch, cached) and Cilium endpoint identity. An IP with no current team pod → `401 Unauthenticated` |
| Anti-spoofing | Cilium network policy: only pods in team namespaces may reach the gateway; Cilium per-endpoint identity binds the IP to the pod; WireGuard transparent encryption is on between nodes, so a source IP cannot be forged on the wire |
| Ignored headers | The SigV4 `Authorization` header that AWS SDKs add, and `x-api-key` / `ANTHROPIC_API_KEY` that Anthropic SDKs send, are ignored and never logged |
| Optional token | Projected ServiceAccount token, audience `afs-gateway`, lifetime 1 hour, rotated by the kubelet, file `/var/run/secrets/afs/gateway/token` (`AFS_GATEWAY_TOKEN_FILE`), sent as `X-Afs-Gateway-Token: <token>` by runtimes that choose to. Defence in depth only: when present it is validated by TokenReview and must name the same pod as the source IP, else `401 Unauthenticated` |
| TLS | The gateway's CA bundle is mounted at `/var/run/secrets/afs/gateway/ca.crt` and named in `AWS_CA_BUNDLE`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE` and `NODE_EXTRA_CA_CERTS`, so AWS, Python, Go and Node clients trust it |
| Models (v1.1.0, MOD-4) | `AFS_DEFAULT_MODEL` (the AFS model id of the agent's or pool's default model), `AFS_MODELS` (comma-separated effective model ids, default first, then by id) and the file `/etc/afs/models.json` (read-only, mounted from a ConfigMap): `{"version": 1, "defaultModelId": "<id>", "models": [{"id": "<id>", "provider": "<provider>", "maxOutputTokens": <int>}]}`. Rendered from `afs.effective_agent_models`. Changing the agent's or pool's own `models` rolls the pod; a change at the team or service level updates the file and environment on the next roll, while the gateway enforces the new set at once (§2.1). A runtime may choose any model in `AFS_MODELS` per call; AFS enforces the set, not the choice (OR-D14). When the default model is not in the effective set, `AFS_DEFAULT_MODEL` still names it and the agent has condition `ModelUnavailable=True` |
| Environment | `AFS_GATEWAY_URL`; `AWS_ENDPOINT_URL_BEDROCK_RUNTIME` = `AFS_GATEWAY_URL`; `ANTHROPIC_BASE_URL` = `AFS_GATEWAY_URL` + `/anthropic`; `ANTHROPIC_API_KEY` = `afs-gateway` (a placeholder, not a secret, so SDKs that require a key start); `AFS_GATEWAY_TOKEN_FILE`; the four CA variables above; `AFS_TAGS` (§6) |

AWS SDKs still need credentials to sign; they find the pod's Pod Identity credentials, which have no
Bedrock permission, and the gateway ignores the signature. Whether any agent runtime needs the token
path is open question OQ-3 (needed by M3); the default is pod identity by source IP for every runtime.

## 4. Reservation math

Before forwarding, the gateway reserves the worst-case cost with
`afs.reserve_spend_held(budget_id, period_start, amount, holder)` (holder = the calling pod; returns a reservation `uuid` or NULL), after
`afs.ensure_spend_counter(budget_id, period_start)` so a new period never blocks calls (D31).

```
output_tokens_max = request maxTokens (Converse inferenceConfig.maxTokens, Anthropic max_tokens)
                    else models.max_output_tokens
input_tokens_est  = ceil(request body bytes / 3)
reserve_usd       = output_tokens_max × output price per token
                  + input_tokens_est  × input price per token
```

Prices are the model's effective `model_prices` row at the time of the call. A request whose
`maxTokens` exceeds `models.max_output_tokens` is capped to it. On completion (or stream end, client
disconnect or error) the gateway calls `afs.settle_reservation(id, budget_id, period_start, actual_usd)`,
always with the budget and period it reserved against, with the cost from the response's usage (input,
output, cache read and cache write tokens). It returns false when the hold had already been released,
and the actual cost is still added, so a call that runs past the TTL still counts. A reservation never settled (for
example a gateway crash) expires after service setting `gateway.reservation_ttl_seconds` (default 900)
and is released by the reconciler. Spend can exceed the cap only where a call's actual cost exceeds its
reserved worst case, at most one in-flight call per agent or pool worker.

The reserved worst case is always the limit the gateway forwards: when the request sends no output limit,
an unusable one, or one above the reserved cap, the gateway writes the cap into the request it forwards
(creating `inferenceConfig` when absent), so Bedrock can never produce more than was reserved. For
`InvokeModel` the limit field depends on the model family named in the model id (cross-region prefixes `us.`,
`eu.`, `apac.` and foundation-model ARNs are handled): `max_tokens` for Anthropic (`max_tokens_to_sample` for
`claude-v2*` and `claude-instant*`), Mistral and Cohere; `textGenerationConfig.maxTokenCount` for Amazon Titan
Text; `max_gen_len` for Meta. A family with no known limit field is refused with `400 ValidationError` before
any reservation or forward (use Converse for such models, for example Amazon Nova). An Anthropic Messages
request without `max_tokens` is refused with `400`, as the Messages API itself requires it.

If settlement fails after the gateway's inline attempts, it keeps the settlement in a bounded in-memory retry
queue (10,000 entries, exponential backoff from 1 s to 1 minute, 10 minutes from the first failure) and
counts it in `afs_gateway_settle_failures_total`; a settlement that cannot be retried falls back to the
reservation's expiry above. On shutdown the gateway drains in-flight HTTP calls, makes a final settle attempt
for each pending entry, then flushes usage rows.

## 5. Streaming

The gateway forwards stream events as they arrive and adds less than 25 ms (p99) to the time to first
byte. The reservation is held for the whole stream. Usage is taken from the final metadata event
(`metadata.usage` for Converse, `message_delta.usage` for Anthropic). If the client disconnects, the
gateway cancels the upstream call and settles to the tokens reported so far, or to the reservation when
none are reported.

## 6. Tags in `requestMetadata`

The gateway sets Bedrock `requestMetadata` on every call, at most **16** pairs (D27): system tags first
(`afs-team-id`, `afs-agent-id` or `afs-pool-id`), then service fixed and required tags, then team tags in
key order, until 16. Keys that do not fit are listed on the team's cost tags page (T13). Any
`requestMetadata` the agent sent is replaced. The pod also receives its tags in `/etc/afs/tags.json`
and `AFS_TAGS` (TAG-4); the gateway does not read them from the request.

## 7. Errors

Errors use the API contract's body, `{"code", "message", "requestId", "details"}`, with JSON content
type, also on streaming paths when the error happens before the first event. After the first event, an
error ends the stream with an `exception` event (Bedrock) or an `error` event (Anthropic) that carries
the same `code`.

| HTTP | `code` | When | Retry |
|---|---|---|---|
| 400 | `ValidationError` | Malformed request, unknown model id format | No |
| 401 | `Unauthenticated` | Source IP is not a current team pod (for example the team was deleted), or an optional token is invalid or names a different pod | No |
| 402 | `BudgetExceeded` | The reservation does not fit under the cap; `details` has `budgetId`, `period`, `remainingUsd` | No. Not `429`, so SDKs do not retry it |
| 403 | `AccessDenied` | Model outside the caller's effective set (`details.reason` = `model_not_enabled_for_service`, `model_not_enabled_for_team`, `model_not_enabled_for_agent` or `model_not_priced`, §2.1); team suspended (`details.reason = team_suspended`) | No |
| 404 | `NotFound` | Unsupported path or operation | No |
| 413 | `ValidationError` | Body over 20 MB | No |
| 429 | `Throttled` | Bedrock throttled the call (passed through with `Retry-After`) | Yes, with backoff |
| 502 | `UpstreamError` | Bedrock returned a server error; the reservation is released | Yes, with backoff |
| 503 | `Unavailable` | The gateway cannot reserve (database unavailable): it fails closed and forwards nothing; or (v1.1.0) the team's inference profile for the model is still being created (`details.reason = model_provisioning`, `Retry-After: 30`) | Yes, with backoff |

The reconciler's IAM explicit deny on the team's Bedrock role (BUD-3) is a backstop and is never seen
by agents, who have no Bedrock permission of their own.

## 8. Usage records

One `afs.usage_events` row per call, written in batches (at most 1 s delay). Columns as in the schema
(000001, 000011, 000012):

| Column | Meaning |
|---|---|
| `team_id`; `agent_id` or `pool_id` with `worker_pod` | Who called (pool workers carry their pod name) |
| `model_id` | AFS model id |
| `outcome` | `ok`, `error`, `rejected_budget` (`402`) or `rejected_model` (`403`; the reason is in the metric `afs_gateway_model_denials_total{reason}` and the team's log record, not in the row) |
| `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | From the response usage |
| `cost_usd` | Settled actual cost (zero for rejected calls) |
| `latency_ms` | Total latency as the gateway saw it |
| `tag_set_id` | Snapshot of the team's tags at call time (TAG-6) |
| `request_id`, `occurred_at` | For support and the five-minute activity windows |

The reserved amount lives in `afs.spend_reservations`; the operation name and gateway overhead are
metrics, not columns. Rejected calls are recorded so reports can show them (RPT-3). No prompt or
completion content is stored or logged. A usage row the writer cannot store (queue full, or a write that fails
after its retries) is dropped, logged with team, budget and amount only, and counted in
`afs_gateway_usage_rows_dropped_total{reason}` (`queue_full` or `write_failed`); reports then miss that call.

## 9. Versioning

Every response carries `X-Afs-Gateway-Contract-Version: <semver>`. New compatible paths, fields or
error codes are minor changes. Changing the authentication, the environment variable names or the error
codes of §7 is a major change and needs an ADR in the root and a transition period in which both forms
work.

## 10. Change process

1. Propose the change in this document in a `-restapi` PR labelled `contract`, with the gateway code
   and its tests.
2. Notify the Agentic Teammates project; a major change waits for its runtime release.
3. A conformance suite in `-restapi` runs the official Bedrock and Anthropic SDKs against the gateway
   with a fake Bedrock, covering every path, streaming, every error of §7 and the reservation math.

## 12. Model routes, team gateway and provider switches (v1.2.0)

Everything in §1 to §8 still holds for Bedrock and Anthropic paths. v1.2.0 adds the following; nothing an existing agent
relies on changes (G8).

### 12.1 Team gateway

When a team's `gateway_deployment` is `per_namespace`, the reconciler renders `afs-gateway` in the team namespace
(`https://afs-gateway.afs-t-<slug>.svc:8443`, two replicas) and rolls the team's agents with that value in
`AFS_GATEWAY_URL`. `AFS_GATEWAY_URL` is **opaque**: runtimes read it, never build it. Identity (§3), reservation (§4),
tags (§6) and usage rows (§8) are unchanged; the team gateway accepts calls only from its own namespace. Model routes
(§12.2) are served only by team gateways.

### 12.2 Route paths

| Path | Compatible with | Notes |
|---|---|---|
| `POST /r/{route}/v1/chat/completions` | OpenAI Chat Completions (stream with SSE) | `model` is a model listed on the route |
| `POST /r/{route}/v1/responses` | OpenAI Responses | Only when the endpoint lists `openai_responses` |
| `POST /r/{route}/v1/embeddings` | OpenAI Embeddings | Only when the endpoint lists `openai_embeddings`; reserves input only |
| `GET /r/{route}/v1/models` | OpenAI List models | Answered by the gateway from the caller's effective models on the route |
| `POST /openai/v1/chat/completions` (and `/responses`, `/embeddings`) | OpenAI, one base URL | `model` = `<route>/<model>`; routed as the path form |
| `POST /r/bedrock/v1/chat/completions` | OpenAI Chat Completions → Bedrock Converse | `model` = AFS model id; Bedrock admission (§2.1) and reservation (§4); `n` > 1, `logprobs`, audio and other unmapped fields → `400 ValidationError`, `details.reason = unsupported_parameter`, `details.field` |

`{route}` is the endpoint slug (`^[a-z][a-z0-9-]{1,30}$`). Any other path under `/r/{route}/` → `404 NotFound`. The
gateway always writes the reserved output cap into the forwarded request (`max_completion_tokens` for Chat,
`max_output_tokens` for Responses); for streams it sets `stream_options.include_usage = true` and removes the extra
usage chunk when the client did not ask for it. The agent's `Authorization` header is replaced by the route's upstream
credential and never logged.

### 12.3 Route admission

Effective routes = (switched-on service endpoints the team opted in to, plus the team's own endpoints) ∩ the agent's or
pool's selection, all on providers that are on. The gateway reads `afs.route_admission(subject_kind, subject_id)`
(database contract §7.4), cached at most 60 s and dropped on change-feed notifications for the 000023 tables.
Denials are `403 AccessDenied` with `details.reason` in this order (CD-41): `provider_disabled`,
`route_not_enabled_for_service`, `route_not_enabled_for_team`, `route_not_enabled_for_agent`, `model_not_on_route`,
`model_not_priced` (per-token routes only); `details.route` and `details.model` name them.

`provider_disabled` also applies to Bedrock paths (§2) and `/r/bedrock` while the Bedrock provider is off, ahead of the
§2.1 reasons.

### 12.4 Delivery to the pod (additions to §3)

| Item | Value |
|---|---|
| `AFS_LLM_ROUTES` | Comma-separated effective route slugs, default first |
| `AFS_LLM_<ROUTE>_BASE_URL` | `AFS_GATEWAY_URL` + `/r/<route>/v1`; `<ROUTE>` is the slug upper-cased with `-` → `_`. Includes `AFS_LLM_BEDROCK_BASE_URL` when Bedrock is on |
| `AFS_LLM_DEFAULT_ROUTE`, `AFS_LLM_DEFAULT_MODEL` | The agent's default route and model when its default is a route model |
| `AFS_DEFAULT_MODEL` | Unchanged meaning; when the default is a route model its value is `<route>/<model>` |
| `OPENAI_BASE_URL`, `OPENAI_API_KEY` | `AFS_GATEWAY_URL` + `/openai/v1` and the placeholder `afs-gateway` |
| `/etc/afs/llm-routes.json` | `{"version": 1, "defaultRoute": "<slug>", "defaultModel": "<model>", "routes": [{"route": "<slug>", "baseUrl": "<url>", "protocols": ["openai_chat", …], "models": [{"name": "<model>", "maxOutputTokens": <int>}], "pricing": "per_token\|capacity\|free"}]}` |

Same roll rules as `AFS_MODELS` (§3): the agent's own change rolls the pod; team and service changes apply on the next roll
and are enforced by the gateway at once.

### 12.5 Errors (additions to §7)

| HTTP | `code` | `details.reason` | When |
|---|---|---|---|
| 400 | `ValidationError` | `unsupported_parameter` | A field the `bedrock` translation cannot map |
| 403 | `AccessDenied` | §12.3 reasons | Route or provider admission |
| 429 | `Throttled` | `provider_budget_exhausted` | The provider's own spending limit refused the call (for example an OpenCode service-account budget) |
| 503 | `Unavailable` | `credential_missing` | The route has no credential for this team; nothing reserved |
| 503 | `Unavailable` | `federation_not_ready` | Azure or Google token exchange not set up or failing; nothing reserved |
| 503 | `Unavailable` | `provider_balance_exhausted` | The provider's prepaid balance is empty (upstream `402`); reservation released |

Upstream `429` passes through as `429 Throttled` with `Retry-After`; upstream 5xx → `502 UpstreamError`; upstream timeout →
`504 UpstreamTimeout`. In every upstream failure the reservation is released.

### 12.6 Usage rows (additions to §8)

`endpoint_id` (NULL for Bedrock), `model_name` (route model as sent), `usage_source` (`response`, `estimated`,
`provider_cost`), `reasoning_tokens`, `ttft_ms`, `upstream_ms`, `gateway_ms`, `http_status`. Calls with no usage in the
response settle to the reservation with `usage_source = estimated`. When the provider reports `usage.cost`, the settled
cost is the larger of it and the token-price cost.

### 12.7 Telemetry

Spans and metrics follow the OpenTelemetry GenAI semantic conventions plus `afs.team_id`, `afs.route`, `afs.provider`
and `afs.usage_source`; agent and pool ids are on spans only, never metric labels. No prompt or completion content is
captured. `traceparent` is continued and propagated upstream only to `corporate` and `in_namespace` endpoints.

## 11. Change log

- **v1.2.0 (2026-11-25):** team gateway per namespace and opaque `AFS_GATEWAY_URL` (§12.1); OpenAI-compatible route
  paths, body form and Chat Completions → Converse on `bedrock` (§12.2); route admission and `provider_disabled` (§12.3);
  `AFS_LLM_*`, `OPENAI_*` and `/etc/afs/llm-routes.json` (§12.4); new error reasons and `504 UpstreamTimeout` (§12.5);
  usage row columns (§12.6); GenAI telemetry (§12.7). Minor: additions only.
- **v1.1.0 (2026-11-23):** model admission by service, team, agent or pool and price (§2.1) with four `details.reason`
  values and a 60 s cache refreshed on the change feed; `AFS_DEFAULT_MODEL`, `AFS_MODELS` and `/etc/afs/models.json` (§3);
  `503 model_provisioning`; the orchestration agent replaces the collaboration agent in §3. Minor: new error reasons and
  environment variables only; nothing an existing agent relies on changes.

| # | Decision |
|---|---|
| CD-39 | Admission reasons are reported in the fixed order service, team, agent (or pool), price, so a caller sees the highest level to ask about. A pool's own selection uses `model_not_enabled_for_agent`, because the PRD names four reasons |
| CD-40 | A callable model whose team inference profile is not yet active answers `503 model_provisioning` with `Retry-After: 30` rather than calling the foundation model directly, so every call stays attributable to the team's profile and cost tags |
| CD-41 | Route admission reasons follow the model admission pattern, with the provider switch first because it is the highest level a caller can ask about |
