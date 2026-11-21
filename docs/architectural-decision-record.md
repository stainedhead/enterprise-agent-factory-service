# Architectural decision record

Cross-repo decisions. One entry per decision: context, decision, consequences. Status values:
Accepted, Proposed (needs review), Superseded.

## ADR-001 Wrapper root with four independent child repositories

- Status: Accepted (J, 2026-11-20)
- Context: the product has a database, a Go control plane, a Go CLI and a TypeScript SDK and console, with
  different toolchains, owners and release cadences.
- Decision: docs-only root `enterprise-agent-factory-service` plus `-db`, `-restapi`, `-cli` and
  `-website`, cloned inside the root and git-ignored by it. No submodules. The TypeScript SDK lives in
  `-website` as `packages/sdk` (a pnpm workspace package, publishable on its own). The reconciler, gateway
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
  `afs/agents/<namespace>/<agent>`. A dedicated agent can be linked to roles in other organization
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
  - **Ephemeral teams and budgeted POCs.** Teams carry `lifecycle` (`long_running` | `ephemeral`),
    `expires_at`, `teardown_on_budget_exhausted` and an optional lifetime budget; the reconciler tears
    them down when due.
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
  `role_bindings` stays without RLS (read through the API's own checks). Decisions D13–D21 in the root
  PRD record the detail.
