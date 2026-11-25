# Architectural decision record

Cross-repo decisions. One entry per decision: context, decision, consequences. Status values:
Accepted, Proposed (needs review), Superseded.

## ADR-001 Wrapper root with four independent child repositories

- Status: Accepted (J, 2026-11-20)
- Context: the product has a database, a Go control plane, a Go CLI and a TypeScript SDK and console, with
  different toolchains, owners and release cadences.
- Decision: docs-only root `enterprise-agent-factory-service` plus `-db`, `-restapi`, `-cli` and
  `-website`, cloned inside the root and git-ignored by it. No submodules. The TypeScript SDK lives in
  `-website` as `packages/sdk` (a Bun workspace package, publishable on its own; amended 2026-11-21, pnpm was replaced by Bun, website ADR-004). The reconciler, gateway
  and billing services live in `-restapi` with the API, because they share its domain, authorization and
  store packages.
- Consequences: each child has its own AGENTS.md, CI and releases. `-restapi` imports `-db` as a Go module
  at a released tag. Cross-repo design and specs live in the root. API changes land in the OpenAPI
  contract first, then in the CLI and SDK.

## ADR-002 PostgreSQL desired state with a reconciler

- Status: Proposed
- Context: configuration must survive restarts, be backed up, move between accounts and clusters, and
  correct manual drift.
- Decision: RDS PostgreSQL is the source of truth; a leader-elected Go reconciler applies it to EKS and
  AWS at startup and continuously. See solution-design section 3.1 and 8.
- Consequences: Kubernetes objects are projections, not the record. Export bundles are portable.

## ADR-003 Bedrock access only through a metering gateway

- Status: Proposed
- Context: AWS billing data lags by hours, so it cannot enforce hard caps.
- Decision: agents have no Bedrock IAM permission; the gateway reserves worst-case cost per request,
  invokes the team's application inference profile, then settles. An IAM explicit deny is the backstop.
- Consequences: one more hop on every model call; spend can never exceed the cap by more than one
  in-flight reservation.

## ADR-004 Biome instead of ESLint for TypeScript 7

- Status: Proposed
- Context: TypeScript 7 is the native (Go) compiler; ESLint's type-aware tooling depends on the
  TypeScript JavaScript API, which 7.0 does not provide in the same form.
- Decision: Biome for lint and format; `tsc` 7 for type-checking only (`--noEmit` or library builds).
- Consequences: no dependency on the TypeScript JS API. Revisit when typescript-eslint supports TS 7.

## ADR-005 One agent is one pod

- Status: Proposed (from J's PRD review, 2026-11-21)
- Context: each agent has its own name, ServiceAccount, IAM session tags, external identities (for
  example a GitHub App installation) and audit trail. Replicas of one agent would share that identity,
  with no sensible way to split work between them.
- Decision: no replica count. The reconciler renders each agent as a StatefulSet with exactly one
  replica; pause scales it to zero. A team adds capacity by adding agents. The exception is the
  swarm (AGT-8): a swarm holds several pools of different identities that work together; each pool has
  one identity and a worker count, and its workers share that identity because they do similar work
  across many repositories. Swarm → pools (one identity, N workers) → worker pods. Its schema is db migration 000012.
- Consequences: `agents.replicas` is dropped (db migration 000003); the console and CLI have no scale
  action. Every action in AWS, GitHub or the audit log maps to exactly one running agent.

## ADR-006 AFS-managed Secrets Manager hierarchy

- Status: Proposed (from J's PRD review, 2026-11-21)
- Context: secrets need simple, predictable access rules and must not depend on users choosing names.
- Decision: AFS alone names every secret `<service>/<namespace>/<agent-name>/<secret-name>`, or
  `<service>/<namespace>/_shared/<secret-name>` for team-shared secrets. Users choose only scope, name and
  value. The database computes the path and rejects an ARN that does not match. Registering arbitrary
  existing ARNs is dropped. IAM policies are prefix rules at the service, team and agent level, with the
  `afs-team-id` tag as a second check.
- Consequences: team slug, agent name and secret name are immutable. An agent secret can be bound only
  to its own agent. Moving a secret between scopes means creating a new one.

## ADR-007 One persistent volume per agent

- Status: Proposed (from J's PRD review, 2026-11-21)
- Context: agents keep memory, configuration and work in progress that must survive restarts,
  upgrades and reschedules.
- Decision: each agent's StatefulSet has one `volumeClaimTemplate` (EBS through the CSI driver,
  encrypted, gp3 by default) mounted at `/var/lib/agent`. Size, storage class, on-delete rule and
  snapshot schedule are part of the agent definition. PVC retention is `Retain`; the reconciler alone
  deletes volumes, after a final snapshot by default. Snapshots are recorded in the database and
  referenced by export bundles. Swarm pool workers get ephemeral scratch volumes, with an optional
  shared EFS volume per pool.
- Consequences: volumes grow but never shrink, and the class is fixed after creation. An agent is tied
  to its volume's Availability Zone until restored from a snapshot elsewhere. Storage counts toward team
  quotas and costs are attributed by tag.

## ADR-008 Namespace and agent configuration values

- Status: Proposed (from J's PRD review, 2026-11-21)
- Context: agents need non-secret settings. Some are shared by every agent in a team, some are
  specific to one agent. J clarified that the shared level is the team's namespace (the cluster of
  agents), not the service or the EKS cluster.
- Decision: two levels. Team-admins keep namespace values per team. Each agent value is either a
  literal or a link to the namespace value of the same name. The database resolves them
  (`agent_config_resolved`) and blocks links to missing values, removal of linked values, credential-like
  names and clashes with secret environment variables. The reconciler delivers the resolved set as a
  ConfigMap (env vars and files) and rolls agents when a value changes. The old free-form `agents.env`
  is folded into agent values.
- Consequences: one mechanism for non-secret settings, kept apart from secrets. A service-wide level
  can be added later in the same shape if needed.

## ADR-009 Dedicated agent IAM roles and cross-account role links

- Status: Proposed (from J's PRD review, 2026-11-21)
- Context: agents need clear AWS identities and, for some work, access to roles in other accounts of
  the organization. J also asked for a team-level list of the accounts a team may reach, with `*` for
  all accounts or specific accounts named.
- Decision: an agent runs with its team's shared role or with a dedicated role
  `/afs/<namespace>/afs-<agent id>` (path `/afs/<namespace>/`, name by immutable id; amended 2026-11-21 per root D25). A dedicated agent can be linked to roles in other organization
  accounts; each link carries a target role ARN, a profile name and an AFS-generated external ID, and the
  target account owner adds a trust policy AFS shows. Each team has an allowed-accounts filter of glob
  patterns over account ids and names, recommended to be set by service admins. The filter is enforced
  in the API, in the database by trigger and in the team's IAM permissions boundary. The reconciler
  mirrors AWS Organizations, grants `sts:AssumeRole` per link, writes an AWS config file with one profile
  per link, and verifies each link by assuming it. Swarm pools can use one shared named role
  across several accounts.
- Consequences: globs rather than regular expressions, so the same filter works in SQL and IAM.
  Cross-account access needs one manual step in each target account (the trust policy), and links stay
  *Pending trust* until it is done. An agent with links cannot switch back to the shared team role.
  Export bundles carry links and filters; import maps account ids and re-verifies.

## ADR-010 External systems catalog with service, team and agent levels

- Status: Proposed (from J's PRD review, 2026-11-21)
- Context: agents reach outside services (Atlassian, GitHub, Microsoft 365, Google, Slack, Okta, other
  model providers). J asked for a list that service admins can switch off for every team, that teams and
  agents inherit (on by default) and can only narrow, that service admins can extend with new endpoints,
  and that teams can add to when allowed, so they declare and document what their work depends on.
- Decision: one table of external systems. Service-level entries (built-in or custom) are written by
  service admins; team-declared entries need the team's `may_add_external_systems` right (set by service
  admins), an owner and a purpose. Default-on opt-out rows switch a system off for a team or an agent.
  The view `agent_external_access` gives each agent's effective access and the level that turned a system
  off. The reconciler renders each agent's allowed endpoints into a per-agent Cilium FQDN policy and
  withholds secrets tied to systems that are off. The free-form `team_egress_rules` table is folded in as
  one team-declared system per team. Non-Bedrock model providers ship switched off and are marked
  unmetered: their calls bypass the gateway, and budgets for them are out of scope (J, 2026-11-21).
- Consequences: one mechanism for egress, visible to viewers and audited. Network enforcement is per host,
  so systems that share a host (Outlook and Teams on `graph.microsoft.com`) cannot be separated by the
  network alone; credentials scope them. Enabling OpenAI or OpenRouter creates spend AFS does not see.

## ADR-011 Reporting from metering, activity samples and flow logs

- Status: Proposed (from J's PRD review, 2026-11-21)
- Context: J wants reporting at service, team and agent level on budget and usage, cost by Bedrock
  model, whether agents are working or idle, and traffic to external services.
- Decision: spend, tokens and calls come from the gateway's ledger (near real time) and the daily
  `cost_daily` rollups, reconciled with CUR; compute from CUR split cost allocation. Agent activity is
  sampled every five minutes into `agent_activity` by the reconciler, from model calls, the agent's
  own busy/idle report and CPU. External traffic is aggregated every five minutes from Cilium flow logs
  into `external_traffic`, with allowed and denied verdicts and reasons. All three are queried through
  one report API at the three levels, with CSV export, and kept in PostgreSQL (monthly partitions,
  13 months of five-minute data).
- Consequences: no separate analytics store to run while volumes are modest; if they grow, the same
  tables can be exported to S3 and Athena without changing the API. "Working" is an inference, so the
  definition is shown with every report and agents are asked to report their own state. Spend with
  non-Bedrock model providers is not reported.

## ADR-012 Answers to the PRD open questions

- Status: Accepted (J, 2026-11-21)
- Context: the PRD listed open questions Q1 to Q7 and risks R1 to R5.
- Decision: Okta (default) and Entra ID at service and team level; Cilium; Agentic Teammates CRDs; one
  shared cluster per environment; break-glass ceilings by service admins; teams manage their own AWS
  account filter only when service admins allow it; non-Bedrock LLMs ship off; Bun as the TypeScript
  runtime where available; credentials per agent through Secrets with sign-ins logged and credentials
  redacted from logs; no model price-drift management. R1, R2 and R4 accepted.
- Consequences: schema 000009 adds `identity_providers` and `teams.may_manage_aws_accounts`. The website
  toolchain moves to Bun in its own change. BUD-6 loses variance alerts. See PRD §10.1 for the full log.


## ADR-013 Cost allocation tags, team sign-in provider, price sync, zero-impact delivery

- Status: Accepted (J, 2026-11-21)
- Context: J clarified Q1 and R3, asked for cost allocation tags passed on Bedrock and external calls
  with team and agent ids as automatic system tags, and asked that agents receive secrets and
  configuration with the least possible lift.
- Decision:
  - Identity providers are service-level only. When more than one is configured, each team's provider
    is chosen at creation (service admins) or later (team-admins). Supersedes the team-level providers of
    ADR-012.
  - Price sync is restored: the billing job proposes AWS Price List changes daily for service admin
    approval; CUR variance above a threshold (default 5%) alerts. Supersedes "no price-drift management".
  - Cost allocation tags: system (`afs-team-id`, `afs-agent-id`, never configurable), service (fixed or
    required) and optional team tags; applied to AWS resources, sent as Bedrock request metadata, exposed
    to pods, rolled up in reports. AFS cannot alter agents' calls to external systems; their traffic is
    attributed by agent and so by tag.
  - Zero impact on the container: secrets, configuration, AWS profiles and tags are injected as
    environment variables and files. External Secrets Operator stays.
- Consequences: schema 000010 (`service_tags`, `team_tags`, tag views, `teams.identity_provider_id`,
  `model_price_proposals`, settings `pricing.price_list_sync` and `billing.variance_alert_pct`). PRD
  §6.12, SEC-6, BUD-9, RPT-9, screens S9 and T13; S1, S3 and S4 updated. The website moved to Bun
  (website ADR-004).

## ADR-014 Feature-complete scope, as-of tag snapshots, swarms and work orders

- Status: Accepted (J, 2026-11-21; items marked *Claude* are for J's review)
- Context: J set the implementation target to feature complete: swarms and pools, ephemeral teams,
  budgeted POCs and CVE work orders are in scope with full stories and acceptance criteria, and phases
  are build order only. J also answered the five database gaps and asked that spend roll up by the tags
  in effect when it happened.
- Decision:
  - **As-of tags.** Usage, activity, traffic and daily cost rows carry an immutable `tag_set_id`
    snapshot (`afs.tag_sets`, content-addressed, system tags excluded). Rollups by tag read the snapshot,
    not current tags. External systems are attributed by agent and reported as traffic, with no dollars
    unless a cost is actually known.
  - **Report schedules** are owned by team-admins and delivered only to the team's own channels.
  - **Isolation tier** (`shared` | `dedicated`) is set per team by service admins; dedicated node cost
    is charged to the team.
  - **Idempotency keys** are stored in the database for 1 hour (service setting
    `api.idempotency_key_ttl_seconds`, *Claude*: made a setting rather than a constant).
  - **Agent sign-ins** to external systems go to logs only (team log delivery); no table, not in the
    console.
  - **Ephemeral teams and budgeted POCs.** Teams carry `kind` (`persistent` | `ephemeral`), `expires_at`,
    `teardown_rule` (`at_expiry` | `at_cap_or_expiry` | `at_work_complete`) and a lifetime budget; the
    reconciler tears them down when due. (Amended 2026-11-21 to the names in the schema and the API
    contract.)
  - **Swarms.** An ephemeral team holds ordered stages; each stage holds pools; each pool has one
    identity and a worker count rendered as a Deployment. Pools hand work to other pools through SQS
    queues delivered as environment variables (*Claude*).
  - **Work orders.** A service-level `security_operator` role (*Claude*), which service-level API keys may
    hold, creates CVE work orders by API or by EventBridge event (queued to SQS and drained by the
    reconciler, *Claude*). Work orders are tracked per repository with SLA state; owning teams are
    notified once per event, and contacts outside AFS through the service-level channel named in
    `work_orders.notification_channel_id` (*Claude*).
  - **Viewer kubectl** (read-only kubeconfig for team viewers) is enabled per team by service admins
    only (*Claude*).
- Consequences: db migrations 000011 and 000012. New permissions and operations in the API contract;
  new CLI services (`pools`, `swarm-templates`, `work-orders`) and console screens 27–29.
  `role_bindings` stays without RLS (read through the API's own checks; superseded by ADR-015, which adds
  RLS and guards in `-db` 000013). Decisions D13 to D22 in the root PRD record the detail.

## ADR-015 Answers to the PRD review: contracts, AWS limits, lifecycle and hardening

- Status: Accepted (J, 2026-11-21); D38 revised by J: work order repositories without an explicit owner
  are resolved from each team's `AFS_OWNED_REPOS` configuration value (`-db` 000014
  `afs.resolve_repo_owners`)
- Context: a `review-prd` pass over the root and the four repository PRDs found contradictions between
  documents (permissions, status words, error codes, event and environment names), behaviours AWS cannot
  deliver as written (IAM and SQS name limits, Pod Identity session tags, tag limits), no contract for
  the agent-to-gateway interface, and gaps in the schema's guards. Under J's standing instruction to
  work out answers, Claude decided D23 to D57 (root PRD §10.1) and opened OQ-1 to OQ-9 (§10.3).
- Decision:
  - **One source per fact.** The API contract is the only list of operations, CLI and SDK names,
    permissions, enums and events; the solution design and repository PRDs point to it. Status words
    are the contract's `phase` and `state`; budget exhaustion is the condition `BudgetExhausted` (D24).
  - **Permissions.** Report schedules for team-admins and service admins only (D23); viewers do not see
    API keys (D50); security operators also list templates and the team directory, and get `403` on every
    team route (D37, D38, D56); agents and pools call `afs-api` as workload principals that only report
    work order progress (D29).
  - **AWS within its limits.** Roles and queues named by id (D25); team and agent attribution through
    role tags, Pod Identity's own session tags and `role_session_name` (D26, D51); at most 40 tags per
    resource and 16 Bedrock metadata pairs (D27).
  - **Gateway contract.** A third shared contract: Bedrock Runtime and Anthropic Messages compatible
    paths, projected-token authentication, environment delivered to pods, worst-case reservation with
    held reservations that expire, `402 BudgetExceeded` (D28, D31).
  - **Budgets.** Temporary ceiling overrides with an expiry (D34, root D5); notify-only exhaustion for
    persistent teams by service admins only (D33).
  - **Platform behaviour.** Change feed by `pg_notify` plus polling (D30); one SQS inbox per receiving
    pool (D32); notification channels rendered as EventBridge rules (D46); 13-month retention for usage,
    activity and traffic, audit kept (D36); team lifecycle table for suspend, delete and teardown (D53);
    asynchronous export to S3 by the reconciler, import as a request body (D49).
  - **Clients.** CSV output, safe updates, expired tokens (D39 to D41); console sign-in, hosting, CORS and
    search (D42 to D44); contract version header and CLI client id (D47, D48); one-time secrets never
    replayed (D52).
  - **Schema.** `-db` 000013 (with tightened 000011 and 000012) guards ceilings, quotas, overrides,
    catalogs, settings, users, role bindings and work orders, adds spend periods and reservations, the
    change feed, retention, `models.max_output_tokens` and four settings (D35, D45, D55). `-db` 000014
    adds the `agent_templates` table (D54) and the `export_bundles` changes for D49 (nullable `s3_uri`,
    `download_url`, `download_expires_at`, `size_bytes`).
  - **Gateway caller identity (D57).** The gateway identifies the calling pod by source pod IP through
    the Kubernetes API and Cilium endpoint identity; Cilium allows only team pods to reach it and
    WireGuard encrypts node-to-node traffic. SDK credentials (SigV4, `ANTHROPIC_API_KEY`) are ignored;
    the projected token is optional and must match the source pod.
- Consequences: root PRD §4, §5, §6 (TEAM-9, AGT-11, BUD-10, IF-5, §6.13 settings, OPS-5), §7,
  §8.2, §9 and §10 updated (US-19 to US-26); API contract v1.1.0; database contract at 000013; new gateway contract;
  solution design §3, §5, §7, §9 to §12 aligned. Repository PRDs follow in their own changes.

## ADR-016 One public edge for team collaboration (Paperclip)

- Status: Proposed (decided by Claude for J's review, 2026-11-22; PC-D1 and PC-D2 of the
  [Paperclip PRD](../paperclip-team-collaboration-PRD.md))
- Context: each team's agents and people need a shared board and chat (Paperclip, run by the Agentic Teammates
  `agentic-team-w-paperclip` image). People must reach its web UI and REST API from the internet, but TEAM-3 and TEAM-4
  deny all namespace ingress and forbid LoadBalancer and NodePort Services. Paperclip has no OIDC (its own sign-in is
  email and password), its own agent and secret models, and its content is untrusted input to every agent that reads it.
- Decision:
  - **One AFS-owned public entry (PC-D1).** An internet-facing ALB with AWS WAF forwards to `afs-edge`, a Go service in
    `afs-system` (multi-AZ, at least 3 replicas), which routes by host (`<team-slug>.<collab.base_domain>`, wildcard DNS
    and certificate) to the team's `paperclip` ClusterIP Service. Teams still cannot publish anything; the reconciler
    renders the only exception. One shared ALB keeps cost flat and needs no per-team listener rules.
  - **The edge decides access, not Paperclip (PC-D2).** `afs-edge` signs people in with the team's own provider (OIDC code
    + PKCE, fixed callback, host-only session cookie per team) and authorizes every request with the same
    `internal/authz` code and role bindings as `afs-api`; REST callers send `X-Afs-Authorization` and keep Paperclip's
    credential in `Authorization`. Paperclip's own login stays but is never the control: removing a binding cuts access
    within 60 seconds. Web UI and REST API are switched on or off independently per team, under a per-team guardrail and a
    service-wide switch.
  - **A least-privilege database path.** The edge connects as `afs_edge`, which can execute ten `SECURITY DEFINER`
    functions (routes, settings, principal by person or key, access counts, one secret-detection event, server-side sessions and the single-use handoff) and reads no table. The ACM certificate and DNS cover the apex and the wildcard; the edge checks `Host`, not SNI.
  - **Recorded exceptions.** TEAM-3 and TEAM-4 gain the named openings of solution design §4.1; the in-namespace hop to
    Paperclip is HTTP inside WireGuard (PC-D7), the one exception to TLS on every hop.
- Consequences: a new component and an internet-facing attack surface for the platform (WAF, ASVS L2, penetration test
  before production, kill switches); a new role `team_collaborator` and five permissions in the API contract; migration
  `-db` 000020; contracts updated (database §7.2, API §4.4b and §4.4c, gateway: no change). Alternatives rejected: a load
  balancer or Ingress per team (breaks TEAM-4 and multiplies cost), and trusting Paperclip's login (no SSO, no RBAC).

## ADR-017 Team orchestration agent, graded exposure and model access

- Status: Accepted (J, 2026-11-23; decisions OR-D1 to OR-D17 of the
  [team orchestration agent PRD](../team-orchestration-agent-PRD.md)). Changes ADR-016 and the 1.0.1 collaboration design;
  release 1.1.0 in every repository, `-db` and `-restapi` in lockstep; removals in 2.0.0.
- Context: in 1.0.1 a team-admin could optionally create one collaboration agent among the workers. Teams ran without one,
  its endpoints (the only openings in a team's isolation) were configured on a page that did not say which agent owned them,
  a surface was either internet-facing or off, Paperclip was hard-wired, and each agent named exactly one model.
- Decision:
  - **Mandatory orchestration agent (OR-D1, OR-D2, OR-D12).** Every team, including work order teams, gets one agent with
    role `orchestration` (named `orchestrator`; converted 1.0.1 agents keep their names) in the same transaction as the team.
    The database enforces at most one (unique index) and, for new teams, at least one (deferred constraint trigger). It cannot
    be created through `CreateAgent` or deleted apart from the team; pause, restart and configuration work as for any agent.
  - **Hidden harness, chosen tool (OR-D3, OR-D6, OR-D7).** The agent runs a harness plus a collaboration tool, Paperclip AI
    (default) or Buzz (preview). Service admins map each tool to an orchestration runtime template; team screens show the tool,
    never the harness. Team-admins may change the tool: AFS snapshots the volume (kept 90 days) and starts the new tool empty.
    Buzz has no browser client and no REST API, so both its surfaces are N/A and fixed off.
  - **Graded exposure (OR-D4, OR-D5).** Each surface is `off`, `private` (internal ALB, corporate and peered networks) or
    `public` (internet ALB), within a per-team limit set by service admins, with separate kill switches per level. Both ALBs
    front the same `afs-edge`, which serves a surface only on the hostname of its effective level. New teams target limit
    `private`; environments without a private base domain seed `public` until the private path is built.
  - **Regrouped console (OR-D11).** The orchestration agent has its own page and card (one purple accent and ◆ mark used for
    nothing else); the shared agent configuration screen never shows tool settings, and the *Collaboration* tab never shows
    agent configuration.
  - **API shape (OR-D8, OR-D9, OR-D10).** A new `/orchestration` resource; `/collaboration` and the booleans stay as
    deprecated aliases with `Deprecation` and `Sunset` headers until 2.0.0; no new permission.
  - **Model access (OR-D13 to OR-D17).** Service, team and agent (or pool) each choose *all* (a live rule that follows the
    level above) or a fixed selection, plus one default model per agent. Service admins set the service and team levels;
    team-admins narrow per agent. The gateway admits service ∩ team ∩ agent and requires an approved price; a daily Bedrock
    sync adds only models the account can invoke (terms are accepted outside AFS). Upgrades keep 1.0.1 access; new installs
    start *all* everywhere.
- Consequences: one more pod per team (counted in its budget); `-db` 000022 renames a role, adds exposure, limit, tool and
  model access columns and tables, and keeps the 1.0.1 columns in step until 2.0.0 (database contract §7.3); a one-time
  backfill hook in `-restapi`; an internal ALB, private hosted zone and certificate in platform Terraform; API contract
  v1.4.0 (§4.4d) and gateway contract v1.1.0 (§2.1). Alternatives rejected: keeping the agent optional (teams without
  coordination), a CIDR allow list on the public ALB as "private" (still internet-facing), letting team-admins pick the
  harness (harness choice is a platform concern), and one model per agent (forces tickets for every task change).

## ADR-018 Team model gateway: a gateway per namespace, model routes and provider switches

- **Status:** Accepted (J, 2026-11-24; build approved 2026-11-25). **Built** in release 1.2.0 (merged 2026-11-25;
  tags pending J): `-db` PR #23, `-restapi` PR #11 and #14, `-cli` PR #12, `-website` PR #14 (merged a05f8ab).
- **Context:** Agents reach non-Bedrock models directly, unmetered and uncapped (EXT-6, RPT-7). J asked whether a
  namespace-scoped gateway fronting OpenAI-compatible endpoints by route name could track and cap their cost, and later
  for per-provider switches (Bedrock included) and Azure and Google as providers.
- **Decision:** Extend `afs-gateway` and run it per team namespace (opt-in per team, then ring by ring). Endpoints are
  a service → team → agent catalog with team opt-in; each has a route name delivered to agents as `AFS_LLM_*` variables
  and a file. Per-token routes use the Bedrock reserve-and-settle path and hard caps; capacity and free routes are metered
  and reported. Every provider has its own switch set by service admins; Bedrock can be turned off once a route model is
  the service default for every team. Azure and Google authenticate by workload identity federation from the team
  gateway's identity, so no provider secret is stored. Details: [model endpoint gateway PRD](../model-endpoint-gateway-PRD.md)
  §13.1 (MEG-D1 to MEG-D12); contracts: gateway v1.2.0, API v1.5.0, database v1.5.0 (000023).
- **Consequences:** Two small pods per team and a connection pooler in front of RDS; agents' traffic stays in their
  namespace; one team's gateway trouble stays in that team. Off-the-shelf gateways are not the enforcement point. Real
  EKS, Azure and Google checks wait for cloud access (fakes and recorded fixtures until then).
- **As built (1.2.0):** one binary in two modes (`--team-namespace`); the router is a mux of route families (Bedrock and
  Anthropic paths, `/r/<route>/`, `/openai/`, `/r/bedrock` with Chat Completions → Converse). Opt-in is per team through
  `PutTeamGatewaySettings` (`gateway_deployment = per_namespace`); teams on the shared gateway are unchanged and get no
  route variables. An endpoint's provider is derived from its host, so a switch cannot be bypassed by naming another
  provider. `AFS_LLM_ROUTES` leaves out Bedrock, which keeps its 1.1.0 variables. Azure and Google federation both use
  the gateway's projected Kubernetes token (one audience per pod); the PRD's AWS-signed variant for Google is not built.
  Billing runs four CronJobs (`route-pull`, `route-statements`, `route-capacity`, `route-price-sync`). The contracts
  record the build's decisions as API CD-53 to CD-60, database CD-61 to CD-66 and gateway CD-67, CD-68. Deferred: the
  Pod Identity association of each team gateway (Terraform per team for now), live Azure and Google federation and
  billing fixtures, OpenRouter past days, the reconciler writing credential status, and real-cloud tests
  ([PRD §16](../model-endpoint-gateway-PRD.md#16-built-and-deferred-120)). Child ADRs: `-restapi` ADR-031 to ADR-034.

## ADR-019 Governed MCP servers as a route type on the team gateway

- **Status:** Accepted (J, 2026-11-25; build approved 2026-11-25). Release 1.3.0.
- **Context:** Agents use MCP servers with no catalog, no review and no record of which tools they call. J asked for a
  central catalog of enterprise servers that teams opt into, team-managed servers that are still audited, telemetry by
  tool, resource and prompt, and search-style discovery, and asked how OIDC temporary credentials fit.
- **Decision:** MCP is a route type (`/mcp`, `/mcp/<server>`) on the per-namespace team gateway of ADR-018, not a
  separate proxy. Enterprise servers are published by service admins and switched on per team (opt-in, with a
  default-for-new-teams flag); team servers are registered by teams where allowed and approved under a three-level
  service policy (`team_all` default, `team_low_security_higher`, `security_all`). Policy narrows service → team →
  agent and a block anywhere wins. Every definition is pinned by an RFC 8785 digest and changes are held for review
  (per-server drift setting). The aggregated endpoint offers fixed meta-tools (`afs_search`, `afs_describe`,
  `afs_call`) over a BM25 index, because MCP 2026-07-28 has no normative search. The gateway mints or exchanges
  credentials per call (RFC 8693 federation, OAuth client, service-account OAuth, SigV4) and never passes a token
  through; agents' own CLIs get per-agent projected OIDC tokens and stay outside the gateway. Every request is a row in
  an append-only ledger with no content. Details: [MCP gateway PRD](../mcp-gateway-PRD.md) §14.1 (MCP-D1 to MCP-D9);
  contracts: gateway v1.3.0 §13, API v1.6.0 §4.14, database v1.6.0 §7.5 (000024).
- **Consequences:** MCP needs a team on a per-namespace gateway (CD-44). Hosted stdio servers run as pods with
  `afs-mcp-bridge`. The policy decision is a database function shared by API, reconciler and gateway (CD-51). Search
  quality is BM25 until embeddings are approved (MCP-OQ-6). Real EKS, IdP federation and hosted-image signing checks
  wait for cloud access (fakes and local tests until then).
- **Built (2026-11-25):** `-db` 000024 to 000026, `-restapi` 1.3.0 (PR #17: the MCP route, catalog, review, OAuth
  connect, agent and pool access, reconciler outputs and conditions, `afs-mcp-bridge`; ADR-035 to ADR-037 there),
  `-cli` 1.3.0 (PR #14, 54 commands). Build decisions: database CD-69, gateway CD-70 to CD-72.
