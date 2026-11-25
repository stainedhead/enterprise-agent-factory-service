# PRD: Team model gateway with OpenAI-compatible model endpoints

| | |
|---|---|
| **Status** | **Approved for build (J, 2026-11-25)**: every open question answered (MEG-OQ-1 to MEG-OQ-23, §13.3); build checklist in Appendix D. Release 1.1.0 is not changed by this document. Target release if approved: 1.2.0 in every repository (`-db` and `-restapi` in lockstep) |
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

**Recommendation, in seven decisions (details in section 13):**

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
   list as a seed for price proposals. The gateway also translates OpenAI Chat Completions to Bedrock Converse, so one
   OpenAI client can reach every model (J, MEG-OQ-8, MEG-OQ-20; section 8.3).
3. **Model endpoints are a catalog with service → team → agent levels**: service admins publish endpoints (and may let
   a team declare its own); **teams opt in** to the endpoints they want (team-admins choose, except endpoints with extra
   terms, which a service admin selects); agents narrow again (section 7; J, MEG-OQ-4, MEG-OQ-19).
4. **Each endpoint gets a route name**, a DNS-label slug such as `openai-prod` or `coder-vllm`. Agents receive one base
   URL per route as an environment variable (`AFS_LLM_OPENAI_PROD_BASE_URL`), a list (`AFS_LLM_ROUTES`) and a file
   (`/etc/afs/llm-routes.json`). Standard OpenAI SDKs work by setting the base URL; no code change (section 8).
5. **Cost and caps by pricing mode** (section 9): token-priced endpoints (OpenAI, OpenRouter, an internal platform with a
   transfer price) are metered **and hard-capped**; self-hosted capacity is metered in tokens and costed from EKS split
   cost allocation or an allocated amount, without a hard limit in 1.2.0 (J, MEG-OQ-7).
6. **Inference telemetry comes with it** (section 10, J 2026-11-24): latency, time to first token, errors and token
   throughput per route, model and team (and per agent from the ledger and traces), emitted as OpenTelemetry with the
   GenAI semantic conventions, landing in the platform's metrics and trace stores, the `usage_events` ledger and,
   optionally, the team's own log destination. Route health becomes a status condition and a notification.
7. **Every provider has its own switch** (section 7.4, J 2026-11-24): service admins turn each model provider off
   independently, Bedrock included. A new install has Bedrock, OpenAI, OpenRouter, Nous Portal and OpenCode on (opt-out),
   and **Azure** (Azure OpenAI and Foundry models) and **Google** (Vertex AI) off, with teams selected by service admins
   (opt-in). Off refuses calls, removes the routes and the gateways' egress, and closes direct access, without deleting
   anything. Azure and Google authenticate by workload identity federation from the team gateway's own AWS identity, so
   no provider secret is stored (section 11.1).

This partly reverses D7 / EXT-6 / RPT-7: a non-Bedrock LLM reached **through a route** is metered and capped; one
reached directly as an external system stays *Unmetered*, and direct access to a provider is blocked while a route for
it exists, unless a service admin allows it for one team (J, MEG-OQ-5).

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
- G5. Route access has three levels: the service switch, each team's opt-in (team-admins; service admins for endpoints
  with extra terms) and each agent's selection.
- G6. One team's gateway trouble does not affect any other team.
- G7. The inference layer is observable: latency, time to first token, errors and token throughput per route, model,
  team and agent, in standard OpenTelemetry form, without storing content (section 10).
- G8. Existing agents keep working: Bedrock paths, environment variable names and error codes of gateway contract
  v1.1.0 do not change.
- G9. Service admins can switch each model provider off independently, Bedrock included, for enterprises that limit
  which providers may be used. Off removes the provider's routes from agents, refuses calls within 60 s and removes the
  gateways' egress to its hosts (J, 2026-11-24; section 7.4).

### Non-goals (this change)

- Hosting inference servers, now or later (J, MEG-OQ-13). AFS routes to and meters servers that teams or a central
  ML platform run; it does not manage GPU node pools, model weights or autoscaling for them.
- Translating to providers other than Bedrock, or from Anthropic Messages. Routes to OpenAI-compatible endpoints are
  pass-through; the one translation is OpenAI Chat Completions → Bedrock Converse (section 8.3).
- Token quotas or other non-USD hard limits in 1.2.0 (J, MEG-OQ-7). Capacity and free routes are metered and reported.
- Prompt or response content inspection, guardrails, caching of completions, or semantic routing across providers.
- Fail-over between routes. An agent picks a route; AFS does not silently move its traffic.
- Metering traffic that does not pass a route (direct provider access stays *Unmetered*).

## 4. Users, roles and permissions

No new roles. New permissions mirror external systems and models.

| Action | Service admin | Team-admin | Team viewer | Agent (workload) |
|---|---|---|---|---|
| Publish, change, retire a service-level endpoint and its prices | Yes | No | No | No |
| Turn a model provider on or off, Bedrock included; choose which teams may use a provider that needs service-admin selection (section 7.4) | Yes | No | No | No |
| Approve endpoint price proposals | Yes | No | No | No |
| Allow a team to declare its own endpoints (`teams.may_add_model_endpoints`) | Yes | No | No | No |
| Declare, change, delete a team endpoint (when allowed) | Yes | Yes | No | No |
| Set a team endpoint's prices or pricing mode | Yes | Yes, except a transfer price on a service endpoint | No | No |
| Opt the team in to, or out of, a switched-on service endpoint | Yes | Yes, except endpoints with extra terms | No | No |
| Select an endpoint with extra terms for a team | Yes | No | No | No |
| Narrow an agent's or pool's routes | Yes | Yes | No | No |
| Set an endpoint credential (write-only) | Yes (service), Yes (team) | Yes (team endpoints) | No | No |
| See routes, models, prices, usage and cost | Yes | Yes | Yes (no credential metadata beyond name and last rotation) | Own routes via `/etc/afs/llm-routes.json` |
| Call a route | No | No | No | Yes, within its effective set |

Permissions (API contract v1.5.0 §3): `admin:model-endpoints`, `admin:inference-providers` and the existing `admin:pricing` (service admins); `model-endpoints:read` (every team role) and `model-endpoints:write` (team-admins). Every one gets allowed and denied tests per role in `-restapi`.

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
| **Change from today** | Small | Medium: reconciler renders new objects, `AFS_GATEWAY_URL` value changes per team (name unchanged), migration window with both gateways (section 12.6) |

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

### 7.2 Levels: service switch, team opt-in, agent narrowing

| Level | Rule |
|---|---|
| Provider | Set by service admins (section 7.4). An endpoint whose provider is off is inactive for every team, service and team endpoints alike, whatever its own switch says. A provider with `team_selection = service_admin` (Azure and Google by default) behaves like *Extra terms*: only service admins select its endpoints for teams |
| Service | A service endpoint is `enabled` or not. Off means off for every team. New service endpoints ship **off** |
| Team | **Opt-in** (J, MEG-OQ-4, MEG-OQ-19): a switched-on service endpoint reaches no team until it is selected for that team. Team-admins select it themselves; an endpoint flagged `requires_terms` can be selected only by a service admin. There is no *All* rule for teams, so a newly switched-on endpoint never reaches a team by itself. A team with `may_add_model_endpoints` (set by service admins, MEG-OQ-12) declares its own endpoints, which are always part of its set |
| Agent or pool | `routes.access` `all` (the team set) or `selected`, set by team-admins, like `models.access` |
| Model on route | The model is listed on the endpoint and is callable: it has a price in force on a `per_token` route, or the route is `capacity` / `free` (section 9). A model not listed is refused (`model_not_on_route`, MEG-OQ-10) |
| Terms | An endpoint flagged `requires_terms` (a provider with its own contract) is selected per team by a service admin only (mirrors OR-D17) |

Effective set = (switched-on service endpoints the team opted in to, plus the team's own endpoints) ∩ agent (∩ pool). The gateway reads it from a
new `afs.route_admission(subject_kind, subject_id)` with the same 60 s cache and change-feed invalidation as model
admission. Denials use `403 AccessDenied` with `details.reason` in fixed order: `provider_disabled`, `route_not_enabled_for_service`,
`route_not_enabled_for_team`, `route_not_enabled_for_agent`, `model_not_on_route`, `model_not_priced`.

### 7.3 Data model (proposed `-db` migration 000023)

All tables in schema `afs`, team-scoped tables with `team_id`, composite foreign keys, RLS through
`afs.caller_sees_team`, desired-state columns (`version`, `created_at/by`, `updated_at`, revision trigger).

| Table | Key columns | Notes |
|---|---|---|
| `model_endpoints` | `id` (`mep_…`), `team_id` (NULL = service), `slug` (route name, `^[a-z][a-z0-9-]{1,30}$`, unique across the service and each team; a team cannot reuse a service slug; `bedrock` reserved), `display_name`, `description`, `owner`, `purpose` (required for team endpoints), `provider` (`bedrock`, `openai`, `openrouter`, `nous`, `opencode`, `azure`, `google`, `other`, `internal`; set by service admins on service endpoints and derived from the host for team endpoints, section 7.4), `protocol` (`openai_chat` in 1.2.0; `openai_responses`, `openai_embeddings` allowed as additional paths), `location` (`external` internet FQDN, `corporate` host on the corporate network, `in_namespace` a Service name in the team namespace; `in_namespace` only for team endpoints), `base_url` (https except `in_namespace`, which may be http inside WireGuard, recorded like PC-D7), `ca_bundle` (optional PEM, not a secret), `auth_kind` (`none`, `bearer`, `header` with `auth_header`, `azure_federated`, `google_federated`, section 11.1), `metrics_port` (optional, `in_namespace` only, MEG-OQ-18), `credential_mode` (`shared` one credential, `per_team` one per team for service endpoints), `pricing_mode` (`per_token`, `capacity`, `free`), `requires_terms`, `enabled`, `timeout_seconds`, `max_body_mib` | No credential value, only metadata. `external_system_id` optional link to the external systems catalog entry of the same provider, used for direct-access policy (MEG-OQ-5) |
| `endpoint_models` | `(endpoint_id, model_name)`, `max_output_tokens`, `context_tokens`, `enabled` | `model_name` is what the client sends in `model`; free text, validated as printable ≤ 200 chars |
| `endpoint_model_prices` | `(endpoint_id, model_name, effective_from)`, `input_per_mtok_usd`, `output_per_mtok_usd`, `cached_input_per_mtok_usd`, `request_fee_usd` (optional per-call fee), `source` (`manual`, `price_list`, `transfer`) | `numeric`, USD. Effective-dated like `model_prices` |
| `endpoint_price_proposals` | as `model_price_proposals` | From LiteLLM's list or a provider's published prices; approved by a service admin |
| `endpoint_credentials` | `(endpoint_id, team_id NULL)`, `secret_arn`, `rotated_at`, `status` | ARN at the managed path of section 11; `team_id` set for `per_team` and team endpoints |
| `team_model_endpoints` | `(team_id, endpoint_id)`, `selected_by` (`team_admin` or `service_admin`) | The team's opt-in rows. Insert of a `requires_terms` endpoint by a caller who is not a service admin → `42501` |
| `agent_model_endpoints`, `pool_model_endpoints` | `(team_id, agent_id\|pool_id, endpoint_id)` | Selection rows when the agent's or pool's `route_access = selected` |
| `endpoint_capacity_costs` | `(endpoint_id, team_id, effective_from)`, `monthly_usd` or `hourly_usd`, `allocation` (`by_tokens`, `by_agent`) | Optional, for `capacity` routes not costed by CUR (section 9.3) |
| `endpoint_federations` | `(endpoint_id, team_id)`, `kind` (`azure`, `google`), Azure `tenant_id`, `client_id`; Google `project_number`, `pool_id`, `provider_id`, `project_id`, `location`; `status`, `last_error`, `checked_at` | Metadata only, no secret (§11.1). Team-owned: RLS; written by service admins |
| `provider_statements` | `id` (`pst_…`), `endpoint_id`, `period` (month), `source` (`nous_statement`, `opencode_csv`), `rows` (per team and model: amount USD, tokens if given), `imported_by`, `imported_at` | Service-wide; read by `afs-billing` for monthly reconciliation (§9.4) |
| `inference_providers` | `provider` (key), `display_name`, `hosts` (FQDN globs, for example `api.openai.com`, `*.openai.azure.com`, `*-aiplatform.googleapis.com`), `enabled`, `team_selection` (`team_admin` or `service_admin`), `disabled_reason`, `changed_by`, `changed_at` | Service-wide, no `team_id`. Seeded per section 7.4; `other` matches any external host not listed; `internal` (corporate and in-namespace endpoints) has no switch. Audited on every change |


Column additions: `teams.may_add_model_endpoints` (service-admin only, guarded like
`may_add_external_systems`); `teams.gateway_deployment` (`shared` default, `per_namespace`, §12.6); `agents.default_route`; `agents.route_access`, `agent_pools.route_access`; `usage_events.endpoint_id` (NULL for
Bedrock), `usage_events.model_name` (text, for route calls, since `model_id` is an FK to Bedrock `models`),
`usage_events.usage_source` (`response`, `estimated`, `provider_cost`), `usage_events.reasoning_tokens`, the timing columns `ttft_ms`, `upstream_ms`, `gateway_ms` and `http_status` (§10.4);
`cost_daily.source` gains `route` and `route_capacity`. View `effective_agent_routes` (security invoker), like
`effective_agent_models`. All on online-safe terms (nullable columns, `usage_events` is partitioned; lock impact noted
in the migration header).

### 7.4 Provider switches (J, 2026-11-24)

Enterprises differ in which model providers they allow. Every provider, **Bedrock included**, is a row in
`inference_providers` with its own switch, set by service admins on the *Provider policy* page (screen 68). There is no
single "all external" switch: each provider is turned off on its own (J).

| Provider | Hosts | New install | Teams selected by |
|---|---|---|---|
| Amazon Bedrock | Bedrock runtime VPC endpoints | **On** (opt-out) | Every team (model catalog, MOD-1) |
| OpenAI | `api.openai.com` | **On** (opt-out) | Team-admins (opt-in per team) |
| OpenRouter | `openrouter.ai` | **On** (opt-out) | Team-admins (endpoint has *Extra terms*) |
| Nous Portal | `inference-api.nousresearch.com` | **On** (opt-out) | Team-admins |
| OpenCode Console | `opencode.ai` | **On** (opt-out) | Team-admins |
| **Azure** (Azure OpenAI and Foundry models) | `*.openai.azure.com`, `*.services.ai.azure.com`, `*.cognitiveservices.azure.com` | **Off** | **Service admins** |
| **Google** (Vertex AI) | `aiplatform.googleapis.com`, `*-aiplatform.googleapis.com` | **Off** | **Service admins** |
| Other external hosts | any external host not listed (team-declared endpoints) | On | Team-admins, when the team may declare endpoints |

"On" for a provider only makes it possible: each of its service endpoints still ships off and reaches a team only
through opt-in (section 7.2). Corporate and in-namespace endpoints are not providers; each has its own switch.

**What "off" does**, in order, all from desired state (nothing is deleted):

1. **Admission.** Within 60 s (change feed), every call on the provider's routes, service and team, returns
   `403 AccessDenied` with `details.reason = provider_disabled`, before anything is reserved or forwarded.
2. **Routes disappear.** The reconciler drops the routes from `AFS_LLM_ROUTES`, the `AFS_LLM_<ROUTE>_BASE_URL`
   variables and `/etc/afs/llm-routes.json`. Agents see the change on their next restart; admission already holds in
   the meantime. An agent whose default model was on the provider follows the default-model rule below.
3. **Egress and identity are removed.** The reconciler removes the provider's hosts from every team gateway's Cilium
   egress policy and from agents' egress for linked `llm` external systems. For Azure and Google it also removes the
   federation from the gateways' token files; for Bedrock it removes `bedrock:Invoke*` from every gateway role. A team
   endpoint whose host matches a disabled provider's `hosts` is refused at create or update (`ValidationError`,
   `provider_disabled`).
4. **Direct access closes too.** `llm` external systems of a disabled provider are not grantable and existing grants stop
   rendering, including service-admin overrides (MEG-OQ-5), so blocking the route does not push agents to an unmetered
   direct path.
5. **Recorded.** One audit record and one `inference_provider.disabled` (or `.enabled`) outbox event; every role sees
   *Off by provider policy* on the affected routes and models.

Turning a provider back on restores opt-ins, agent selections, credentials, federations and prices.

**When Bedrock is off.** Bedrock is the default today: the orchestration agent and every agent get a Bedrock default
model (MOD-3, MOD-4), and the Bedrock paths of the gateway contract serve the Anthropic Messages protocol. So:

- *Default models can be route models.* `models.default_model_id` and an agent's default model may name a route model
  as `<route>/<model>` (for example `azure-openai/gpt-5.1`). It is delivered as `AFS_DEFAULT_MODEL` plus
  `AFS_LLM_DEFAULT_ROUTE` and `AFS_LLM_DEFAULT_MODEL` (§8.2). This is useful even with Bedrock on.
- *A fallback is required.* Bedrock can be turned off only when the service default model is a route model on a provider
  that is on, and that route is selected for every team. The confirmation (screen 68a) offers to select it for all
  teams in the same step, recorded as `selected_by = service_admin`. Otherwise `ValidationError`
  (`no_fallback_model`).
- *Agents move to the fallback.* An agent whose default model is a Bedrock model gets `ModelUnavailable=True` (MOD-6) and
  starts on the service default route model at its next restart, orchestration agents included; a team-admin may pick
  another default. An agent with selected models and no route at all is `Degraded`.
- *Harness protocols.* Each runtime template declares the protocols it speaks (`anthropic_messages`, `openai_chat`).
  An agent whose template speaks only Anthropic Messages has no model without Bedrock in 1.2.0 and becomes `Degraded`;
  the confirmation lists them. Hermes, the default harness and the orchestration agent's, is configured for an
  OpenAI-compatible endpoint by base URL; the conformance suite covers it, but Bedrock off is not gated on it (J,
  MEG-OQ-23): it ships in 1.2.0 with the fallback rule and the impact confirmation.
- *Bedrock refusals.* Calls on Bedrock paths, `/r/bedrock` and the Converse translation return `provider_disabled`. The
  daily Bedrock catalog sync pauses; CUR reconciliation continues for any residual spend.

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

### 8.3 OpenAI protocol to Bedrock (J, MEG-OQ-8, MEG-OQ-20)

The built-in route `bedrock` also accepts the OpenAI protocol: `POST ${AFS_GATEWAY_URL}/r/bedrock/v1/chat/completions`
with `"model": "<AFS model id>"` (stream or not), so an agent can reach every Bedrock model in its effective model set
with one OpenAI client. Agents with Bedrock models receive `AFS_LLM_BEDROCK_BASE_URL` like any route.

- `afs-gateway` maps Chat Completions to Bedrock **Converse** / **ConverseStream**: `messages` (system, user, assistant,
  tool), images as content blocks, `tools` and `tool_choice` to `toolConfig`, `tool_calls` and tool results both ways,
  `max_completion_tokens` / `max_tokens` to `inferenceConfig.maxTokens`, `temperature`, `top_p`, `stop`; `stopReason` to
  `finish_reason`; Converse `usage` to the OpenAI `usage` object; ConverseStream events to SSE chunks.
- It is the same call as a native Converse call for everything that matters to AFS: model admission (§2.1 of the
  gateway contract), reservation and settlement, the team's application inference profile, `requestMetadata` tags and
  usage rows (`endpoint_id` NULL, model id as today).
- Not supported on this path, answered `400 ValidationError` with `details.reason = unsupported_parameter` naming the
  field: `n` > 1, `logprobs`, `response_format` types the model cannot honour, audio. `GET /v1/models` lists the
  agent's Bedrock models.
- Responses and Embeddings on `bedrock` are not in 1.2.0 (`404`); embeddings stay on `InvokeModel`.

## 9. Cost tracking and hard caps

### 9.1 Pricing modes

| Mode | Use for | Metered | USD cost per call | Hard cap |
|---|---|---|---|---|
| `per_token` | OpenAI, OpenRouter, Azure OpenAI, any priced provider; an internal platform with a **transfer price** set by service admins | Yes | From `endpoint_model_prices` (+ optional request fee) | **Yes**, reserve and settle against the team budget |
| `capacity` | Self-hosted inference whose cost is the hardware (team GPU nodes, a reserved cluster) | Yes, tokens | Zero per call; cost comes from CUR (EKS split cost by namespace) or `endpoint_capacity_costs`, allocated daily | No (reported only, MEG-OQ-7) |
| `free` | Internal services charged elsewhere, evaluation endpoints | Yes, tokens | Zero | No (reported only) |

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
- `capacity` and `free` routes have no hard limit in 1.2.0 (J, MEG-OQ-7): tokens are metered and reported per agent,
  so a team sees which agent saturates its server. Token quotas are recorded as a candidate for a later release; if
  added, they should refuse with `402` and a distinct code `QuotaExceeded`, because OpenAI SDKs retry `429`.

### 9.4 Reconciliation against the provider's bill

CUR reconciles Bedrock. For external providers, `afs-billing` reconciles the gateway's settled cost against the
provider's own figures once a day and raises the same `cost.variance_detected` event above
`billing.variance_alert_pct` (J, MEG-OQ-11). Attribution is clean when the endpoint uses `credential_mode = per_team`
with one provider project or key per team, so the provider's figures split by team.

| Provider | How AFS reaches it | Reconciliation source in 1.2.0 |
|---|---|---|
| OpenAI | Route, OpenAI protocol | Organization usage and costs API, per project, pulled daily with an admin key at `<prefix>/_service/billing/<route>` |
| OpenRouter | Route, OpenAI protocol; `usage.cost` per call | Key usage and credits API, pulled daily; per-call `usage.cost` already settles each call (§9.2) |
| **Nous Portal** (J, 2026-11-24) | Route, OpenAI protocol (Nous describes its inference API as OpenAI-compatible chat completions) | **No usage or cost API is documented** (checked 2026-11-24): usage, credits and teams are managed in the portal UI only. Decided (J, MEG-OQ-21): a service admin uploads the portal's monthly usage statement (CSV or PDF figures entered by hand) and AFS reconciles monthly; until then the route shows *Not reconciled* beside its gateway cost. Switch to a daily pull if Nous publishes an API |
| **OpenCode Console** (pay-as-you-go, J, MEG-OQ-22) | Route, OpenAI protocol at `https://opencode.ai/inference/openai/v1`; per-call `usage.cost` in USD | **No usage or billing API is documented** (checked 2026-11-24); the Console's *Export usage* gives a CSV of daily totals by day, model and key holder. Per-call `usage.cost` already settles each call (§9.2). A service admin imports the CSV monthly, as for Nous (MEG-OQ-21); *Not reconciled* until then |
| **Azure** (J, 2026-11-24) | Route, OpenAI protocol on the Azure **v1 API**: `https://<resource>.openai.azure.com/openai/v1/` (or `<resource>.services.ai.azure.com`), standard OpenAI SDK, no `api-version`; Chat Completions, Responses, Embeddings. `model` is the **deployment name**, so the route's model list holds deployment names. Foundry models sold by Azure (DeepSeek, Grok, Llama and others) use the same endpoint | Azure Cost Management, pulled daily for each team's resource or resource group (one Azure resource or group per team keeps attribution clean). The Cost Management query API is not confirmed from the pages checked; confirm under MEG-OQ-14 |
| **Google** (J, 2026-11-24) | Route, OpenAI protocol on Vertex AI's OpenAI-compatible Chat Completions: `https://aiplatform.googleapis.com/v1/projects/<project>/locations/<location>/endpoints/openapi` (path shape confirmed in the REST reference; the `openapi` endpoint name and model ids such as `google/gemini-…` come from Google's OpenAI guide and are confirmed by the conformance fixture) | Cloud Billing export to BigQuery, queried daily per team's Google project. To confirm under MEG-OQ-14 |
| Others | Route | Not reconciled in 1.2.0; gateway cost only |

**Nous Portal and Hermes models (J, 2026-11-24).** Nous Research's Hermes models are offered as a built-in catalog
entry `nous-portal` (shipped off, like every service endpoint), with the Hermes models Nous serves listed on the route
and priced from Nous's published per-token prices. Facts to confirm with Nous before the contract (MEG-OQ-14): the base
URL (third-party guides give `https://inference-api.nousresearch.com/v1`; not stated on Nous's own pages), the model ids
(for example Hermes 4 70B and 405B), whether responses carry `usage` and honour `stream_options.include_usage`, and
whether a portal account can hold one key per team. If usage is missing, calls settle to the reservation and are marked
`estimated` (MEG-D6), so the cap still holds but cost is overstated; the conformance suite records a Nous fixture to find
out. The same Hermes models are also on OpenRouter (`nousresearch/hermes-4-…`), which returns `usage.cost` and has a usage
API: teams that need daily reconciliation today can use Hermes through the `openrouter` route.

**OpenCode (J, 2026-11-24, MEG-OQ-22).** J asked about the OpenCode Go plan. Go is a flat monthly subscription with
a usage allowance, meant for coding agents, monitored for abuse and not covering service accounts, so J chose OpenCode's
**pay-as-you-go Console** instead. It is an ordinary `per_token` route with hard caps. Checked against OpenCode's own
pages on 2026-11-24 ([models and prices](https://opencode.ai/docs/console/models/),
[inference API](https://opencode.ai/docs/console/api/inference), [billing](https://opencode.ai/docs/console/billing)):

- *API.* OpenAI, Anthropic and Gemini-compatible APIs under `https://opencode.ai/inference`. The route uses
  `/inference/openai/v1` (Chat Completions for open models such as Kimi, GLM, MiniMax and DeepSeek; Responses for GPT and
  Grok models). Models whose native API is Anthropic Messages are not offered on this route in 1.2.0. Bearer key.
- *Usage and cost.* Responses carry the native usage fields and `usage.cost` in USD (the amount charged), with the final
  stream chunk when `stream_options.include_usage` is set. The gateway settles to the larger of `usage.cost` and the
  token-price cost, as for OpenRouter.
- *Prices.* Per-1M-token prices are published per model and loaded as price proposals for a service admin to approve.
  Credits are prepaid per workspace, with a card processing fee of 4.6% plus $0.31 on each purchase that is not in
  `usage.cost`; it shows as reconciliation variance unless a service admin includes it in the approved prices.
- *Keys.* One OpenCode **service account per team** (Settings, Service accounts), each with a restricted key that may
  only call models, so `credential_mode = per_team` and the usage export splits by team. OpenCode's own monthly budget
  per service account can be set as a second safety net; AFS's cap stays the authority.
- *Errors.* An empty balance returns `402` from OpenCode, which the gateway maps to `503 Unavailable` with
  `details.reason = provider_balance_exhausted`, so agents do not mistake it for their team's AFS budget. An OpenCode
  budget refusal (`429`) is passed through as `429 Throttled` with `details.reason = provider_budget_exhausted`.
- *Catalog.* Built-in entry `opencode`, provider `opencode`, shipped off like every service endpoint. Free-tier models
  are refused to non-OpenCode clients, so only paid models are listed.

Hermes the **models** are separate from Hermes the **agent harness** (Hermes Agent, MIT), which is AFS's default agent
runtime. The harness is unaffected: it calls whichever routes and models the agent has, through the team gateway.

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
"model spend" across Bedrock and routes, with a *Metered* / *Capped* badge per route. Routes in `capacity`
mode show tokens, allocated cost and effective $/1M tokens. RPT-7 changes from "non-Bedrock LLMs are unmetered" to
"non-Bedrock LLMs reached directly are unmetered".

## 10. Inference telemetry and observability

J, 2026-11-24: the gateway also gives AFS **telemetry for the inference layer**. Every model call, to Bedrock or a
route, already passes one component that knows the team, the agent or pool, the route, the model, the tokens and the
timings, so it is the natural place to measure the health and performance of every model backend, including ones
AFS does not run. Nothing here stores prompt or completion content.

### 10.1 What is measured

| Signal | Definition | Why it matters |
|---|---|---|
| Request latency | Gateway receipt to last byte, split into gateway overhead and upstream time | SLOs per route; overhead keeps the < 25 ms p99 TTFB budget of gateway contract §5 honest |
| Time to first token (TTFT) | Receipt to first content chunk on streams | What agents and people feel; the first sign of an overloaded backend |
| Inter-token latency / output throughput | Mean time between output chunks; output tokens per second per call | Compares backends and models; detects a self-hosted server that is saturating |
| Token throughput | Input, output, cached and reasoning tokens per second and per period | Capacity planning for self-hosted inference; demand per team and route |
| Request rate and concurrency | Calls per second and in-flight calls | Load per route; sizing of team gateways |
| Errors | By outcome and code: upstream 4xx/5xx, `429` throttles with `Retry-After`, timeouts, client disconnects, AFS refusals (`402`, `403` reason) | Separates "the provider is failing" from "AFS refused it" |
| Usage completeness | Share of calls settled with `usage_source = estimated` | A backend that omits usage is a cost-accuracy risk |
| Cost rate | USD per hour per route and team (from settlements) | Spend anomalies before the daily report |
| Backend saturation (in-namespace servers only, optional) | Scraped from the server's own `/metrics` (for vLLM: queue length, running requests, KV-cache use) | Explains TTFT growth on self-hosted inference |

### 10.2 OpenTelemetry GenAI semantic conventions

The gateway emits OpenTelemetry traces and metrics following the GenAI semantic conventions, so standard dashboards
and backends understand them, plus AFS attributes for tenancy:

| Kind | Name (GenAI conventions) | AFS additions |
|---|---|---|
| Span | One client span per call, name `{gen_ai.operation.name} {gen_ai.request.model}` (for example `chat gpt-4.1`), attributes `gen_ai.operation.name`, `gen_ai.provider.name` (`aws.bedrock`, `openai`, or the endpoint's declared provider), `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.request.max_tokens`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`, `server.address`, `error.type` | `afs.team.id`, `afs.agent.id` or `afs.pool.id`, `afs.route`, `afs.endpoint.location`, `afs.pricing_mode`, `afs.cost_usd`, `afs.reserved_usd`, `afs.usage_source`, `afs.request_id` |
| Histogram | `gen_ai.client.operation.duration` (s) | Label set below |
| Histogram | `gen_ai.client.token.usage` (tokens, `gen_ai.token.type` = `input` / `output`) | Plus `afs.token.type` = `cached` / `reasoning` as a separate AFS histogram, because the convention has only input and output |
| Histogram | `afs.gateway.time_to_first_token`, `afs.gateway.time_per_output_token` (s). The conventions define `gen_ai.server.*` versions for servers to report; the gateway measures from the client side, so it uses AFS names rather than claim server-side figures | Label set below |
| Counter | `afs_gateway_requests_total{outcome, code}`, the existing `afs_gateway_*` metrics (added latency, reservation and settle failures, model denials, dropped usage rows) | Route label added |

Trace context: the gateway accepts an incoming W3C `traceparent` from the agent's runtime and continues it, so a
runtime that traces its own work (Hermes, Paperclip AI) sees the model call as a child span; it propagates
`traceparent` upstream only to `in_namespace` and `corporate` endpoints, never to external providers. Content
capture (the conventions' opt-in prompt and completion events) is **off and not configurable** in 1.2.0, in line with
"no prompt or completion content is stored or logged" (gateway contract §8).

The semantic conventions for GenAI are still marked *development* in OpenTelemetry; the gateway pins one version and
records it in `X-Afs-Gateway-Contract-Version` notes, and attribute names are rechecked at contract time
(MEG-OQ-14).

### 10.3 Labels and cardinality

Metrics carry `team_id` (and `namespace`), `route`, `model`, `operation`, `outcome` and status class. **Agent and pool
ids are not metric labels**: hundreds of teams × agents × models × routes would explode series counts in the metrics
store. Per-agent views come from two places that are built for that cardinality: spans (every span carries the agent
id) and the `usage_events` ledger, which already rolls up into five-minute activity rows per agent. Models are bounded
by the route's model list, so `model` is safe as a label.

### 10.4 Where the data lands

| Data | Destination | Who sees it |
|---|---|---|
| Metrics | Each team gateway exposes `/metrics` and pushes OTLP to the cluster's OpenTelemetry Collector (ADOT), which writes to the platform's Prometheus-compatible store (for example Amazon Managed Service for Prometheus) | Platform operators: dashboards and SLO burn-rate alerts per route and team. The console reads aggregated figures through the API (below) |
| Traces | Collector → the platform trace backend (for example AWS X-Ray or Grafana Tempo), tail-sampled: every error, every refused call, every call slower than the route's latency objective, and a 5% sample of the rest | Platform operators; support by `afs.request_id` |
| Per-call ledger | `afs.usage_events` (gains `ttft_ms`, `upstream_ms`, `gateway_ms`, `http_status`) | Reports API, console, CSV exports, by team, agent, route, model and tag, 13-month retention as today |
| Team copy | Optional: the collector forwards a team's spans and gateway log records to the team's own log delivery destination (Fluent Bit / CloudWatch / S3, solution design §7.3), filtered by `afs.team.id` | The team, in its own tools, without access to anyone else's data |
| Health state | The reconciler derives a route condition per team (`Ready`, `Degraded` when the error rate or TTFT objective is breached over 5 minutes, `Unavailable` when every call fails) and writes it to `resource_status`; it emits `model_endpoint.degraded` and `model_endpoint.recovered` outbox events for notification channels | Console route pages, `afs model-endpoints describe-model-endpoint`, notifications |

### 10.5 What people see

- **Service admins**: an *Inference* report (all teams) with latency percentiles, TTFT, error rate, tokens per
  second and cost rate per route and model, and the effective $/1M tokens of self-hosted routes beside priced
  ones; route health on the *Model endpoints* catalog.
- **Team-admins and viewers**: the same for their team, filterable by agent (from `usage_events`), plus route health
  badges on agent pages. A team sees only its own calls, including on service-level routes.
- **Reports API**: `GET …/reports/inference` with `groupBy` `route`, `model`, `agent`, `hour`, `day` and percentiles
  computed from `usage_events` (p50, p95, p99 of latency and TTFT), JSON or CSV, same permissions as the other reports.

### 10.6 Objectives

Proposed defaults, per route, settable by service admins on service endpoints and team-admins on team endpoints:
error rate < 2% and p95 TTFT < 5 s over 30 days; gateway added latency p99 < 25 ms (existing). Breaches drive the
`Degraded` condition and burn-rate alerts; they never block calls.

## 11. Credentials (Secrets Manager and ESO)

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

### 11.1 Workload identity federation for Azure and Google (J, 2026-11-24)

Azure and Google can trust the team gateway's own identity, so **no provider secret is stored at all**. This is the
same pattern as the token exchange proposed for MCP servers (MCP PRD, MCP-OQ-10). `auth_kind` gains
`azure_federated` and `google_federated`. Each team gateway exchanges its identity for a short-lived token per call
(cached until shortly before expiry) and never gives it to agents.

| | Azure (Microsoft Entra workload identity federation) | Google (Workload Identity Federation) |
|---|---|---|
| What the gateway presents | A projected Kubernetes service account token for `afs-gateway` in the team namespace, audience `api://AzureADTokenExchange`, issued by the EKS cluster's OIDC issuer (RS256) | The team gateway's AWS role (Pod Identity): a signed `GetCallerIdentity` request, which Google verifies with AWS. No AWS-side setup is needed |
| Trust set up by the enterprise's cloud admins | A federated identity credential on a user-assigned managed identity or app registration: issuer = the EKS OIDC issuer URL, subject = `system:serviceaccount:afs-t-<slug>:afs-gateway`, one audience | A workload identity pool with an AWS provider for the AFS account; attribute mapping `attribute.aws_role` from the role ARN; the team's gateway role granted Vertex AI access on the team's Google project (direct resource access, no service account key) |
| Token used on the call | Entra access token for the Azure AI scope (Microsoft's examples use `https://cognitiveservices.azure.com/.default` and `https://ai.azure.com/.default`; the conformance fixture fixes which), role *Cognitive Services OpenAI User* | Google access token from STS (`sts.googleapis.com/v1/token`), bearer on the Vertex AI call |
| Per-team isolation | Subject names the team's namespace, so only that team's gateway can obtain the identity. Wildcards are not allowed and an identity holds at most 20 federated credentials, so AFS recommends **one managed identity per team** | The mapping names the team's gateway role, so only that gateway matches. One Google project per team gives cost attribution |
| What AFS stores | Tenant id, client id and the issuer/subject it expects (metadata, not secrets) | Project number, pool and provider ids, project and location (metadata) |

- Service admins register the per-team identifiers on the endpoint's *Teams & credentials* tab (S-G3). The tab shows
  the exact issuer, subject and audience (Azure) or role ARN (Google) that the cloud admins must trust.
- Until the trust works, calls return `503 Unavailable` with `details.reason = federation_not_ready`, and the tab shows
  the last exchange error. Entra may need a short while after a credential is created, so the gateway retries the
  exchange with backoff.
- API keys stay possible for both providers (`bearer`, stored per §11) for enterprises that prefer them; federation is
  the default on new Azure and Google endpoints.

## 12. Impact by layer

### 12.1 Gateway contract (v1.2.0, minor)

New paths (§8.1, §8.3), route admission reasons, `unsupported_parameter`, `AFS_LLM_*` variables and `/etc/afs/llm-routes.json`.
`AFS_GATEWAY_URL` keeps its name; its value is documented as opaque (it was already only consumed as a variable), so
moving it to the team gateway is not a major change. Bedrock paths, error codes and identity rules are unchanged.

### 12.2 `-db` (000023, release 1.2.0)

Tables and columns of section 7.3, `afs.route_admission`, `effective_agent_routes`, the `_gateway` secret path in
`afs.secret_path`, change-feed triggers on the new tables, RLS and grants (`afs_gateway` reads its team's rows only;
from B, the per-namespace gateway connects as `afs_gateway` with `SET LOCAL afs.team_ids` to its team), isolation
tests and `seedOtherTeams` rows for every new team-owned table.

### 12.3 `-restapi`

- `afs-gateway`: OpenAI-protocol adapter (Chat, Responses, Embeddings, SSE streaming), the Chat Completions →
  Converse translator for the `bedrock` route (§8.3), route resolution, upstream auth
  from files, usage parsing per §9.2, `GET /v1/models`, route admission cache, a mode flag so the same binary runs as
  the shared gateway or a team gateway (`--team-namespace`); GenAI-convention spans and metrics, `traceparent`
  handling and the new timing columns (§10).
- `afs-reconciler`: renders the team gateway (Deployment, Service, PDB, certificate, ServiceAccount and Pod Identity to
  the team's Bedrock role, ExternalSecret, CiliumNetworkPolicy egress to route hosts (minus hosts of blocked providers,
  §7.4) and in-namespace Services, ingress
  from the team's agents only), route ConfigMap content per agent, ring-based gateway image rollout, credential
  secrets at create time.
- `afs-reconciler` (providers): provider switches (§7.4), including removing `bedrock:Invoke*` from gateway roles and
  rendering fallback defaults when Bedrock is off; projected service account tokens for Azure federation.
- `afs-reconciler` (telemetry): route health conditions and `model_endpoint.degraded` / `recovered` events; OTel
  Collector routing of team spans to team log destinations when opted in.
- `afs-billing`: endpoint price proposals from LiteLLM's list and provider pages; daily OpenAI, OpenRouter, Azure Cost
  Management and Google billing export pulls (MEG-OQ-11); Nous Portal monthly statements and OpenCode usage CSV imports;
  capacity allocation; reports by route.
- `afs-api`: the operations listed in Appendix D.3.4 (contract v1.5.0), including: `ListModelEndpoints`, `GetModelEndpoint`, `CreateModelEndpoint`,
  `UpdateModelEndpoint`, `DeleteModelEndpoint` (service and team scope), `PutEndpointModels`,
  `PutEndpointModelPrice`, `List/Approve/RejectEndpointPriceProposal`, `PutModelEndpointCredential`,
  `RotateModelEndpointCredential`, `PutTeamModelEndpoints` (opt-in list), `ListInferenceProviders` and
`UpdateInferenceProvider` (one provider on or off with a reason, its team selection rule and, for Bedrock, the fallback
check), agent and pool `routes` in the existing model
  access body, plus report parameters. Each mutation writes audit and outbox (`model_endpoint.*` events).

### 12.4 `-website`

- SDK regenerated from the contract.
- Console, service admin: **Model endpoints** page beside *Models* (catalog table with protocol, location, pricing
  mode, Metered / Capped badges, enabled switch), create wizard with review step and the equivalent `afs` command,
  prices and proposals tabs, credential tab (write-only).
- Team-admin: **Model endpoints** under the team (opted-in service routes, *Add service endpoint* to opt in, team
  endpoints when allowed),
  agent configuration's *Model access* tab gains *Routes* (all or selected, default route and model) and shows the
  env var names an agent will receive.
- Reports: route group-by and badges; an *Inference* report (latency, TTFT, errors, tokens per second, cost rate)
  for service admins and per team; *Unmetered* badge kept only for direct `llm` external systems.
- Service admin: **Provider policy** tab on *Model endpoints* (one row per provider, Bedrock included, with its hosts,
  routes, teams, team selection rule and switch; a confirmation that lists the impact before turning one off, and for
  Bedrock the fallback default model).
- Proposal mockups are screens 56 to 68 (Appendix A); console stories are US-62 to US-79 (Appendix B).

### 12.5 `-cli`

New service `model-endpoints` (`list-model-endpoints`, `describe-model-endpoint`, `create-model-endpoint`,
`update-model-endpoint`, `delete-model-endpoint`, `put-endpoint-models`, `put-endpoint-model-price`,
`list-endpoint-price-proposals`, `approve-endpoint-price-proposal`, `put-model-endpoint-credential` with value from
file, stdin or prompt only, `rotate-model-endpoint-credential`, `list-inference-providers`, `update-inference-provider`), `teams put-team-model-endpoints`, route options on
`agents update-agent-models`; one command per operation, goldens and AccessDenied tests.

### 12.6 Migration from the shared gateway

1. Ship the team gateway behind `gateway.deployment = shared | per_namespace` (default `shared`).
2. Turn on per namespace for canary teams: the reconciler creates the team gateway, then rolls agents with the new
   `AFS_GATEWAY_URL`. The shared gateway keeps serving pods not yet rolled; both write the same ledger.
3. Ring by ring until every team is moved; then the shared gateway's Bedrock role trust is removed and its Deployment
   scaled to zero. Rollback per team is the reverse (flip the team back and roll agents).
4. Routes are offered only on teams with a team gateway (they need the namespace-scoped credentials).

## 13. Decisions, risks and open questions

### 13.1 Decisions (confirmed by J's answers, 2026-11-24)

| # | Decision | Why |
|---|---|---|
| MEG-D1 | Per-namespace team gateway; shared control plane (J: MEG-OQ-1) | Credential and network isolation stay at the namespace and IAM boundary; one team's failure stays in that team (§5) |
| MEG-D2 | Extend `afs-gateway`; borrow price data from LiteLLM (J: MEG-OQ-2) | Only AFS's gateway reserves USD in AFS's ledger and uses AFS's tenancy (§6) |
| MEG-D3 | Endpoints are a service → team → agent catalog: service switch, **team opt-in** by team-admins (service admins for `requires_terms`), agent narrowing (J: MEG-OQ-4, MEG-OQ-19) | Nothing reaches a team it did not choose; self-service within the service switch |
| MEG-D4 | Route = endpoint slug; path form `/r/<route>/v1` is primary, `<route>/<model>` in the body is supported | Zero-change SDK use and one-client runtimes both work |
| MEG-D5 | Pricing modes `per_token` (capped), `capacity` (CUR or allocated), `free`; no non-USD limits in 1.2.0 (J: MEG-OQ-6, MEG-OQ-7) | Hard caps only where a per-call price is meaningful |
| MEG-D6 | No usage in a response settles to the reservation | Never under-count spend the gateway could not measure |
| MEG-D7 | Upstream credentials at `<prefix>/<namespace>/_gateway/<route>`, gateway-only; `per_team` default for service endpoints | Isolation, revocation and provider-side attribution per team |
| MEG-D8 | Route hosts are reachable from the team gateway only | Without this, caps are advisory |
| MEG-D9 | Pass-through to OpenAI-compatible endpoints, plus Chat Completions → Converse for Bedrock in `afs-gateway` (J: MEG-OQ-8, MEG-OQ-20); no fail-over or content inspection; AFS never hosts inference (J: MEG-OQ-13) | One client protocol for every model, one enforcement path |
| MEG-D11 | Every model provider, Bedrock included, has its own switch set by service admins; existing providers on by default (opt-out), Azure and Google off with teams selected by service admins; off refuses calls, removes routes, egress and direct access, without deleting anything (J, 2026-11-24) | Enterprises allow different providers; one switch per provider says exactly what is allowed (§7.4) |
| MEG-D12 | OpenCode is offered through its pay-as-you-go Console as a `per_token` route, not the Go subscription (J: MEG-OQ-22) | Per-call USD cost fits reserve-and-settle and hard caps; Go's terms target coding agents and exclude service accounts |
| MEG-D10 | The gateway emits OpenTelemetry with the GenAI semantic conventions plus `afs.*` tenancy attributes; agent ids on spans and in the ledger, never as metric labels; content capture off | One standard signal for every backend, at a cardinality the metrics store can hold (§10) |

### 13.2 Risks

| Risk | Mitigation |
|---|---|
| Per-team gateway footprint and RDS connections at hundreds of teams | Small Go pods; RDS Proxy; Valkey counters; option C cells keep the same model |
| Providers that omit usage or bill outside tokens | Settle to reservation; refuse unknown paths; daily provider reconciliation and variance alerts |
| A team re-opens direct provider egress to avoid caps | `llm` systems linked to a route are not grantable to agents (MEG-OQ-5); denied attempts already appear in traffic reports |
| OpenAI-compatible servers differ in small ways (field names, `include_usage` support) | Conformance suite in `-restapi` against the OpenAI SDK and recorded vLLM, SGLang, Ollama and OpenRouter fixtures |
| Version skew during ring rollout | `X-Afs-Gateway-Contract-Version`; minor-only changes inside a release |
| Price data from third-party lists is wrong | Proposals only; a service admin approves every price |

### 13.3 Open questions for J

| # | Question | Recommended answer |
|---|---|---|
| MEG-OQ-1 | Per-namespace team gateway or shared gateway with per-team routing? | **Decided (J, 2026-11-24): per-namespace team gateway (MEG-D1)** |
| MEG-OQ-2 | Extend `afs-gateway` or adopt an off-the-shelf gateway? | **Decided (J, 2026-11-24): extend afs-gateway (MEG-D2)** |
| MEG-OQ-3 | Service endpoint credentials: one shared key, or one key or project per team? | **Decided (J, 2026-11-24): per team by default; shared allowed for providers without projects (MEG-D7)** |
| MEG-OQ-4 | Do enabled service endpoints join every team whose route access is *All* (like models), or must teams opt in? | **Decided (J, 2026-11-24): teams must opt in; a switched-on service endpoint reaches no team until selected for it (no route access All)** |
| MEG-OQ-5 | Keep direct (unmetered) access to an `llm` external system once a route exists for that provider? | **Decided (J, 2026-11-24): blocked while a route exists; service-admin override per team, shown Unmetered** |
| MEG-OQ-6 | Self-hosted cost: transfer price, capacity allocation, CUR only, or all three? | **Decided (J, 2026-11-24): all three as pricing modes: CUR for in-namespace, transfer price or capacity amount for central platforms, plus free** |
| MEG-OQ-7 | Add token quotas (non-USD hard limits) for `capacity` and `free` routes in 1.2.0? | **Decided (J, 2026-11-24): not in 1.2.0; capacity and free routes are metered and reported only** |
| MEG-OQ-8 | Translate OpenAI requests to Bedrock (one protocol for every model) in scope? | **Decided (J, 2026-11-24): yes in 1.2.0: OpenAI-protocol calls can reach Bedrock models (see MEG-OQ-20 for how)** |
| MEG-OQ-9 | Strip the injected usage chunk from streams when the client did not ask for it? | **Decided (J, 2026-11-24): yes, strip it** |
| MEG-OQ-10 | A model name not listed on a route: refuse, or allow with a route default price? | **Decided (J, 2026-11-24): refuse (model_not_on_route)** |
| MEG-OQ-11 | Provider cost reconciliation (OpenAI organization costs, OpenRouter usage) in 1.2.0? | **Decided (J, 2026-11-24): yes for OpenAI and OpenRouter in 1.2.0; others later** |
| MEG-OQ-12 | Who may declare team endpoints? | **Decided (J, 2026-11-24): team-admins of teams where a service admin sets may_add_model_endpoints** |
| MEG-OQ-13 | Should AFS host inference servers as a resource kind (GPU NodePool, weights, autoscaling)? | **Decided (J, 2026-11-24): never; AFS routes and meters, teams or a central ML platform host inference** |
| MEG-OQ-14 | Recheck vendor facts (§2.3, §6) before contracts are written | Action for Claude at contract time (not a decision) |
| MEG-OQ-15 | RDS Proxy now, or move spend counters to Valkey with the team gateway? | **Decided (J, 2026-11-24): RDS Proxy now; Valkey counters only if load tests show the need** |
| MEG-OQ-16 | Does the orchestration agent (Hermes, Paperclip AI) get routes like any agent? | **Decided (J, 2026-11-24): yes, same Models & routes screen and rules; the collaboration tool's model calls go through its routes** |
| MEG-OQ-17 | Forward a team's spans and gateway log records to the team's own log destination? | **Decided (J, 2026-11-24): yes, opt-in per team, off by default** |
| MEG-OQ-18 | Scrape self-hosted servers' own metrics (vLLM queue, KV cache) for in-namespace routes? | **Decided (J, 2026-11-24): yes, optional per endpoint, read-only** |
| MEG-OQ-19 | With opt-in (MEG-OQ-4), who opts a team in to a service endpoint? | **Decided (J, 2026-11-24): team-admins opt their team in to any switched-on service endpoint; endpoints flagged Extra terms still need a service admin** |
| MEG-OQ-20 | How is OpenAI-to-Bedrock translation built (MEG-OQ-8)? | **Decided (J, 2026-11-24): in `afs-gateway`, mapping Chat Completions to Bedrock Converse for every Bedrock model, on the same reserve-and-settle path and team inference profiles** |
| MEG-OQ-21 | Nous Portal documents no usage or cost API. How is it reconciled? | **Decided (J, 2026-11-24): monthly statement entered by a service admin; Not reconciled until then; daily pull if Nous publishes an API; OpenRouter stays the daily-reconciled path to Hermes models** |
| MEG-OQ-22 | OpenCode Go is a personal coding-agent subscription that monitors for abuse and excludes service accounts. Offer it through team gateways? | **Decided (J, 2026-11-24): use OpenCode's pay-as-you-go Console instead, as a `per_token` route with caps; the Go plan is not offered** |
| MEG-OQ-23 | With Bedrock off, agents need a route model. Ship *Bedrock off* in 1.2.0, gated by the fallback rule of §7.4? | **Decided (J, 2026-11-24): ship Bedrock off in 1.2.0 without a test gate; the fallback model rule and the impact confirmation (68a) stay** |

## 14. Glossary

| Term | Meaning |
|---|---|
| Team gateway | The per-namespace `afs-gateway` Deployment rendered by the reconciler |
| Model endpoint | A configured OpenAI-compatible upstream (service or team level) |
| Route | The name agents use for an endpoint, in URLs and environment variable names |
| Route model | A model name served on a route, with limits and prices |
| Pricing mode | How a route's calls are costed: `per_token`, `capacity` or `free` |
| Provider policy | The service admins' switch per model provider, Bedrock included (§7.4) |
| Transfer price | A per-token internal price service admins set for a shared internal inference platform |

## 15. Review record

- 2026-11-25: J approved the build of 1.2.0. Completeness review added Appendix D (requirements by repository, the full
  operation list, definition of done) and the `endpoint_federations` and `provider_statements` tables.

- 2026-11-24: J asked to add OpenCode Go and to let service admins turn external providers off; §7.4 provider policy,
  screens 68 and 68a, US-78, US-79, MEG-D11, MEG-D12, MEG-OQ-22, MEG-OQ-23 and their tests added. J chose OpenCode's
  pay-as-you-go Console over the Go subscription (MEG-OQ-22), so it is a normal per-token route.
- 2026-11-24: J clarified the provider switches: one per provider, Bedrock included, existing providers on by default,
  no single "all external" switch; and asked for Azure and Google, off by default with teams chosen by service admins.
  §7.4 rewritten (Bedrock-off fallback), §9.4 and §11.1 (workload identity federation) added; MEG-OQ-23 replaced.
- 2026-11-24: J answered MEG-OQ-23: Bedrock off ships in 1.2.0 without a test gate; fallback and impact screen stay.

- 2026-11-24: drafted from J's question in the project thread; proposal only, awaiting J's answers to section 13.3.
- 2026-11-24: J added inference-layer telemetry as a goal; section 10 added (G7, MEG-D10, MEG-OQ-17, MEG-OQ-18).
- 2026-11-24: J asked to add Nous Portal (Hermes models) as a supported provider with reconciliation; §9.4 table, MEG-OQ-21,
  TC-BL-04, TC-BL-05, TC-GW-25 added.
- 2026-11-24: J answered MEG-OQ-1 to MEG-OQ-20 on decision cards; the PRD, stories, tests and mockups were updated: no token
  quotas in 1.2.0, team opt-in to service endpoints, Chat Completions → Converse translation for Bedrock, AFS never hosts
  inference.
- 2026-11-24: J asked for UI, use cases and test cases to review; Appendix A (screens 56 to 67 by role), Appendix B
  (user stories US-62 to US-77 with acceptance criteria) and Appendix C (test cases) added.

---

## Appendix A. User experience by role (proposal mockups)

The mockups follow the existing console (AWS-console familiar: dark header with role pill, left navigation,
breadcrumbs, page header with *Info* and right-aligned actions, tables with filter and pagination, one primary action,
wizards with a review step, status as dot + word, *Equivalent CLI* on create forms). Every screen carries a
**PROPOSAL · not built** badge. Sources: [docs/ui/source/gw_screens.py](docs/ui/source/gw_screens.py), run by
`gen.py` and rendered by `shoot.mjs`. Data is illustrative.

New navigation: service admins get **Model endpoints** under *Platform* (beside *Model catalog & pricing*); every team
role gets **Model endpoints** under *Configuration* (beside *Models*); reports gain an **Inference** tab; the agent
page's *Models* tab becomes **Models & routes**.

### A.1 Service admin

| # | Screen | What it shows | Stories |
|---|---|---|---|
| S-G1 | Model endpoints (56) | Service endpoint catalog with route, protocol, location, pricing mode, *Metered* / *Capped* / *Extra terms* badges, service switch, team count, 15-minute health and credential mode; team-declared endpoints; direct LLM access and its *Unmetered* state; pending price proposals; degraded-route alert | US-62, US-63, US-70, US-74 |
| S-G2 | Create endpoint, step 3 (57) | Wizard: endpoint and route, connection and credential, **models and pricing** (pricing mode tiles, models with prices, LiteLLM import, provider-reported cost), access and objectives, review; equivalent CLI | US-62, US-64 |
| S-G3 | Endpoint detail, Teams & credentials tab (58) | Per-team access, credential state (set / missing, never the value), last rotation, team gateway version during ring rollout, spend, calls, errors; provider reconciliation KPI | US-65, US-71, US-76 |
| S-G4 | Inference report (59) | Calls, tokens per second, errors split upstream vs AFS refusals, gateway overhead; per-route latency, TTFT, throughput, error rate, estimated-usage share, cost and effective $/MTok; TTFT chart against the objective | US-73, US-74 |
| S-G5 | Team detail, Model endpoints (60) | The team's opted-in service routes (who selected each), extra-terms selection by service admins, *may declare endpoints* switch | US-63, US-66 |
| S-G6 | Model endpoints, Provider policy (68, 68a) | One row per provider, Bedrock included, with hosts, routes, teams, who selects teams, credential kind and switch; Azure and Google off by default; the confirmation before turning Bedrock off, with the fallback default model and the impact | US-78, US-80, US-81 |

![Service admin: Model endpoints](docs/ui/56-admin-model-endpoints.png)
![Service admin: Create endpoint, models and pricing](docs/ui/57-admin-create-model-endpoint.png)
![Service admin: Endpoint detail, teams and credentials](docs/ui/58-admin-endpoint-detail.png)
![Service admin: Inference report](docs/ui/59-admin-inference-report.png)
![Service admin: Team model endpoints](docs/ui/60-admin-team-routes.png)
![Service admin: Provider policy](docs/ui/68-admin-provider-policy.png)
![Service admin: Turn off Amazon Bedrock](docs/ui/68a-admin-provider-policy-confirm.png)

### A.2 Team-admin

| # | Screen | What it shows | Stories |
|---|---|---|---|
| T-G1 | Model endpoints (61) | Team gateway status and overhead; opted-in service routes with *Add service endpoint* with agents using each, credential, health and spend; team endpoints with owner; degraded-route notice | US-66, US-67, US-74 |
| T-G2 | Create team endpoint (62) | Route name (and the env var it produces), owner, purpose, location tiles (in namespace / corporate / external), Service and port, protocol paths, auth, *Test connection*, pricing mode, models; equivalent CLI; what agents get | US-67 |
| T-G3 | Agent, Models & routes (63) | Bedrock models as in 1.1.0; routes *All* / *Selected* with models, budget control, calls and cost (including `bedrock` through the OpenAI protocol); default route and model; **the exact environment and file the agent receives**; equivalent CLI | US-68 |
| T-G4 | Team Inference report (64) | Calls, p95 TTFT, errors and refusals; per-agent table across routes; cost by route with effective $/MTok for capacity routes; TTFT chart | US-73 |
| T-G5 | Budget & usage (65) | What counts against the cap (per-token routes and Bedrock), what does not (capacity routes, reported only), reserved in flight, EKS compute including the team gateway | US-70, US-72 |

![Team-admin: Model endpoints](docs/ui/61-ta-model-endpoints.png)
![Team-admin: Create team endpoint](docs/ui/62-ta-create-team-endpoint.png)
![Team-admin: Agent models and routes](docs/ui/63-ta-agent-models-routes.png)
![Team-admin: Inference report](docs/ui/64-ta-team-inference-report.png)
![Team-admin: Budget and usage with routes](docs/ui/65-ta-budget-routes.png)

### A.3 Team viewer

Same pages, read-only: every changing control is disabled with the tooltip "Needs team-admin", credentials show only
*Set* / *Missing*, and the CLI panel is hidden. Viewers can open the Inference report (T-G4) as on other reports.

| # | Screen | What it shows | Stories |
|---|---|---|---|
| V-G1 | Model endpoints (66) | T-G1 read-only, with the read-only banner | US-75 |
| V-G2 | Agent, Models & routes (67) | T-G3 read-only, including the environment the agent receives (no values that are secrets exist there) | US-75 |

![Team viewer: Model endpoints](docs/ui/66-tv-model-endpoints.png)
![Team viewer: Agent models and routes](docs/ui/67-tv-agent-models-routes.png)

## Appendix B. User stories and acceptance criteria

Numbering continues the root PRD and the orchestration PRD (last story US-61). Each story names the requirements
sections and screens it proves.

### B.1 Service admin

**US-62 · Publish an OpenAI-compatible endpoint.** As a service admin, I want to publish a model provider as a route
with its models and prices, so that every team can use it with metering and caps. *(§7, §9.1; S-G1, S-G2)*
- Given I complete the *Create endpoint* wizard with slug `openrouter`, protocol Chat, location External, pricing
  *Per token* and three models, when I create it, then `CreateModelEndpoint` returns `mep_…`, the endpoint is **off**
  for the service, an audit record and a `model_endpoint.created` event are written, and no team gets the route.
- Given a slug that is not a DNS label, is `bedrock`, or equals an existing service or team slug, then
  `ValidationError` with `details.reason` `slug_invalid`, `slug_reserved` or `slug_taken`.
- Given a non-HTTPS base URL for an External or Corporate endpoint, then `ValidationError` (`base_url_not_https`).
- Given a *Per token* model without a price, then the endpoint saves, the model shows *Not callable*, and calls to it
  return `403` `model_not_priced`.
- The wizard's review step shows the equivalent `afs model-endpoints create-model-endpoint` command.

**US-63 · Teams opt in to service endpoints.** As a service admin, I want a switched-on endpoint to be available to
teams without reaching any of them until they choose it. *(§7.2; S-G1, S-G5, T-G1)*
- Given `openai-prod` is switched on, then no team has the route until it opts in; T-G1's *Add service endpoint* lists
  it for every team.
- Given a team-admin adds `openai-prod` to the team, then within 60 s calls from that team's agents whose route access
  is *All* are admitted, after their next restart they have `AFS_LLM_OPENAI_PROD_BASE_URL`, and the opt-in is audited
  with `selected_by = team_admin`.
- Given an endpoint flagged *Extra terms*, then a team-admin cannot add it (control disabled with "Needs a service
  admin"; API `403`), and a service admin can, on S-G5.
- Given I switch an endpoint off, then within 60 s every call on that route returns `403`
  `route_not_enabled_for_service`, opt-in rows are kept, and agents' files and variables drop it on their next restart.

**US-64 · Approve prices for a route.** As a service admin, I want price changes proposed and approved like Bedrock
prices. *(§7.3, §9.2; S-G1, S-G2)*
- Given the daily job finds a price on the provider's page or the LiteLLM list that differs from the price in force,
  then one pending proposal per model appears; approving writes an `endpoint_model_prices` row effective from its date
  or the approval, whichever is later; rejecting writes nothing.
- No price ever changes without a service admin's approval, and every approval is audited with the old and new price.

**US-65 · Credentials per team.** As a service admin, I want each team to have its own provider key, so that the
provider's invoice splits by team and I can revoke one team. *(§10; S-G3)*
- Given credential mode *Per team*, when I set a team's credential from a file or prompt, then the value goes to
  Secrets Manager at `afs/<namespace>/_gateway/<route>`, the response and every later read return only state and
  rotation time, and the audit record has no value.
- Given a team with the route but no credential, then its calls on the route return `503 Unavailable` with
  `details.reason = credential_missing`, and S-G3 lists the team as *Missing*.
- Given I rotate a credential, then the team gateway uses the new value within 2 minutes without a restart, and calls
  in flight complete.

**US-66 · Let a team declare its own endpoints.** As a service admin, I want to allow selected teams to add their own
endpoints. *(§7.2, MEG-OQ-12; S-G5)*
- Given `may_add_model_endpoints` is off, then a team-admin's *Create endpoint* is disabled with "Needs permission from
  a service admin" and `CreateModelEndpoint` for the team returns `403 AccessDenied`.
- Only a service admin can change the switch (`403` for a team-admin, audited either way).

### B.2 Team-admin

**US-67 · Add the team's own inference server.** As a team-admin, I want to put the team's vLLM server behind a
route, so that agents use it through the gateway and its use is measured. *(§7, §8, §9.3; T-G1, T-G2)*
- Given I create endpoint `coder-vllm`, location *In this namespace*, Service `vllm-coder:8000`, auth none, pricing
  *Capacity*, then the route appears on T-G1, the team gateway's network policy allows it to reach that Service, and
  no agent's policy does.
- Given *Test connection* is on, then the gateway calls `GET /v1/models` once and the form shows reachable or the
  error; nothing is saved when it fails unless I turn the test off.
- Owner and purpose are required; a Service name outside the namespace is refused (`ValidationError`).

**US-68 · Choose an agent's routes and see what it gets.** As a team-admin, I want to pick an agent's routes and a
default, and see the exact variables it receives. *(§8.2; T-G3)*
- Given I select routes `bedrock`, `openai-prod`, `coder-vllm` with default `openai-prod` / `gpt-4.1`, when I save with
  `If-Match`, then the pod restarts and has `AFS_LLM_ROUTES=openai-prod,bedrock,coder-vllm`, one
  `AFS_LLM_<ROUTE>_BASE_URL` per route, `OPENAI_BASE_URL` pointing at `openai-prod`, `OPENAI_API_KEY=afs-gateway`, and
  `/etc/afs/llm-routes.json` matching T-G3's preview.
- Given a stale version, then `412 PreconditionFailed` and nothing changes.
- Given the agent calls a route it does not have, then `403` `route_not_enabled_for_agent`.
- Given the agent already sets `OPENAI_BASE_URL` as a configuration value, then AFS does not override it.

**US-69 · Reach Bedrock models with an OpenAI client.** As a team-admin, I want agents that speak only the OpenAI
protocol to use our Bedrock models, with the same budget and tags. *(§8.3; T-G3)*
- Given an agent with Bedrock model `claude-sonnet`, when it calls `AFS_LLM_BEDROCK_BASE_URL` + `/chat/completions` with
  `model: claude-sonnet`, streaming or not, with tools, then it receives a valid Chat Completions response or SSE stream,
  and the call used the team's inference profile, was reserved and settled like a Converse call, and wrote one usage row.
- Given a request with `n: 2` or `logprobs`, then `400 ValidationError` with `details.reason = unsupported_parameter`
  and the field name, before any reservation.
- Given a model outside the agent's effective set, then `403` with the same reasons as a native Bedrock call.

**US-70 · One budget for every per-token model.** As a team-admin, I want OpenAI and other priced routes to count
against the same budget and cap as Bedrock. *(§9.2; T-G5)*
- Given the team has spent 99.9% of a blocking budget, when an agent calls `openai-prod` with a reservation larger than
  what is left, then `402 BudgetExceeded` with `budgetId`, `period`, `remainingUsd`, and nothing is forwarded.
- Given concurrent calls from several pods, then total spend exceeds the cap by at most one in-flight call per pod.
- T-G5 lists each source with *Capped* or *Reported only* and shows reserved in-flight spend.

**US-71 · Never see or leak an upstream key.** As a team-admin, I want agents to work without holding provider keys.
*(§10; T-G3, S-G3)*
- No agent pod has a Secret volume, environment variable or file containing a route credential; T-G3's preview has
  only placeholders.
- A credential sent by an agent in `Authorization` is removed before the upstream call and never logged.

**US-72 · Spend I can trust when usage is missing.** As a team-admin, I want calls whose response has no usage to be
charged safely. *(§9.2, MEG-D6; T-G5)*
- Given a server that returns no `usage`, then the call settles at its reservation, the row has
  `usage_source = estimated`, and the share of estimated calls is shown per route.

### B.3 Any team role and service admins (telemetry)

**US-73 · See how inference is performing.** As anyone on a team, I want latency, TTFT, errors and throughput by
route, model and agent. *(§10; T-G4, S-G4)*
- Given calls in the period, then T-G4 shows p50 latency, p95 TTFT, output tokens per second, error rate split into
  upstream errors and AFS refusals, per agent and per route, computed from `usage_events`; S-G4 shows the same across
  teams for service admins.
- No report, span or log contains prompt or completion text.

**US-74 · Know when a route is degraded.** As a service admin or team-admin, I want to be told when a backend is slow
or failing. *(§10.4, §10.6; S-G1, T-G1)*
- Given p95 TTFT over the route's objective for 5 minutes, then the route's condition becomes `Degraded`, a
  `model_endpoint.degraded` event reaches the team's notification channels, and the alert shows on S-G1 and T-G1;
  `model_endpoint.recovered` follows when it clears. Calls are never blocked by this.

### B.4 Team viewer

**US-75 · Read-only view of routes.** As a team viewer, I want to see routes, health and usage but change nothing.
*(§4; V-G1, V-G2)*
- Every changing control on V-G1 and V-G2 is disabled with "Needs team-admin"; the API returns `403 AccessDenied` for
  every mutation a viewer sends.
- Credentials show only *Set* or *Missing*; no endpoint returns credential metadata beyond name, state and last rotation.

### B.5 Platform operator

**US-76 · Move teams to their own gateway safely.** As a platform operator, I want to move teams ring by ring with
rollback. *(§5, §12.6; S-G3)*
- Given `gateway.deployment = per_namespace` for a canary team, then the reconciler creates its team gateway, then rolls
  agents to the new `AFS_GATEWAY_URL`; agents not yet rolled keep working through the shared gateway, and both write
  the same ledger.
- Given I flip the team back, then agents roll back to the shared gateway and no call is refused during the move.
- A gateway image change rolls by ring; a team gateway that fails readiness stops the ring.

**US-77 · One team's trouble stays in that team.** As a platform operator, I want a failing team gateway or backend to
affect only that team. *(§5.3)*
- Given team A's gateway is crash-looping or saturated by slow upstream streams, then team B's calls see no change in
  error rate or p99 overhead.

### B.6 Provider switches, OpenCode, Azure and Google (J, 2026-11-24)

**US-78 · Turn a provider off.** As a service admin in an enterprise that limits which model providers may be used, I
want to turn each provider off on its own, so that no agent can reach it through AFS. *(§7.4; S-G6)*
- Given a new install, then Bedrock, OpenAI, OpenRouter, Nous Portal, OpenCode and other external hosts are on, and Azure
  and Google are off.
- Given I turn off provider `openrouter` with a reason, then within 60 s every call on any `openrouter` route, service
  or team, returns `403 AccessDenied` with `details.reason = provider_disabled` and nothing is reserved or forwarded;
  one audit record and one `inference_provider.disabled` event are written.
- Given the same change, then the reconciler removes the provider's hosts from every team gateway's egress policy, and
  the routes leave `AFS_LLM_ROUTES`, the `AFS_LLM_<ROUTE>_BASE_URL` variables and `/etc/afs/llm-routes.json` on each
  agent's next restart.
- Given a linked `llm` external system, including one with a service-admin override, then it is no longer rendered into
  any agent's egress and cannot be granted while the provider is off.
- Given a team endpoint whose host matches a disabled provider's hosts, then create or update returns `ValidationError`
  (`provider_disabled`).
- Given I turn the provider back on, then opt-ins, selections, credentials and prices are as they were.
- A team-admin or team viewer sees *Off by provider policy* on the affected routes and cannot change the policy (API
  `403`, audited).

**US-79 · Offer OpenCode pay-as-you-go as a route.** As a service admin, I want OpenCode's open models available to
teams through a capped route, so that teams can use them with the same metering as other providers. *(§9.4; S-G1, S-G6)*
- Given the built-in `opencode` endpoint is switched on and a team opts in, when I set the team's key from its OpenCode
  service account, then calls on the route reserve and settle like any `per_token` route and settle to the larger of
  `usage.cost` and the token-price cost, recording both.
- Given the OpenCode balance is empty, then the agent receives `503 Unavailable` with
  `details.reason = provider_balance_exhausted` and the reservation is released.
- Given an OpenCode service-account budget refusal, then the agent receives `429 Throttled` with
  `details.reason = provider_budget_exhausted`.
- Given I import OpenCode's usage CSV for a month, then variance per team is computed and alerted over 5%; before the
  import the route shows *Not reconciled*.

**US-80 · Turn Bedrock off.** As a service admin in an enterprise that does not use AWS Bedrock, I want to turn it off
and move agents to another provider. *(§7.4; S-G6)*
- Given the service default model is a Bedrock model, when I try to turn Bedrock off, then `ValidationError`
  (`no_fallback_model`) and the confirmation asks me to choose a route model on a provider that is on.
- Given I choose `azure-openai/gpt-5.1` and *Select for every team*, then the route is selected for all teams
  (`selected_by = service_admin`, audited), the service default model becomes the route model, and Bedrock turns off.
- Then within 60 s Bedrock paths, `/r/bedrock` and Converse translation return `403 provider_disabled`; the reconciler
  removes `bedrock:Invoke*` from every gateway role; the daily Bedrock sync pauses.
- Then every agent whose default was a Bedrock model, orchestration agents included, has `ModelUnavailable=True` and
  starts on the fallback at its next restart with `AFS_DEFAULT_MODEL`, `AFS_LLM_DEFAULT_ROUTE` and
  `AFS_LLM_DEFAULT_MODEL` set; agents on a template that speaks only Anthropic Messages are `Degraded`, as the
  confirmation listed.
- Given I turn Bedrock back on, then Bedrock models return to every effective set; defaults chosen meanwhile stay.

**US-81 · Offer Azure or Google to chosen teams.** As a service admin, I want Azure and Google off until I turn them on,
and then only for the teams I pick. *(§7.4, §9.4, §11.1; S-G6, S-G5)*
- Given a new install, then Azure and Google are off and their catalog entries cannot be switched on until the provider
  is on.
- Given I turn Azure on, then a team-admin cannot opt in to its endpoints (control disabled with "Needs a service admin";
  API `403`) and I can select them per team on S-G5.
- Given an Azure or Google endpoint with credential kind *Workload identity federation*, then no secret is stored for
  it; the team gateway obtains a short-lived token per §11.1, and a team whose federation is not set up gets
  `503 Unavailable` with `details.reason = federation_not_ready`.
- Calls are metered and capped like any `per_token` route, and the daily cost pull reconciles them (§9.4).

## Appendix C. Test cases

Test types: **U** unit, **I** integration (real PostgreSQL 17 or envtest), **C** conformance (official OpenAI SDKs
and recorded vLLM, SGLang, Ollama, OpenRouter and Nous Portal fixtures against a fake upstream), **E** console end-to-end
(Playwright with the fake API), **K** cluster isolation test (Cilium, admission, IAM simulator), **P** performance or
chaos. Every authorization rule has a denied case.

### C.1 Database (`-db` 000023)

| ID | Type | Case | Expected |
|---|---|---|---|
| TC-DB-01 | I | Insert endpoint with slug `Bad_Slug`, `bedrock`, a duplicate service slug, a team slug equal to a service slug | `23514` / `23505`, constraint named in the error |
| TC-DB-02 | I | Team endpoint without owner or purpose; `in_namespace` at service level | `23514` |
| TC-DB-03 | I | `afs_app` as team-admin of team A reads or writes team B's endpoints, credentials, opt-ins and selections | 0 rows / `42501` (added to `seedOtherTeams`; `TestCrossTeamWritesChangeNothing` covers them) |
| TC-DB-04 | I | Team-admin sets `teams.may_add_model_endpoints`, or opts the team in to a `requires_terms` endpoint | `42501`; service admin succeeds |
| TC-DB-05 | I | Credential ARN whose path is not `afs.secret_path(team, '_gateway', route)` | `23514` |
| TC-DB-06 | I | A column named like a value (`value`, `secret_string`) on any new table | Schema test fails (existing guard) |
| TC-DB-07 | I | `afs.route_admission` for each level off in turn, and a model without price | Reasons in order: service, team, agent, `model_not_on_route`, `model_not_priced` |
| TC-DB-08 | I | Service endpoint switched on, team has not opted in | Not in the team's effective set; after a team-admin opt-in, in it |
| TC-DB-09 | I | Change on any new table | `pg_notify` on `afs_desired_state` with table, team and id |
| TC-DB-10 | I | Up, down, up of 000023 | Clean; checksums stable |
| TC-DB-11 | I | Switch a service endpoint off and on again | Opt-in rows kept; effective set follows the switch |
| TC-DB-12 | I | `afs.route_admission` with the endpoint's provider off, for service and team endpoints; `internal` endpoints | `provider_disabled` first; covers service and team endpoints; `internal` unaffected |
| TC-DB-13 | I | Team-admin writes `inference_providers`; opts in to an endpoint of a `team_selection = service_admin` provider | `42501`; service admin succeeds |
| TC-DB-14 | I | Fresh migration seed | Bedrock, OpenAI, OpenRouter, Nous, OpenCode, other on; Azure and Google off with `team_selection = service_admin` |
| TC-DB-15 | I | Turn Bedrock off with a Bedrock service default; with a route default not selected for every team; with a valid fallback | `no_fallback_model` twice; then succeeds |

### C.2 Gateway (`-restapi` `afs-gateway`)

| ID | Type | Case | Expected |
|---|---|---|---|
| TC-GW-01 | C | OpenAI Python, Node and Go SDKs with `base_url = AFS_LLM_<ROUTE>_BASE_URL`, Chat non-stream and stream, Responses, Embeddings | Same results as the fake upstream; one usage row per call |
| TC-GW-02 | U | Route in the body form `openai-prod/gpt-4.1` on `/openai/v1/chat/completions` | Routed like the path form |
| TC-GW-03 | U | Request without `max_completion_tokens` / `max_tokens`, with one above the model's limit, and a reasoning model | Forwarded request carries the reserved cap; reservation equals §9.2 formula (table-driven, to the micro-dollar) |
| TC-GW-04 | U | Settlement with cached and reasoning tokens | Cost per §9.2; reasoning not double-counted |
| TC-GW-05 | C | Stream where the client did not set `include_usage` | Upstream receives `include_usage: true`; client receives no extra usage chunk; settlement uses it |
| TC-GW-06 | C | Upstream omits usage; stream cut mid-way; client disconnects | Settled at reservation (or reported tokens), `usage_source = estimated` |
| TC-GW-07 | U | OpenRouter `usage.cost` above and below the token-price cost | Settles to the larger; both recorded |
| TC-GW-08 | U | Budget remaining below the reservation | `402 BudgetExceeded`, nothing forwarded, row `rejected_budget` |
| TC-GW-09 | U | Each admission reason; caller with no route | `403` with the right `details.reason`; usage row `rejected_model` |
| TC-GW-10 | C | OpenAI SDKs against `/r/bedrock/v1/chat/completions`: plain, streaming, tools and tool results, images, stop sequences | Valid Chat Completions output; Converse request as expected (recorded fake Bedrock); reservation, settlement, inference profile and tags as a native call |
| TC-GW-11 | U | Agent sends `Authorization: Bearer sk-…` | Header replaced by the route credential; value absent from logs, spans and errors |
| TC-GW-12 | U | Route with no credential | `503 credential_missing`, nothing reserved |
| TC-GW-13 | I | Credential file rotated on disk | Next call uses the new value; no restart; in-flight call unaffected |
| TC-GW-14 | U | `GET /v1/models` on a route | Answered by the gateway from the agent's effective models; upstream not called |
| TC-GW-15 | U | Unsupported path (`/v1/files`, `/v1/batches`, `/v1/fine_tuning/jobs`) | `404 NotFound`, nothing reserved |
| TC-GW-16 | U | Upstream 5xx, 429 with `Retry-After`, timeout | Reservation released; `502` / `429` passed through / `504`; error recorded by code |
| TC-GW-17 | I | Database unreachable | `503 Unavailable`, nothing forwarded (fail closed) |
| TC-GW-18 | U | Change-feed notification for a route switched off | Cache entry dropped; next call refused within 60 s |
| TC-GW-19 | U | Span for a call | GenAI attributes (`gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.usage.*`) and `afs.*` present; no prompt or completion content |
| TC-GW-20 | U | Incoming `traceparent` | Continued; propagated upstream only for `in_namespace` and `corporate` endpoints |
| TC-GW-21 | U | Metric labels | No agent or pool id label on any metric |
| TC-GW-23 | U | `n` > 1, `logprobs`, audio on the `bedrock` route | `400 unsupported_parameter` naming the field; nothing reserved |
| TC-GW-24 | U | Stream where the client did not request usage, on routes and on `bedrock` | No extra usage chunk reaches the client (MEG-OQ-9) |
| TC-GW-22 | C | Bedrock and Anthropic paths of contract v1.1.0 through the team gateway | Existing conformance suite passes unchanged |
| TC-GW-26 | U | Change-feed notification that a provider is off, including Bedrock | Next call on its routes (Bedrock: contract §2 paths, `/r/bedrock`) `403 provider_disabled` within 60 s; nothing reserved or forwarded |
| TC-GW-28 | C | Azure fixture (v1 Chat Completions and Responses) and Vertex AI fixture (OpenAI-compatible Chat Completions), each with a federated token | Usage parsed and settled; bearer token from the token file, never logged; expired token refreshed without failing the call |
| TC-GW-29 | U | Federation not set up or token exchange failing | `503 federation_not_ready`, nothing reserved |
| TC-GW-27 | C | OpenCode Console fixture: Chat Completions with `usage.cost`, streaming with `include_usage`, `402` empty balance, `429` budget | Settles to the larger cost; `503 provider_balance_exhausted` and `429 provider_budget_exhausted`, reservations released |

### C.3 Reconciler and cluster isolation

| ID | Type | Case | Expected |
|---|---|---|---|
| TC-RC-01 | I | Team switched to `per_namespace` | Deployment (2 replicas), PDB, Service, certificate, ServiceAccount, Pod Identity to the team Bedrock role, ExternalSecret, network policies rendered; agents rolled after the gateway is ready |
| TC-RC-02 | K | Agent pod connects to a route host (for example `api.openai.com`) or the in-namespace `vllm-coder` Service | Denied by Cilium; Hubble records the drop |
| TC-RC-03 | K | Team gateway connects to another team's namespace or gateway | Denied |
| TC-RC-04 | K | Pod in team B reaches team A's gateway | Denied before the gateway |
| TC-RC-05 | K | A non-gateway pod uses the `afs-gateway` ServiceAccount, or a team tries to edit an object labelled `afs.io/component=gateway` | Refused by admission |
| TC-RC-06 | K | IAM policy simulation: agent role reads `afs/<ns>/_gateway/*`; team A gateway reads team B's `_gateway/*` | Denied; team A gateway on its own path allowed |
| TC-RC-07 | I | Agent pod spec | No Secret volume or env from `afs-gateway-routes` |
| TC-RC-08 | I | Agent route change; team-level change; service-level change | Agent change rolls the pod; others update ConfigMap and apply on next roll; gateway enforces within 60 s |
| TC-RC-09 | I | `llm` external system linked to a route | Not rendered into any agent's egress unless a service-admin override exists |
| TC-RC-10 | I | Ring rollout with a gateway image that fails readiness | Ring stops; earlier rings stay; event raised |
| TC-RC-11 | I | Route breaches TTFT objective 5 minutes, then recovers | `Degraded` condition and event, then `recovered` |
| TC-RC-12 | K | Provider turned off | Its hosts leave every team gateway's egress policy; a gateway connection to them is dropped (Hubble); linked `llm` systems leave agent egress, overrides included; routes leave the rendered ConfigMaps; turning it back on restores them |
| TC-RC-13 | I | Bedrock turned off with a route fallback | `bedrock:Invoke*` removed from every gateway role (IAM simulation denies); agents with a Bedrock default rendered with the fallback `AFS_DEFAULT_MODEL`/`AFS_LLM_DEFAULT_*` and `ModelUnavailable`; Anthropic-only templates `Degraded` |
| TC-RC-14 | I | Azure and Google federation for a team | Token files rendered for the team gateway only; no Secret holds a provider credential; agents have no token file |

### C.4 REST API (`-restapi` `afs-api`)

| ID | Type | Case | Expected |
|---|---|---|---|
| TC-API-01 | I | Every new operation × service admin, team-admin (own team, other team), team viewer, security operator, API key | Allowed only per §4; every denied case `403 AccessDenied` and audited |
| TC-API-02 | I | Mutations | Row, audit record and `model_endpoint.*` outbox event in one transaction |
| TC-API-03 | I | Update without `If-Match`, with a stale one | `428` / `412` |
| TC-API-04 | I | `PutModelEndpointCredential` then every read operation | No response, log line or audit record contains the value |
| TC-API-05 | I | `teamId` in the body differs from the path | Path wins; body ignored or `ValidationError` |
| TC-API-06 | I | Reports `inference` with `groupBy=route|model|agent|hour`, JSON and CSV | Percentiles match a reference computed from the fixture ledger |
| TC-API-07 | U | OpenAPI document | Lints; every route declares a permission; a handler without one fails the test |
| TC-API-08 | I | `ListInferenceProviders` and `UpdateInferenceProvider` × every role; team endpoint create with a disabled provider's host | Update service admin only, others `403` and audited; create refused `provider_disabled` |

### C.5 Billing (`-restapi` `afs-billing`)

| ID | Type | Case | Expected |
|---|---|---|---|
| TC-BL-01 | I | Recorded OpenAI organization costs fixture vs ledger, per team project | Variance computed; over 5% emits `cost.variance_detected` |
| TC-BL-02 | I | Capacity route with CUR namespace cost and token shares | Daily allocation by token share sums to the CUR amount |
| TC-BL-03 | I | Price list differs from the price in force | One pending proposal per model; none when equal |
| TC-BL-04 | I | OpenRouter key usage fixture vs ledger | Variance computed per team key |
| TC-BL-05 | I | Nous Portal route with no statement uploaded; then a monthly statement entered | *Not reconciled* shown; after entry, monthly variance computed and alerted over 5% |
| TC-BL-06 | I | OpenCode usage CSV (daily totals by model and service account) vs ledger | *Not reconciled* before import; after import, variance per team computed and alerted over 5% |
| TC-GW-25 | C | Nous Portal fixture: Chat Completions, streaming with `include_usage` | Usage parsed when present; when absent, settled to reservation and marked `estimated` |

### C.6 Console (`-website`) and SDK

| ID | Type | Case | Expected |
|---|---|---|---|
| TC-UI-01 | E | Service admin creates an endpoint through the wizard (S-G2) | Review step and CLI preview match the request sent |
| TC-UI-02 | E | Team-admin creates `coder-vllm` (T-G2) with *Test connection* failing | Error shown; nothing saved |
| TC-UI-03 | E | Team-admin edits agent routes (T-G3) | Env preview updates as routes and default change; request has `If-Match` |
| TC-UI-04 | E | Team viewer on V-G1 and V-G2 | Every changing control disabled with "Needs team-admin"; API `AccessDenied` handled if forced |
| TC-UI-05 | E | Team-admin without `may_add_model_endpoints` | *Create endpoint* disabled with the service-admin tooltip |
| TC-UI-10 | E | Team-admin opts in to a service endpoint; tries one with *Extra terms* | Opt-in saved and audited; extra-terms endpoint disabled with "Needs a service admin" |
| TC-UI-06 | U | Credential form | Value never in state store, URL, storage or logs; field cleared after submit |
| TC-UI-07 | E | Visual baselines for screens 56 to 68 | Match approved baselines |
| TC-UI-11 | E | Service admin turns a provider off, then Bedrock (S-G6, 68a); team-admin opens T-G1 | Confirmation lists the impact; Bedrock needs a fallback before *Turn off* enables; request sent only after confirm; team-admin sees *Off by provider policy* and no policy controls |
| TC-UI-08 | U | `@afs/sdk` generated from contract v1.5.0 | New operations typed; pagination and `If-Match` helpers |
| TC-UI-09 | E | Accessibility of the new pages | WCAG 2.2 AA checks pass |

### C.7 CLI (`-cli`)

| ID | Type | Case | Expected |
|---|---|---|---|
| TC-CLI-01 | U | Each new command: parsing, request sent, `--output json|table|text`, golden files | Matches goldens; JSON field names as the API |
| TC-CLI-02 | U | `put-model-endpoint-credential` with `--value` as an argument | Rejected; value accepted only from file, stdin or no-echo prompt |
| TC-CLI-03 | U | API `AccessDenied` | Exit 254 with the AWS-style message |
| TC-CLI-04 | U | `--debug` on a credential call | Value and `Authorization` redacted |
| TC-CLI-05 | U | `list-inference-providers`, `update-inference-provider --provider bedrock --no-enabled --fallback-model azure-openai/gpt-5.1 --select-for-all-teams --reason …` | Request bodies and goldens match; `AccessDenied` exit 254 |

### C.8 Performance and resilience

| ID | Type | Case | Expected |
|---|---|---|---|
| TC-P-01 | P | Team gateway overhead at 200 concurrent streams | p99 added time to first byte < 25 ms |
| TC-P-02 | P | 300 team gateways against RDS through RDS Proxy | No connection exhaustion; reservation p99 < 10 ms |
| TC-P-03 | P | Team A gateway crash-looping and saturated by slow upstreams | Team B error rate and p99 unchanged (US-77) |
| TC-P-04 | P | Migration of a canary team under load (US-76) | No refused call during the switch and the rollback |

## Appendix D. Requirements by repository (build checklist for 1.2.0)

Added on 2026-11-25 when J approved the build. Every requirement names the stories (Appendix B) and test cases
(Appendix C) that prove it. Each child repository copies its section into its spec (`specs/261125-model-endpoint-gateway/`)
and records progress in that spec's `status.md`. Release 1.2.0 in every repository; `-db` and `-restapi` in lockstep.

### D.1 Root (`enterprise-agent-factory-service`)

| ID | Requirement | Proves |
|---|---|---|
| MEG-ROOT-1 | Database contract: migration 000023 tables, columns, functions (`afs.route_admission`, `afs.provider_enabled`), roles and grants, RLS, change-feed rows, seed of `inference_providers` | TC-DB-* |
| MEG-ROOT-2 | API contract v1.5.0: the operations of D.3.4, schemas, permissions and scopes, error reasons, outbox event types `model_endpoint.*` and `inference_provider.*` | TC-API-* |
| MEG-ROOT-3 | Gateway contract v1.2.0: route paths, body form, `/r/bedrock` translation, admission reasons, provider error mappings, `AFS_LLM_*` variables and `/etc/afs/llm-routes.json`, default-model delivery for route models, headers, telemetry attributes | TC-GW-* |
| MEG-ROOT-4 | Cross-repo spec `specs/261125-model-endpoint-gateway/` and ADR-018 (team gateway per namespace; providers as switches) | — |
| MEG-ROOT-5 | Solution design, README, diagrams (team gateway topology; provider switches) and `skills/` CLI entry updated after the children merge | — |

### D.2 `-db` (migration 000023, v1.2.0)

| ID | Requirement | Proves |
|---|---|---|
| MEG-DB-1 | Tables `inference_providers`, `model_endpoints`, `endpoint_models`, `endpoint_model_prices`, `endpoint_price_proposals`, `endpoint_credentials`, `endpoint_federations`, `team_model_endpoints`, `agent_model_endpoints`, `pool_model_endpoints`, `endpoint_capacity_costs`, `provider_statements` with the constraints of §7.3 | TC-DB-01, 02, 05, 06 |
| MEG-DB-2 | Columns: `teams.may_add_model_endpoints`, `teams.gateway_deployment` (`shared` default, `per_namespace`), `agents.route_access`, `agent_pools.route_access`, `agents.default_route`, `usage_events` route and timing columns, `cost_daily.source` values | TC-DB-01, TC-DB-10 |
| MEG-DB-3 | `afs.route_admission(subject_kind, subject_id)` returning the effective routes and models with denial reasons in the fixed order; `effective_agent_routes` view; `afs.secret_path` `_gateway` scope | TC-DB-07, 08, 12 |
| MEG-DB-4 | RLS on every team-owned table, rows in `seedOtherTeams`, grants per role (`afs_gateway` reads its team's routes; `afs_billing` reads statements; service-only tables writable only by service admins through `afs_app`) | TC-DB-03, 04, 13 |
| MEG-DB-5 | Seed of providers (Bedrock, OpenAI, OpenRouter, Nous, OpenCode, other on; Azure and Google off, `service_admin` selection) and built-in catalog entries, all off | TC-DB-14 |
| MEG-DB-6 | Bedrock-off guard: provider update refused unless the service default is a route model selected for every team | TC-DB-15 |
| MEG-DB-7 | Change feed for every new table; up/down/up clean; `docs/data-model.md` updated | TC-DB-09, 10 |

### D.3 `-restapi` (v1.2.0, API contract v1.5.0, gateway contract v1.2.0)

#### D.3.1 `afs-gateway`

| ID | Requirement | Proves |
|---|---|---|
| MEG-GW-1 | Team mode (`--team-namespace`): one binary serves the shared or a team gateway | TC-GW-22, TC-P-03 |
| MEG-GW-2 | Route resolution (path and body forms), admission from `afs.route_admission` with 60 s cache and change-feed invalidation | TC-GW-02, 09, 18, 26 |
| MEG-GW-3 | OpenAI pass-through for Chat Completions, Responses, Embeddings, SSE; reservation cap written into the request; `include_usage` injected and stripped; usage parsing; provider `usage.cost` settles to the larger | TC-GW-01, 03 to 07, 24, 27 |
| MEG-GW-4 | Chat Completions → Bedrock Converse on `/r/bedrock`, `unsupported_parameter` for unmapped fields | TC-GW-10, 23 |
| MEG-GW-5 | Upstream auth from files (bearer, header), Azure and Google federation (§11.1), rotation without restart; agent `Authorization` replaced and redacted | TC-GW-11 to 13, 28, 29 |
| MEG-GW-6 | Error mapping: `credential_missing`, `federation_not_ready`, `provider_balance_exhausted`, `provider_budget_exhausted`, upstream 429/5xx/timeout, fail closed on database loss | TC-GW-12, 16, 17 |
| MEG-GW-7 | `GET /v1/models` per route from the agent's effective models; unsupported paths 404 | TC-GW-14, 15 |
| MEG-GW-8 | Telemetry: GenAI spans and metrics, no agent label, `traceparent` rules, timing columns | TC-GW-19 to 21 |

#### D.3.2 `afs-reconciler`

| ID | Requirement | Proves |
|---|---|---|
| MEG-RC-1 | Render the team gateway per namespace (Deployment, PDB, Service, certificate, ServiceAccount, Pod Identity, ExternalSecret, network policies) behind `teams.gateway_deployment`; ring rollout | TC-RC-01, 10, US-76 |
| MEG-RC-2 | Egress: route hosts only from the team gateway; agents never; `llm` systems linked to a route not rendered unless overridden; providers off removed | TC-RC-02 to 04, 09, 12 |
| MEG-RC-3 | Agent delivery: `AFS_LLM_*`, `OPENAI_BASE_URL`, `/etc/afs/llm-routes.json`, route default model; roll on agent change | TC-RC-07, 08 |
| MEG-RC-4 | Credentials and federation: `_gateway` secrets, projected token for Azure, nothing mounted into agents | TC-RC-06, 14 |
| MEG-RC-5 | Provider switches incl. Bedrock off (remove `bedrock:Invoke*`, fallback defaults, `ModelUnavailable`, `Degraded` for Anthropic-only templates) | TC-RC-13 |
| MEG-RC-6 | Route health conditions and `model_endpoint.degraded` / `recovered` events | TC-RC-11 |

#### D.3.3 `afs-billing`

| ID | Requirement | Proves |
|---|---|---|
| MEG-BL-1 | Daily provider pulls (OpenAI costs, OpenRouter key usage, Azure Cost Management, Google billing export) behind a provider interface with recorded fixtures; variance over `billing.variance_alert_pct` emits `cost.variance_detected` | TC-BL-01, 04 |
| MEG-BL-2 | Statement imports (Nous monthly statement, OpenCode usage CSV) and *Not reconciled* state | TC-BL-05, 06 |
| MEG-BL-3 | Capacity allocation by token share; endpoint price proposals | TC-BL-02, 03 |

#### D.3.4 `afs-api` operations (contract v1.5.0)

| Operation | Method and path | Permission | Story |
|---|---|---|---|
| `ListModelEndpoints` | `GET /v1/admin/model-endpoints` | `admin:model-endpoints` | US-62 |
| `CreateModelEndpoint` | `POST /v1/admin/model-endpoints` | `admin:model-endpoints` | US-62 |
| `GetModelEndpoint` | `GET /v1/admin/model-endpoints/{endpointId}` | `admin:model-endpoints` | US-62 |
| `UpdateModelEndpoint` | `PATCH /v1/admin/model-endpoints/{endpointId}` (If-Match; includes `enabled`) | `admin:model-endpoints` | US-63 |
| `DeleteModelEndpoint` | `DELETE /v1/admin/model-endpoints/{endpointId}` | `admin:model-endpoints` | US-62 |
| `PutEndpointModels` | `PUT /v1/admin/model-endpoints/{endpointId}/models` | `admin:model-endpoints` | US-62 |
| `CreateEndpointModelPrice` | `POST /v1/admin/model-endpoints/{endpointId}/prices` | `admin:pricing` | US-64 |
| `ListEndpointPriceProposals` | `GET /v1/admin/endpoint-price-proposals` | `admin:model-endpoints` | US-64 |
| `ApproveEndpointPriceProposal` / `RejectEndpointPriceProposal` | `POST /v1/admin/endpoint-price-proposals/{proposalId}:approve` / `:reject` | `admin:pricing` | US-64 |
| `ListEndpointTeams` | `GET /v1/admin/model-endpoints/{endpointId}/teams` | `admin:model-endpoints` | US-65 |
| `PutModelEndpointCredential` | `PUT /v1/admin/model-endpoints/{endpointId}/credentials/{scope}` (`scope` = team id or `_shared`; write-only) | `admin:model-endpoints` | US-65 |
| `RotateModelEndpointCredential` | `POST /v1/admin/model-endpoints/{endpointId}/credentials/{scope}:rotate` | `admin:model-endpoints` | US-65 |
| `PutEndpointFederation` | `PUT /v1/admin/model-endpoints/{endpointId}/federations/{teamId}` (metadata only) | `admin:model-endpoints` | US-81 |
| `ImportProviderStatement` | `POST /v1/admin/model-endpoints/{endpointId}/statements` | `admin:model-endpoints` | US-79, TC-BL-05 |
| `ListInferenceProviders` | `GET /v1/admin/inference-providers` | `admin:model-endpoints` | US-78 |
| `UpdateInferenceProvider` | `PATCH /v1/admin/inference-providers/{provider}` (If-Match; Bedrock fallback fields) | `admin:inference-providers` | US-78, US-80 |
| `PutTeamGatewaySettings` | `PUT /v1/admin/teams/{teamId}/gateway-settings` (`deployment`, `mayAddModelEndpoints`) | `teams:set-guardrails` | US-66, US-76 |
| `ListTeamModelEndpoints` | `GET /v1/teams/{teamId}/model-endpoints` (opted-in, own and available) | `model-endpoints:read` | US-63, US-75 |
| `PutTeamModelEndpoints` | `PUT /v1/teams/{teamId}/model-endpoint-selections` (opt-in list) | `model-endpoints:write` | US-63 |
| `CreateTeamModelEndpoint` / `UpdateTeamModelEndpoint` / `DeleteTeamModelEndpoint` | `/v1/teams/{teamId}/model-endpoints[/{endpointId}]` | `model-endpoints:write` | US-67 |
| `PutTeamEndpointModels` | `PUT /v1/teams/{teamId}/model-endpoints/{endpointId}/models` (prices inline for team endpoints) | `model-endpoints:write` | US-67 |
| `PutTeamModelEndpointCredential` | `PUT /v1/teams/{teamId}/model-endpoints/{endpointId}/credential` | `model-endpoints:write` | US-65, US-67 |
| Agent and pool routes | existing `PutAgentModels` / `PutPoolModels` bodies gain `routeAccess`, `routes`, `defaultRoute`, `defaultModel` may be `<route>/<model>` | existing | US-68 |
| Reports | `GET /v1/reports/inference`, `groupBy=route` and `route` filter on usage and cost reports | existing reports permission | US-73 |

| ID | Requirement | Proves |
|---|---|---|
| MEG-API-1 | Every operation above with allowed and denied tests per role; team scope from the path | TC-API-01, 05, 07 |
| MEG-API-2 | Row, audit and outbox in one transaction; If-Match on updates | TC-API-02, 03 |
| MEG-API-3 | Credential values never stored, returned or logged; federation is metadata only | TC-API-04 |
| MEG-API-4 | Provider rules: disabled-provider host refused; Bedrock fallback guard | TC-API-08 |
| MEG-API-5 | Inference report percentiles from the ledger, JSON and CSV | TC-API-06 |

### D.4 `-cli` (v1.2.0)

| ID | Requirement | Proves |
|---|---|---|
| MEG-CLI-1 | New service `model-endpoints` with one command per operation of D.3.4 (kebab-case of the operationId), examples, columns and goldens | TC-CLI-01, 05 |
| MEG-CLI-2 | `teams put-team-gateway-settings`, `teams put-team-model-endpoints`; agent and pool route options on the existing model commands | TC-CLI-01 |
| MEG-CLI-3 | Credential values only from file, stdin or prompt; redaction under `--debug` | TC-CLI-02, 04 |
| MEG-CLI-4 | AccessDenied tests for every new command; generated reference docs | TC-CLI-03 |

### D.5 `-website` (v1.2.0)

| ID | Requirement | Proves |
|---|---|---|
| MEG-WEB-1 | `@afs/sdk` regenerated from contract v1.5.0; resource helpers for endpoints, providers and the inference report | TC-UI-08 (SDK replay) |
| MEG-WEB-2 | Service admin screens 56 to 60 and 68/68a (catalog, create wizard with CLI preview, endpoint detail with credentials and federation, inference report, team routes, provider policy with Bedrock fallback) | TC-UI-01, 07, 11 |
| MEG-WEB-3 | Team-admin screens 61 to 65 (team endpoints with opt-in, create team endpoint, agent models and routes with env preview, team inference report, budget by route) | TC-UI-02, 03, 05, 10 |
| MEG-WEB-4 | Team viewer screens 66 and 67, every changing control disabled with the role named | TC-UI-04 |
| MEG-WEB-5 | Permission mirror updated with the new permissions; credential values never in state, URL, storage or logs | TC-UI-06 |
| MEG-WEB-6 | Visual baselines for the new screens, for J's approval | TC-UI-07 |

### D.6 Definition of done for 1.2.0

- Every requirement above is implemented with its tests; each repository's gate is green; coverage holds the existing
  floors.
- Release 1.1.0 behaviour is unchanged for teams on the shared gateway: the existing conformance and contract tests pass.
- Contracts merge first in the root (for the MCP 1.3.0 build), then `-db`, `-restapi`, and `-cli` and `-website`.
- Each repository's CHANGELOG records 1.2.0; tag targets are reported to J (tags are pushed by J).
- Real-cloud checks (EKS, Azure and Google federation against live tenants) wait for J's cloud access, as for 1.1.0.
