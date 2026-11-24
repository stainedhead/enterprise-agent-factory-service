# PRD: Team model gateway with OpenAI-compatible model endpoints

| | |
|---|---|
| **Status** | **Proposed, for J's review (2026-11-24).** Design proposal only: nothing here is built, and no contract, schema or release changes until J approves. Release 1.1.0 is not changed by this document. Target release if approved: 1.2.0 in every repository (`-db` and `-restapi` in lockstep) |
| **Kind** | Change PRD to the [initial PRD](enterprise-agent-factory-service-initial-PRD.md) (BUD-2, BUD-3, EXT-6, RPT-7), the [team orchestration agent PRD](team-orchestration-agent-PRD.md) (model access, section 6.9) and the [gateway contract](docs/contracts/gateway-contract.md) v1.1.0 |
| **Author** | J (Enterprise Architecture), drafted with Claude |
| **Jira** | N/A |
| **Repositories** | `enterprise-agent-factory-service` (this root: PRD, contracts, design), `-db`, `-restapi` (`afs-gateway`, `afs-reconciler`, `afs-billing`, `afs-api`), `-cli`, `-website` (`@afs/sdk` and the console) |
| **Origin** | J, 2026-11-24: "What if we used a namespace scoped AI gateway that could front multiple endpoints as a proxy? Teams could then be given an env var name for the endpoint and add the name tied to the configured endpoint to help the routing. This can support any OpenAI protocol endpoint (including internal inference if they decided to run that). I wonder if that opens the door to tracking the cost of these services." |

---

## 1. Summary and recommendation

Today one shared `afs-gateway` in `afs-system` is the only route to Bedrock. It knows the caller from its pod IP,
admits only models in the caller's effective set, reserves the worst-case cost against the team budget, forwards
to the team's inference profile and settles to the actual cost. Every other model provider (OpenAI, OpenRouter, and
anything a team runs itself) is reached directly as an *external system* with the agent's own key. Those calls are
**unmetered, uncapped and switched off by default** (EXT-6, RPT-7, decision D7).

J's idea answers the question "can we track the cost of those services?" with **yes, and we can cap most of them**,
because the reason they are unmetered today is only that their traffic does not pass the gateway. Once a call goes
through a gateway that (a) holds the provider credential, (b) is the only thing allowed to reach the provider, and
(c) reads the token usage that every OpenAI-compatible server returns, it can be metered and capped with the same
reserve-and-settle math AFS already uses for Bedrock.

**Recommendation, in five decisions (details in section 12):**

1. **Run the gateway per namespace** ("team gateway"), not as one shared service with per-team routing. The decisive
   reasons are credential isolation (a team's upstream keys live only in its own namespace and IAM scope), blast radius
   (one team's load, bug or bad upstream cannot stall another team's model calls) and reach (a team's own inference
   server is in its namespace, so no cross-namespace hole is needed). The control plane stays shared: one catalog, one
   reconciler, one spend ledger. Cost: roughly two small pods per team and a connection pooler in front of RDS
   (section 5).
2. **Extend `afs-gateway`, do not adopt LiteLLM, Envoy AI Gateway, Kong or agentgateway as the enforcement point.**
   None of them does USD reserve-before-call against an external ledger, and each brings its own tenancy model (keys,
   teams, orgs) that would become a second source of truth beside AFS's role bindings and model access. The existing
   Go gateway already has identity, admission, reservation, settlement, usage rows and tag handling; adding an
   OpenAI-compatible pass-through is the smallest change (section 6). We borrow from them: LiteLLM's published price
   list as a seed for price proposals, and Envoy AI Gateway as a later option if protocol translation is wanted.
3. **Model endpoints are a catalog with the same service → team → agent narrowing** as external systems and models:
   service admins publish endpoints (and may let a team declare its own), teams narrow, agents narrow again (section 7).
4. **Each endpoint gets a route name**, a DNS-label slug such as `openai-prod` or `coder-vllm`. Agents receive one base
   URL per route as an environment variable (`AFS_LLM_OPENAI_PROD_BASE_URL`), a list (`AFS_LLM_ROUTES`) and a file
   (`/etc/afs/llm-routes.json`). Standard OpenAI SDKs work by setting the base URL; no code change (section 8).
5. **Cost and caps by pricing mode** (section 9): token-priced endpoints (OpenAI, OpenRouter, an internal platform with a
   transfer price) are metered **and hard-capped**; self-hosted capacity is metered in tokens, costed from EKS split
   cost allocation, and limited by an optional token quota rather than a USD cap.

This partly reverses D7 / EXT-6 / RPT-7: a non-Bedrock LLM reached **through a route** is metered and capped; one
reached directly as an external system stays *Unmetered*. Whether direct access stays allowed at all is open
decision MEG-OQ-5.

## 2. Problem and context

### 2.1 What teams cannot do today

- **Use a non-Bedrock model with budget safety.** A team that needs an OpenAI or OpenRouter model must get the provider
  switched on (it ships off), store its own API key as a secret, and accept that the spend is invisible to AFS reports
  and outside the team's hard cap.
- **Use internal inference.** Teams that run vLLM, SGLang, TGI or Ollama (or call a central enterprise inference
  platform) have no AFS concept for it: no catalog entry, no usage, no cost, no access rule beyond an egress FQDN.
- **See one bill.** Reports show Bedrock token cost and EKS compute; any other model spend is somewhere else.
- **Switch providers without changing code.** An agent that hard-codes a provider URL and key must be rebuilt or
  reconfigured to move to a different OpenAI-compatible backend.

### 2.2 What already exists and is reused

| Existing piece | Where | Reused for |
|---|---|---|
| Pod-IP caller identity through Cilium, optional projected token | Gateway contract §3, D57 | Same identity in the team gateway |
| Model admission service ∩ team ∩ agent (∩ pool), 60 s cache on the change feed | Gateway contract §2.1, MOD-5 | Route admission and model-on-route admission |
| `reserve_spend_held` / `settle_reservation`, TTL release, fail closed | Database contract §4.2, gateway contract §4 | Reservation for token-priced routes |
| `usage_events`, tag snapshots, reports by tag | Solution design §7.3 | Usage rows for routes, reports by route |
| `model_prices` + `model_price_proposals` with service-admin approval | BUD-9, D10 | Effective-dated endpoint prices and proposals |
| External systems catalog with default-on opt-out narrowing and team declarations | ADR-010, EXT-1..7 | The shape of the endpoint catalog |
| AFS-managed Secrets Manager paths, ESO delivery, write-only values | ADR-006, D12 | Upstream credentials, held by the gateway only |
| Reconciler-rendered Cilium FQDN egress per agent | Solution design §3.1 | Egress to providers from the team gateway only |
| EKS split cost allocation by namespace in CUR | Solution design §3.1 (`afs-billing`) | Cost of self-hosted inference and of the team gateway itself |

### 2.3 What an OpenAI-compatible server tells us

Every server of the OpenAI Chat Completions protocol returns token counts, which is what makes metering possible
without parsing prompts:

| Protocol | Usage fields | Streaming |
|---|---|---|
| Chat Completions (`POST /v1/chat/completions`) | `usage.prompt_tokens`, `usage.completion_tokens`, `usage.prompt_tokens_details.cached_tokens`, `usage.completion_tokens_details.reasoning_tokens` (already inside completion tokens) | Final chunk carries `usage` when the request sets `stream_options.include_usage = true` |
| Responses (`POST /v1/responses`) | `usage.input_tokens`, `usage.output_tokens`, `input_tokens_details.cached_tokens`, `output_tokens_details.reasoning_tokens` | `response.completed` event carries `usage` |
| Embeddings (`POST /v1/embeddings`) | `usage.prompt_tokens` | None |

vLLM, SGLang, TGI and Ollama's OpenAI-compatible endpoints return the Chat Completions `usage` object and honour
`include_usage`. OpenRouter also returns a provider-computed `usage.cost` when usage accounting is on. Facts in this
table to be rechecked against each server's current docs before the contract is written (MEG-OQ-14).

## 3. Goals and non-goals

### Goals

- G1. Agents call any configured OpenAI-compatible endpoint, external or internal, through AFS with a standard SDK and
  only a base-URL change, using a named route.
- G2. Every call through a route is metered: tokens, cost (when the route is priced), latency and outcome, per team,
  agent or pool, route and model, with tags as at call time.
- G3. Token-priced routes are covered by the team's hard cap with the same guarantee as Bedrock: spend can exceed the
  cap only by one in-flight call per pod.
- G4. Upstream credentials are never visible to agents, are stored only in Secrets Manager at AFS-managed paths, and a
  team's credentials are reachable only by that team's gateway.
- G5. Route access follows service → team → agent narrowing, defaulting the way model access does (OR-D16, OR-D17).
- G6. One team's gateway trouble does not affect any other team.
- G7. Existing agents keep working: Bedrock paths, environment variable names and error codes of gateway contract
  v1.1.0 do not change.

### Non-goals (this change)

- Hosting inference servers as an AFS resource kind (GPU node pools, model weights, autoscaling). The endpoint can
  point at a team-run server; how the team runs it is a separate PRD (MEG-OQ-13).
- Translating between protocols (OpenAI ↔ Bedrock Converse ↔ Anthropic Messages). Routes are pass-through
  (MEG-OQ-8).
- Prompt or response content inspection, guardrails, caching of completions, or semantic routing across providers.
- Fail-over between routes. An agent picks a route; AFS does not silently move its traffic.
- Metering traffic that does not pass a route (direct provider access stays *Unmetered*).

## 4. Users, roles and permissions

No new roles. New permissions mirror external systems and models.

| Action | Service admin | Team-admin | Team viewer | Agent (workload) |
|---|---|---|---|---|
| Publish, change, retire a service-level endpoint and its prices | Yes | No | No | No |
| Approve endpoint price proposals | Yes | No | No | No |
| Allow a team to declare its own endpoints (`teams.may_add_model_endpoints`) | Yes | No | No | No |
| Declare, change, delete a team endpoint (when allowed) | Yes | Yes | No | No |
| Set a team endpoint's prices or pricing mode | Yes | Yes, except a transfer price on a service endpoint | No | No |
| Narrow the team's routes (opt out of a service endpoint) | Yes | Yes | No | No |
| Narrow an agent's or pool's routes | Yes | Yes | No | No |
| Set an endpoint credential (write-only) | Yes (service), Yes (team) | Yes (team endpoints) | No | No |
| See routes, models, prices, usage and cost | Yes | Yes | Yes (no credential metadata beyond name and last rotation) | Own routes via `/etc/afs/llm-routes.json` |
| Call a route | No | No | No | Yes, within its effective set |

Permissions (proposed): `model-endpoints:read`, `model-endpoints:write` (service), `team-model-endpoints:write`,
`model-endpoint-prices:approve`. Every one gets allowed and denied tests per role in `-restapi`.

## 5. Per-namespace versus shared gateway

### 5.1 The options

- **A. Shared gateway with per-team routing.** Extend the existing `afs-gateway` in `afs-system`. One fleet holds the
  routes and credentials of every team and reaches every team's endpoints.
- **B. Per-namespace team gateway (recommended).** The reconciler renders a small gateway Deployment in each team
  namespace (`afs-gateway`, two replicas, PDB, topology spread over zones), built from the same `afs-gateway` image.
  The shared control plane (API, DB catalog, reconciler, billing) is unchanged in shape.
- **C. Shared gateway in cells** (a fleet per group of teams). Same code as A with bounded blast radius; more moving
  parts than either. Kept as the fallback if B's per-team cost turns out too high (section 5.4).

### 5.2 Comparison

| Concern | A. Shared, per-team routing | B. Per namespace (recommended) |
|---|---|---|
| **Credential isolation** | One identity that can read every team's upstream keys and assume every team's Bedrock role. A gateway compromise or a routing bug exposes all teams | Each gateway reads only `<prefix>/<namespace>/_gateway/*` and assumes only its own team's Bedrock role, by IAM ABAC on `afs-team-id` and namespace. A compromise is one team |
| **Network isolation** | Needs egress to every provider for every team, and an **ingress hole into every namespace** that runs its own inference server, breaking "no cross-namespace traffic" (section 4 of the solution design) | Agent → gateway → in-namespace inference stays inside the namespace. Egress FQDNs are only the team's own routes. The existing agent → `afs-system` exception goes away once Bedrock moves too |
| **Blast radius** | One hot team (large streams, slow upstream, retry storm) consumes shared connections, memory and file descriptors; a bad release breaks every team at once | Load, crashes and upstream slowness stay in one team. Releases roll by ring (canary teams first), and a bad image stops at the first ring |
| **Noisy neighbour / fairness** | Needs per-team concurrency limits and queues inside the gateway | Kubernetes resource limits per gateway; the team's `ResourceQuota` covers it |
| **Cost attribution of the gateway itself** | Platform overhead, shared | Lands on the team through EKS split cost allocation by namespace, like any team pod (honest showback) |
| **Footprint** | 3–6 pods total | About 2 pods per team (request ~50m CPU, 96 MiB each; Go binary). 300 teams ≈ 600 pods ≈ 30 vCPU requested |
| **Database connections** | Few pools | Many small pools: 600 pods × 4 connections ≈ 2,400. Needs RDS Proxy (or PgBouncer in transaction mode) in front of the spend functions, or the Redis/Valkey spend counter already planned for scale (solution design §3.1) |
| **Operations** | One Deployment to upgrade, watch and scale | One image and one setting (`gateway.image`), rolled by the reconciler; version skew across teams for up to one ring interval; per-team dashboards come from the same metrics with a `namespace` label |
| **Caller identity** | Pod IP → any namespace | Pod IP → its own namespace only; a caller from another namespace is refused by network policy before it reaches the gateway |
| **Change from today** | Small | Medium: reconciler renders new objects, `AFS_GATEWAY_URL` value changes per team (name unchanged), migration window with both gateways (section 11) |

### 5.3 Why B

The new thing a multi-endpoint gateway holds is **team-supplied credentials and reach into team-run services**. AFS
isolates teams by namespace and IAM ABAC everywhere else (secrets, roles, volumes, logs, inference profiles); a shared
component that holds every team's keys would be the one place where that isolation collapses into a single process.
Option B keeps the tenant boundary where it already is, and it also makes the gateway's own cost visible per team.

### 5.4 Risks of B and their mitigations

- **Gateway runs on team nodes, beside agent pods.** An agent container escape on that node could read that gateway's
  credentials; they are only that team's, and the team's own agents already run there. Teams on the dedicated
  NodePool tier keep that isolation. The gateway runs as non-root, read-only root filesystem, `restricted` PSA, its
  own ServiceAccount; agents have no Kubernetes RBAC, so they cannot read its Secret or exec into it.
- **Teams cannot tamper with it.** Admission policy already stops teams creating workloads; it is extended so only the
  reconciler may create or change objects labelled `afs.io/component=gateway`, and so no other pod may use the
  `afs-gateway` ServiceAccount.
- **Connection count.** RDS Proxy is required for B (MEG-OQ-15 covers whether to go straight to Valkey counters).
- **Footprint at very large team counts.** If the per-team overhead is unacceptable, option C (cells) uses the same
  code and routing tables; the data model in section 7 does not change.

## 6. Build on `afs-gateway` or adopt an off-the-shelf gateway

Assessed 2026-11-24 from vendor documentation; versions and licence boundaries move quickly and are to be rechecked
before implementation (MEG-OQ-14).

| Product | Strengths | Gaps against AFS's needs |
|---|---|---|
| **LiteLLM proxy** (Python, MIT core + enterprise licence) | 100+ providers, OpenAI-compatible front door, per-key / team / org spend tracking in its own Postgres, budgets per team and key, a widely used model price list (`model_prices_and_context_window.json`) | Budgets are checked against recorded spend before a call, not reserved, so concurrent calls can overshoot by more than one call per pod. Tenancy is its own keys, users, teams and orgs: a second source of truth beside AFS role bindings. SSO, audit logs, org admins, tag budgets and per-team logging are in the enterprise licence. Python runtime and its own database to operate |
| **Envoy AI Gateway** (Envoy Gateway + CRDs `AIGatewayRoute`, `AIServiceBackend`, `BackendSecurityPolicy`) | Kubernetes-native Gateway API, strong data plane, OpenAI ↔ Bedrock / Azure translation, token counts as `llmRequestCosts` (including CEL expressions) feeding Envoy's global rate limit | Limits are token rate limits counted after the response, so the call that crosses the limit is admitted; no USD price table or effective-dated prices; no link to an external spend ledger. Good candidate for a later translation layer (MEG-OQ-8) |
| **Kong AI Gateway** (AI Proxy plugins) | Mature API gateway, multi-provider proxying, token metrics | Advanced AI rate limiting and several features are Kong Enterprise; tenancy and budgets are Kong consumers and plugins, not AFS's model |
| **agentgateway** (Linux Foundation, Rust) | Fast, MCP and A2A aware, OpenTelemetry token metrics (`gen_ai.usage.*`) | Does not compute dollar cost (price math is left to PromQL); budgets are token rate limits |
| **Portkey, Bifrost and similar** | Feature-rich hosted or self-hosted routers with budgets | Same structural gap: their own tenancy and post-hoc budgets; SaaS variants send traffic outside the account |

**Verdict.** What AFS must guarantee (identity by pod, three-level admission refreshed in 60 s, USD reservation in
the AFS ledger, fail closed, tag snapshots, audit) is exactly the part none of these products owns, while the part
they do best (many provider dialects) is not needed for pass-through OpenAI-compatible routes. Extending
`afs-gateway` keeps one enforcement implementation for Bedrock and routes. The usecase layer already separates
reserve → invoke → settle from the Bedrock adapter (`internal/usecase/gateway`, `Service.Do` with an `InvokeFunc`), so
the new work is an OpenAI-protocol adapter, route resolution, upstream auth and usage parsing.

**What we borrow.** LiteLLM's price list as one input to endpoint price proposals (it is data, MIT licensed; a
service admin still approves every price). Envoy AI Gateway, if translation is ever in scope, as a data plane *behind*
`afs-gateway`, never as the budget enforcer.

## 7. Endpoint catalog

### 7.1 Concepts

- **Model endpoint**: one configured upstream that speaks a protocol, at a base URL, with an auth method, a
  credential and a pricing mode. Service level (`team_id` NULL) or team level.
- **Route**: the name agents use for an endpoint. One route per endpoint; the route slug is the endpoint's slug.
- **Route model**: a model name the endpoint serves through the route, with its own output limit and prices.
- **Bedrock** stays as it is. It appears in route listings as the built-in route `bedrock` (read-only) so screens and
  reports can show all model spend in one list, but its catalog remains `models` and its paths remain the
  gateway contract §2 paths.

### 7.2 Narrowing (service → team → agent)

| Level | Rule |
|---|---|
| Service | A service endpoint is `enabled` or not. Off means off for every team. New service endpoints ship **off** |
| Team | Service endpoints reach a team by the team's `routeAccess`: `all` (every enabled service endpoint, live rule, as with models) or `selected` (a list). Only service admins narrow a team's service routes (same rule as team model lists, OR-D16). A team with `may_add_model_endpoints` declares its own endpoints, which are always part of its set |
| Agent or pool | `routes.access` `all` (the team set) or `selected`, set by team-admins, like `models.access` |
| Model on route | The model is listed on the endpoint and is callable: it has a price in force on a `per_token` route, or the route is `capacity` / `free` (section 9) |
| Terms | An endpoint flagged `requires_terms` (a provider with its own contract) never joins *All* automatically; it must be selected at the team level by a service admin (mirrors OR-D17) |

Effective set = service ∩ team ∩ agent (∩ pool), plus the team's own endpoints ∩ agent. The gateway reads it from a
new `afs.route_admission(subject_kind, subject_id)` with the same 60 s cache and change-feed invalidation as model
admission. Denials use `403 AccessDenied` with `details.reason` in fixed order: `route_not_enabled_for_service`,
`route_not_enabled_for_team`, `route_not_enabled_for_agent`, `model_not_on_route`, `model_not_priced`.

### 7.3 Data model (proposed `-db` migration 000023)

All tables in schema `afs`, team-scoped tables with `team_id`, composite foreign keys, RLS through
`afs.caller_sees_team`, desired-state columns (`version`, `created_at/by`, `updated_at`, revision trigger).

| Table | Key columns | Notes |
|---|---|---|
| `model_endpoints` | `id` (`mep_…`), `team_id` (NULL = service), `slug` (route name, `^[a-z][a-z0-9-]{1,30}$`, unique across the service and each team; a team cannot reuse a service slug; `bedrock` reserved), `display_name`, `description`, `owner`, `purpose` (required for team endpoints), `protocol` (`openai_chat` in 1.2.0; `openai_responses`, `openai_embeddings` allowed as additional paths), `location` (`external` internet FQDN, `corporate` host on the corporate network, `in_namespace` a Service name in the team namespace; `in_namespace` only for team endpoints), `base_url` (https except `in_namespace`, which may be http inside WireGuard, recorded like PC-D7), `ca_bundle` (optional PEM, not a secret), `auth_kind` (`none`, `bearer`, `header` with `auth_header`), `credential_mode` (`shared` one credential, `per_team` one per team for service endpoints), `pricing_mode` (`per_token`, `capacity`, `free`), `requires_terms`, `enabled`, `timeout_seconds`, `max_body_mib` | No credential value, only metadata. `external_system_id` optional link to the external systems catalog entry of the same provider, used for direct-access policy (MEG-OQ-5) |
| `endpoint_models` | `(endpoint_id, model_name)`, `max_output_tokens`, `context_tokens`, `enabled` | `model_name` is what the client sends in `model`; free text, validated as printable ≤ 200 chars |
| `endpoint_model_prices` | `(endpoint_id, model_name, effective_from)`, `input_per_mtok_usd`, `output_per_mtok_usd`, `cached_input_per_mtok_usd`, `request_fee_usd` (optional per-call fee), `source` (`manual`, `price_list`, `transfer`) | `numeric`, USD. Effective-dated like `model_prices` |
| `endpoint_price_proposals` | as `model_price_proposals` | From LiteLLM's list or a provider's published prices; approved by a service admin |
| `endpoint_credentials` | `(endpoint_id, team_id NULL)`, `secret_arn`, `rotated_at`, `status` | ARN at the managed path of section 10; `team_id` set for `per_team` and team endpoints |
| `team_model_endpoints` | `(team_id, endpoint_id)` | Selection rows when `teams.route_access = selected` |
| `agent_model_endpoints`, `pool_model_endpoints` | `(team_id, agent_id\|pool_id, endpoint_id)` | Selection rows when the agent's or pool's `route_access = selected` |
| `endpoint_capacity_costs` | `(endpoint_id, team_id, effective_from)`, `monthly_usd` or `hourly_usd`, `allocation` (`by_tokens`, `by_agent`) | Optional, for `capacity` routes not costed by CUR (section 9.3) |
| `token_quotas` | `(team_id, endpoint_id NULL, period)`, `max_tokens`, counters as `spend_counters` | Optional non-USD cap (MEG-OQ-7) |

Column additions: `teams.route_access`, `teams.may_add_model_endpoints` (service-admin only, guarded like
`may_add_external_systems`); `agents.route_access`, `agent_pools.route_access`; `usage_events.endpoint_id` (NULL for
Bedrock), `usage_events.model_name` (text, for route calls, since `model_id` is an FK to Bedrock `models`),
`usage_events.usage_source` (`response`, `estimated`, `provider_cost`), `usage_events.reasoning_tokens`;
`cost_daily.source` gains `route` and `route_capacity`. View `effective_agent_routes` (security invoker), like
`effective_agent_models`. All on online-safe terms (nullable columns, `usage_events` is partitioned; lock impact noted
in the migration header).

## 8. Route names and delivery to agents

### 8.1 URLs

The team gateway is `https://afs-gateway.afs-t-<slug>.svc:8443` (one Service per namespace, certificate from the AFS
internal CA, so the CA bundle and its four environment variables do not change). Two equivalent ways to pick a route:

| Form | Example | For |
|---|---|---|
| Route in the path (primary) | `POST ${AFS_GATEWAY_URL}/r/openai-prod/v1/chat/completions` with `"model": "gpt-4.1"` | Any OpenAI SDK: set `base_url` to the route's base URL. Zero code change |
| Route in the model (convenience) | `POST ${AFS_GATEWAY_URL}/openai/v1/chat/completions` with `"model": "openai-prod/gpt-4.1"` | Runtimes that keep one client and switch models per call (Hermes, LiteLLM-style clients) |

Supported paths per route: `POST /v1/chat/completions`, `POST /v1/responses` and `POST /v1/embeddings` when the
endpoint declares them, and `GET /v1/models` answered **by the gateway** from the agent's effective route models (never
forwarded). Anything else on a route → `404 NotFound`. The gateway strips the client's `Authorization`, sets the
upstream credential, and adds `X-Afs-Request-Id`.

### 8.2 Environment and files (zero change to the container, D12)

| Variable or file | Value |
|---|---|
| `AFS_GATEWAY_URL` | Unchanged name; value becomes the team gateway URL after migration |
| `AFS_LLM_ROUTES` | Comma-separated effective routes, default first, then by slug, e.g. `openai-prod,coder-vllm` |
| `AFS_LLM_<ROUTE>_BASE_URL` | Per route, slug upper-snake: `AFS_LLM_OPENAI_PROD_BASE_URL=${AFS_GATEWAY_URL}/r/openai-prod/v1` |
| `AFS_LLM_DEFAULT_ROUTE`, `AFS_LLM_DEFAULT_MODEL` | Optional default route and model for the agent (set on the agent's model access screen) |
| `OPENAI_BASE_URL` | The default route's base URL, when the agent has a default OpenAI-protocol route and does not set `OPENAI_BASE_URL` itself as a config value |
| `OPENAI_API_KEY` | `afs-gateway` placeholder (like `ANTHROPIC_API_KEY`), only when `OPENAI_BASE_URL` is set by AFS |
| `/etc/afs/llm-routes.json` | `{"version":1,"defaultRoute":"openai-prod","routes":[{"name":"openai-prod","protocol":"openai_chat","baseUrl":"…","paths":["chat/completions","responses"],"models":[{"name":"gpt-4.1","maxOutputTokens":32768,"metered":true,"capped":true}]}]}` |

Rendered by the reconciler into the agent's ConfigMap from `effective_agent_routes`. A change to the agent's own route
access rolls the pod; team and service changes update the file and environment on the next roll, while the gateway
enforces at once (same rule as gateway contract §3 for models). A route name that would collide with an existing
config value name is refused at create time.

## 9. Cost tracking and hard caps

### 9.1 Pricing modes

| Mode | Use for | Metered | USD cost per call | Hard cap |
|---|---|---|---|---|
| `per_token` | OpenAI, OpenRouter, Azure OpenAI, any priced provider; an internal platform with a **transfer price** set by service admins | Yes | From `endpoint_model_prices` (+ optional request fee) | **Yes**, reserve and settle against the team budget |
| `capacity` | Self-hosted inference whose cost is the hardware (team GPU nodes, a reserved cluster) | Yes, tokens | Zero per call; cost comes from CUR (EKS split cost by namespace) or `endpoint_capacity_costs`, allocated daily | No USD cap; optional token quota |
| `free` | Internal services charged elsewhere, evaluation endpoints | Yes, tokens | Zero | Optional token quota |

### 9.2 Reservation and settlement on `per_token` routes

The Bedrock math (gateway contract §4) applies with OpenAI field names:

```
output_tokens_max = max_completion_tokens, else max_tokens (Chat); max_output_tokens (Responses);
                    else endpoint_models.max_output_tokens; capped to it either way
input_tokens_est  = ceil(request body bytes / 3)
reserve_usd       = output_tokens_max × output price + input_tokens_est × input price + request_fee_usd
actual_usd        = (prompt − cached) × input + cached × cached-input price + completion × output + request_fee_usd
```

- The gateway always forwards the reserved cap (writing `max_completion_tokens` for Chat, `max_output_tokens` for
  Responses), so the upstream cannot produce more than was reserved. Reasoning tokens are inside completion tokens, so
  the cap covers them.
- For streams, the gateway sets `stream_options.include_usage = true` and reads the final usage chunk. When the client
  did not ask for it, the gateway removes that extra chunk before it reaches the client (MEG-OQ-9).
- No usage in the response (a server that omits it, a cut stream): settle to the reservation and mark
  `usage_source = estimated`. Conservative by design: the team is never under-charged for a call AFS could not measure.
- When OpenRouter (or another provider) returns its own `usage.cost`, the gateway settles to the larger of that cost and
  the token-price cost, and records both, so a provider-side fee we did not model still counts.
- Embeddings reserve input only.
- **What the cap cannot see:** provider-side tool fees not reported in usage (for example hosted web search billed per
  call), batch APIs, fine-tuning and file storage. Routes do not proxy those paths (404), and the daily reconciliation
  (section 9.4) flags any residual variance.

The guarantee is the same as Bedrock: spend exceeds the cap only where a call's actual cost exceeds its reserved worst
case, at most one in-flight call per pod. It holds **only if agents cannot reach the provider another way** (section
9.5).

### 9.3 Self-hosted inference cost

- **In the team namespace** (`in_namespace`): GPU nodes and pods already land on the team in CUR through EKS split
  cost allocation by namespace, as `eks_compute`. Reports add the route's token totals beside that cost and derive an
  effective $/1M tokens for the period, which lets teams compare self-hosting with a priced provider honestly.
- **On a corporate or central platform** (`corporate`): either a transfer price (`per_token`, capped) set by service
  admins from the platform's chargeback rate, or `capacity` with a monthly or hourly amount in
  `endpoint_capacity_costs`, allocated to agents by token share each day.
- Token quotas (`token_quotas`) give `capacity` and `free` routes a hard limit that is not money: reserve output-token
  worst case, settle actual, refuse with `429 QuotaExceeded` (not `402`, because no money is involved; MEG-OQ-7).

### 9.4 Reconciliation against the provider's bill

CUR reconciles Bedrock. For external providers, `afs-billing` gains an optional daily pull per endpoint with an admin
credential: OpenAI's organization usage and costs API (per project) and OpenRouter's key usage; other providers
(for example Azure OpenAI) are out of scope for 1.2.0. Attribution is clean when the endpoint uses `credential_mode = per_team` with one
provider project or key per team, so the provider's own invoice splits by team. Variance over
`billing.variance_alert_pct` raises the same `cost.variance_detected` event (MEG-OQ-11).

### 9.5 Closing the bypass

Metering a route is only meaningful if the same provider is not also reachable directly:

- The upstream host of a route is in the **team gateway's** egress policy only. An agent's egress policy never includes
  a route's host.
- If the provider is also on in the external systems catalog for that agent (category `llm`), the agent can still call
  it with its own key, unmetered. Proposed rule: an `llm` external system linked to an endpoint (`external_system_id`)
  is not grantable to agents while the route exists, and the console says to use the route. Whether to allow an
  explicit unmetered override is MEG-OQ-5.
- Agents never receive the upstream credential, so a key cannot leak into an agent's own code path.

### 9.6 Reports

Usage, cost and activity reports gain `groupBy=route` and a `route` filter; the Bedrock model reports become
"model spend" across Bedrock and routes, with a *Metered* / *Capped* / *Quota* badge per route. Routes in `capacity`
mode show tokens, allocated cost and effective $/1M tokens. RPT-7 changes from "non-Bedrock LLMs are unmetered" to
"non-Bedrock LLMs reached directly are unmetered".

## 10. Credentials (Secrets Manager and ESO)

| Credential | Secrets Manager name (AFS-managed, ADR-006) | Who reads it |
|---|---|---|
| Team endpoint | `<prefix>/<namespace>/_gateway/<route>` | That team's gateway only |
| Service endpoint, `per_team` | `<prefix>/<namespace>/_gateway/<route>` (created when the team gains the route; a service admin or team-admin sets the value) | That team's gateway only |
| Service endpoint, `shared` | `<prefix>/_service/gateway/<route>` | Projected into each namespace that has the route; read only by those gateways |
| Provider admin key for reconciliation | `<prefix>/_service/billing/<route>` | `afs-billing` only |

- `_gateway` is a new reserved scope beside `_shared`. Agent roles' IAM policies already match only their own path and
  `_shared`, so they cannot read `_gateway`; the team gateway's role matches only `_gateway/*` of its own namespace,
  with `afs-team-id` as the second check.
- The reconciler renders one ExternalSecret per namespace (`afs-gateway-routes`) that projects the gateway's
  credentials into a Kubernetes Secret mounted **only** into the gateway pod as files. The gateway watches the files and
  picks up a rotation without a restart (ESO refresh interval 1 minute). Agents have no Kubernetes RBAC and do not mount
  it.
- For `shared` service credentials, the projected Secret exists in every namespace that has the route. That is the
  accepted cost of a shared key (etcd encryption with the environment's KMS key); `per_team` is the recommended default
  because it also gives per-team revocation and provider-side attribution (MEG-OQ-3).
- Values are write-only through the API (`PutModelEndpointCredential`, `RotateModelEndpointCredential`), never stored
  in the database, never returned, never logged; the gateway redacts upstream auth headers in debug logs.
- An endpoint with `auth_kind = none` (typical for an in-namespace vLLM) needs no secret; network policy is its guard.

## 11. Impact by layer

### 11.1 Gateway contract (v1.2.0, minor)

New paths (§8.1), route admission reasons, `429 QuotaExceeded`, `AFS_LLM_*` variables and `/etc/afs/llm-routes.json`.
`AFS_GATEWAY_URL` keeps its name; its value is documented as opaque (it was already only consumed as a variable), so
moving it to the team gateway is not a major change. Bedrock paths, error codes and identity rules are unchanged.

### 11.2 `-db` (000023, release 1.2.0)

Tables and columns of section 7.3, `afs.route_admission`, `effective_agent_routes`, the `_gateway` secret path in
`afs.secret_path`, change-feed triggers on the new tables, RLS and grants (`afs_gateway` reads its team's rows only;
from B, the per-namespace gateway connects as `afs_gateway` with `SET LOCAL afs.team_ids` to its team), isolation
tests and `seedOtherTeams` rows for every new team-owned table.

### 11.3 `-restapi`

- `afs-gateway`: OpenAI-protocol adapter (Chat, Responses, Embeddings, SSE streaming), route resolution, upstream auth
  from files, usage parsing per §9.2, `GET /v1/models`, route admission cache, a mode flag so the same binary runs as
  the shared gateway or a team gateway (`--team-namespace`).
- `afs-reconciler`: renders the team gateway (Deployment, Service, PDB, certificate, ServiceAccount and Pod Identity to
  the team's Bedrock role, ExternalSecret, CiliumNetworkPolicy egress to route hosts and in-namespace Services, ingress
  from the team's agents only), route ConfigMap content per agent, ring-based gateway image rollout, credential
  secrets at create time.
- `afs-billing`: endpoint price proposals from LiteLLM's list and provider pages; optional provider cost pulls;
  capacity allocation; reports by route.
- `afs-api`: about 16 operations (contract v1.5.0): `ListModelEndpoints`, `GetModelEndpoint`, `CreateModelEndpoint`,
  `UpdateModelEndpoint`, `DeleteModelEndpoint` (service and team scope), `PutEndpointModels`,
  `PutEndpointModelPrice`, `List/Approve/RejectEndpointPriceProposal`, `PutModelEndpointCredential`,
  `RotateModelEndpointCredential`, `PutTeamRouteAccess`, agent and pool `routes` in the existing model access body,
  `PutTokenQuota`, plus report parameters. Each mutation writes audit and outbox (`model_endpoint.*` events).

### 11.4 `-website`

- SDK regenerated from the contract.
- Console, service admin: **Model endpoints** page beside *Models* (catalog table with protocol, location, pricing
  mode, Metered / Capped badges, enabled switch), create wizard with review step and the equivalent `afs` command,
  prices and proposals tabs, credential tab (write-only).
- Team-admin: **Model endpoints** under the team (service routes with opt-out state, team endpoints when allowed),
  agent configuration's *Model access* tab gains *Routes* (all or selected, default route and model) and shows the
  env var names an agent will receive.
- Reports: route group-by and badges; *Unmetered* badge kept only for direct `llm` external systems.
- New mockups are needed (`docs/ui/46-…`), to be drawn once J approves the direction.

### 11.5 `-cli`

New service `model-endpoints` (`list-model-endpoints`, `describe-model-endpoint`, `create-model-endpoint`,
`update-model-endpoint`, `delete-model-endpoint`, `put-endpoint-models`, `put-endpoint-model-price`,
`list-endpoint-price-proposals`, `approve-endpoint-price-proposal`, `put-model-endpoint-credential` with value from
file, stdin or prompt only, `rotate-model-endpoint-credential`), `teams put-team-route-access`, route options on
`agents update-agent-models`, `budgets put-token-quota`; one command per operation, goldens and AccessDenied tests.

### 11.6 Migration from the shared gateway

1. Ship the team gateway behind `gateway.deployment = shared | per_namespace` (default `shared`).
2. Turn on per namespace for canary teams: the reconciler creates the team gateway, then rolls agents with the new
   `AFS_GATEWAY_URL`. The shared gateway keeps serving pods not yet rolled; both write the same ledger.
3. Ring by ring until every team is moved; then the shared gateway's Bedrock role trust is removed and its Deployment
   scaled to zero. Rollback per team is the reverse (flip the team back and roll agents).
4. Routes are offered only on teams with a team gateway (they need the namespace-scoped credentials).

## 12. Decisions, risks and open questions

### 12.1 Proposed decisions (Claude, for J's review)

| # | Decision | Why |
|---|---|---|
| MEG-D1 | Per-namespace team gateway; shared control plane | Credential and network isolation stay at the namespace and IAM boundary; one team's failure stays in that team (§5) |
| MEG-D2 | Extend `afs-gateway`; borrow price data from LiteLLM; Envoy AI Gateway only as a possible translation layer later | Only AFS's gateway reserves USD in AFS's ledger and uses AFS's tenancy (§6) |
| MEG-D3 | Endpoints are a service → team → agent catalog with model-access semantics (`all` live rule, service admins narrow teams, `requires_terms` never joins *All*) | Same mental model as models and external systems (OR-D16, OR-D17, ADR-010) |
| MEG-D4 | Route = endpoint slug; path form `/r/<route>/v1` is primary, `<route>/<model>` in the body is supported | Zero-change SDK use and one-client runtimes both work |
| MEG-D5 | Pricing modes `per_token` (capped), `capacity` (CUR or allocated, quota optional), `free` | Hard caps only where a per-call price is meaningful |
| MEG-D6 | No usage in a response settles to the reservation | Never under-count spend the gateway could not measure |
| MEG-D7 | Upstream credentials at `<prefix>/<namespace>/_gateway/<route>`, gateway-only; `per_team` default for service endpoints | Isolation, revocation and provider-side attribution per team |
| MEG-D8 | Route hosts are reachable from the team gateway only | Without this, caps are advisory |
| MEG-D9 | Pass-through only in 1.2.0; no protocol translation, fail-over or content inspection | Keep the first release small and the cap guarantee simple |

### 12.2 Risks

| Risk | Mitigation |
|---|---|
| Per-team gateway footprint and RDS connections at hundreds of teams | Small Go pods; RDS Proxy; Valkey counters; option C cells keep the same model |
| Providers that omit usage or bill outside tokens | Settle to reservation; refuse unknown paths; daily provider reconciliation and variance alerts |
| A team re-opens direct provider egress to avoid caps | `llm` systems linked to a route are not grantable to agents (MEG-OQ-5); denied attempts already appear in traffic reports |
| OpenAI-compatible servers differ in small ways (field names, `include_usage` support) | Conformance suite in `-restapi` against the OpenAI SDK and recorded vLLM, SGLang, Ollama and OpenRouter fixtures |
| Version skew during ring rollout | `X-Afs-Gateway-Contract-Version`; minor-only changes inside a release |
| Price data from third-party lists is wrong | Proposals only; a service admin approves every price |

### 12.3 Open questions for J

| # | Question | Recommended answer |
|---|---|---|
| MEG-OQ-1 | Per-namespace team gateway or shared gateway with per-team routing? | Per namespace (MEG-D1) |
| MEG-OQ-2 | Extend `afs-gateway` or adopt an off-the-shelf gateway? | Extend (MEG-D2) |
| MEG-OQ-3 | Service endpoint credentials: one shared key, or one key or project per team? | Per team by default; shared allowed for providers without projects |
| MEG-OQ-4 | Do enabled service endpoints join every team whose route access is *All* (like models), or must teams opt in? | Join *All*, except `requires_terms` endpoints |
| MEG-OQ-5 | Keep direct (unmetered) access to an `llm` external system once a route exists for that provider? | No by default; a service-admin override per team, shown *Unmetered* |
| MEG-OQ-6 | Self-hosted cost: transfer price, capacity allocation, CUR only, or all three? | All three as modes; CUR for in-namespace, transfer price for central platforms |
| MEG-OQ-7 | Add token quotas (non-USD hard limits) for `capacity` and `free` routes in 1.2.0? | Yes, team-level only first |
| MEG-OQ-8 | Translate OpenAI requests to Bedrock (one protocol for every model) in scope? | Not in 1.2.0; revisit with Envoy AI Gateway or Bedrock's own OpenAI-compatible endpoint |
| MEG-OQ-9 | Strip the injected usage chunk from streams when the client did not ask for it? | Yes |
| MEG-OQ-10 | A model name not listed on a route: refuse, or allow with a route default price? | Refuse (`model_not_on_route`), as Bedrock refuses unpriced models |
| MEG-OQ-11 | Provider cost reconciliation (OpenAI organization costs, OpenRouter usage) in 1.2.0? | Yes for OpenAI and OpenRouter; others later |
| MEG-OQ-12 | Who may declare team endpoints? | Team-admins of teams where a service admin sets `may_add_model_endpoints`, mirroring external systems |
| MEG-OQ-13 | Should AFS host inference servers as a resource kind (GPU NodePool, weights, autoscaling)? | Separate PRD after this one |
| MEG-OQ-14 | Recheck vendor facts (§2.3, §6) before contracts are written | Yes, at contract time |
| MEG-OQ-15 | RDS Proxy now, or move spend counters to Valkey with the team gateway? | RDS Proxy now; Valkey when load tests say so |
| MEG-OQ-16 | Does the orchestration agent (Hermes, Paperclip AI) get routes like any agent? | Yes, same model access screen; the collaboration tool's own model calls go through its routes too |

## 13. Glossary

| Term | Meaning |
|---|---|
| Team gateway | The per-namespace `afs-gateway` Deployment rendered by the reconciler |
| Model endpoint | A configured OpenAI-compatible upstream (service or team level) |
| Route | The name agents use for an endpoint, in URLs and environment variable names |
| Route model | A model name served on a route, with limits and prices |
| Pricing mode | How a route's calls are costed: `per_token`, `capacity` or `free` |
| Transfer price | A per-token internal price service admins set for a shared internal inference platform |

## 14. Review record

- 2026-11-24: drafted from J's question in the project thread; proposal only, awaiting J's answers to section 12.3.
