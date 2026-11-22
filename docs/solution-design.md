# Agent Factory Service: Solution Design

Status: Draft for review · 2026-11-20, aligned with the contracts 2026-11-21 · Owner: J (Enterprise Architecture) · Requirements: [initial PRD](../enterprise-agent-factory-service-initial-PRD.md)

The [contracts](contracts/README.md) are the single source for operation names, CLI and SDK names,
permissions, enums, events, the database interface and the gateway wire format. Where this document and
a contract disagree, the contract wins; this document explains the design behind them.

## 1. Purpose and scope

The Agent Factory Service (AFS) lets enterprise teams create and run their own **software factories**: isolated EKS namespace environments that host containerized teams of AI agents, with human teammates, secrets, identities, budgets and log delivery managed through one control plane. The "Agentic Teammates" project supplies the agent runtime (container images, agent CRDs/manifests). AFS supplies everything around it.

**Deliverables of this product (the software we build):**

| Deliverable | Tech | Notes |
|---|---|---|
| Control plane REST API | Go 1.27 | System of record API, RBAC enforced here |
| Reconciler (management plane automation) | Go 1.27 | Applies desired state from RDS to EKS/AWS, continuously |
| LLM gateway | Go 1.27 | Bedrock proxy that meters tokens and enforces hard caps |
| Billing ingestor | Go 1.27 | Daily CUR reconciliation and EKS split cost attribution |
| `afs` CLI | Go 1.27 | AWS CLI design conventions (own repo) |
| `@afs/sdk` accelerator SDK | TypeScript 7 | Typed wrapper over the REST API |
| Web management console | TypeScript 7, React | Clean architecture, consumes `@afs/sdk` |
| Datastore | RDS PostgreSQL 17 | Desired state, audit, usage ledger |
| Documentation | Markdown | This set, plus runbooks and OpenAPI |

**Toolchain confirmed on 2026-11-20:** Go 1.27.4 (latest 1.27 patch on proxy.golang.org) and TypeScript 7.0.2 (npm `typescript@latest`, the native Go-based compiler).

### 1.1 Capabilities and build order

All three capabilities are in scope for the feature-complete release (J, 2026-11-21). The order is the
build order only (PRD §9, milestones M0 to M6).

| Order | Capability | Built with |
|---|---|---|
| 1 | Long-running teams for development and maintenance | M0 to M4 |
| 2 | Short-term "swarm rentals" for one job with a hard cost cap | `teams.kind = ephemeral`, expiry, lifetime budget, teardown rule, pools and stages (§9); M5 |
| 3 | CVE remediation teams | security operators, swarm templates, `work_orders` with per-repository tracking and notifications, EventBridge intake (§9); M6 |

## 2. Requirements analysis

### 2.1 Functional requirements

| ID | Requirement | Source |
|---|---|---|
| F1 | Create, update, suspend, resume and delete teams. Each team maps to one isolated EKS namespace | J |
| F2 | Define the agents in a team (template/image, persona, model, resources, secrets). One agent is one pod | J |
| F3 | Manage human teammates and their role on the team | J |
| F4 | Manage agent identities (Kubernetes service account, AWS IAM role via Pod Identity, external identities such as a GitHub App installation) | J |
| F5 | Manage secrets as references to AWS Secrets Manager. Values are write-only through the API and never stored in or returned by AFS | J |
| F6 | Budgets per team with alert thresholds and a hard cap enforced in near real time | J |
| F7 | Budget and usage reporting: real time from the gateway, reconciled daily against CUR, including EKS compute | J |
| F8 | Log delivery configuration per team (CloudWatch, S3, OTLP, Splunk/Datadog via HEC/API) | J |
| F9 | Team configuration (allowed models, external systems, resource quotas) and non-secret configuration values at namespace and agent level | J |
| F10 | Four roles: service admin, team-admin, team viewer and security operator (service level, work orders only). Enforced in API, respected by CLI and web | J, security operator by Claude (D18) |
| F11 | Desired state stored in RDS PostgreSQL, versioned and audited. Exportable as a portable bundle and importable in another account or cluster | J |
| F12 | Reconciler applies stored state on startup and continuously, recovering from failure and reverting manual drift | J |
| F13 | Web console, CLI and SDK over one REST API | J |
| F14 | Ephemeral teams, swarm pools, work orders, event hooks and notifications (feature complete) | J |

### 2.2 Non-functional requirements

| Area | Requirement |
|---|---|
| Isolation | A team's agents cannot reach another team's pods, secrets, IAM permissions, logs or budget. Namespace + NetworkPolicy is the primary network boundary |
| Security | SSO via enterprise IdP (OIDC). Least privilege everywhere. No long-lived AWS keys. Secrets never in the DB or in logs |
| Auditability | Every mutation recorded with actor, time, request id and before/after. Append-only |
| Availability | API and gateway multi-AZ, 99.9%. Gateway outage must fail closed for spend (no unmetered calls) |
| Recoverability | RDS PITR (35 days) + cross-region snapshot copy. Full environment rebuild from DB in under 1 hour |
| Portability | Export bundle is versioned, checksummed, and holds no secret values |
| Cost | Spend enforcement lag under 1 request (pre-authorized reservation). Reporting freshness: real time (gateway), daily (CUR) |
| Scale (initial) | 200 teams; 5,000 concurrent agents and pool workers; 1,000 RPS sustained on the gateway, 2,000 peak (PRD §7) |

### 2.3 Assumptions and open questions

Decided by J on 2026-11-21 (PRD §10.1):

1. **IdP:** Okta (default) and Microsoft Entra ID, both OIDC with a groups claim, configured in `identity_providers` at service level only; when there is more than one, each team picks one (`teams.identity_provider_id`, NULL = the default) at creation or later. `users` are keyed by (issuer, subject), so one person can come from either.
2. **Cluster topology:** one shared EKS cluster per environment (dev/stage/prod). `teams.cluster_id` keeps a split possible; more than one cluster per environment is a non-goal of this release.
3. **Network policy engine:** Cilium (FQDN egress, Hubble flow logs).
4. **Agentic Teammates contract:** Kubernetes CRDs. The reconciler renders the Agentic Teammates custom resources for each agent.
5. **TypeScript runtime:** Bun 1.4 (installs, workspaces, scripts, tests, dev server; adopted in `-website`), Node.js 22 as the fallback. `tsc` 7 still type-checks; Biome still lints.
6. **Prices and the organization's hierarchy:** token and model prices drive budgets, so AWS Price List changes are proposed daily for service admins to approve, and CUR variance alerts above a threshold. AFS cannot see the organization's hierarchy; cost allocation tags carry it in (§7.4).
7. **Secrets and configuration in the pod:** zero impact on the container. Everything arrives as environment variables and files; the agent makes no calls (§6).
8. **Currency:** USD only.

Decisions made after the PRD review (D23 to D57) are in PRD §10.1 and ADR-015. Open technical questions,
with owners and defaults, are PRD §10.3 (OQ-1 to OQ-9).

## 3. Architecture overview

```
                    ┌──────────────── Enterprise IdP (OIDC) ────────────────┐
                    │                                                        │
  Browser ── Web console (TS7/React) ──┐                                     │
  Terminal ── afs CLI (Go) ────────────┼──► ALB ──► afs-api (Go) ◄── JWT ────┘
  Pipelines ── @afs/sdk (TS7) ─────────┘              │  RBAC, validation, audit
  Internet ── public ALB + WAF ──► afs-edge (SSO, authz, scan) ──► ns afs-t-<slug> Service paperclip:3100
                                                      ▼
                                       ┌────── RDS PostgreSQL ──────┐
                                       │ desired state · audit ·    │
                                       │ usage ledger · outbox      │
                                       └───┬──────────┬─────────┬───┘
                     LISTEN/NOTIFY + poll  │          │         │ outbox
                                           ▼          │         ▼
                          afs-reconciler (Go, leader) │    EventBridge ──► notifications
                            │  K8s API   │ AWS APIs   │                  (Slack/email/Jira/webhook)
                            ▼            ▼            │
        ┌──── EKS cluster ─────────────────────┐   IAM, Pod Identity, Secrets Manager,
        │ ns afs-t-payments  ns afs-t-search … │   Bedrock app inference profiles,
        │  agents (Agentic Teammates runtime)  │   CloudWatch/S3 log destinations
        │    │ pod identity (source IP)        │
        │    ▼                                 │
        │ ns afs-system: afs-gateway ──────┼──► Bedrock (via VPC endpoint)
        └──────────────────────────────────────┘        │ per-team inference profile
                                                         ▼
          afs-billing-ingestor ◄── CUR 2.0 (S3/Athena) ── daily reconciliation
```

### 3.1 Components

**afs-api (Go).** Stateless REST service behind an internal ALB. Validates OIDC JWTs, resolves the caller's role bindings, authorizes every request, writes desired state and an audit record in one transaction, and emits an outbox event. Never calls Kubernetes or AWS for mutating desired state; that is the reconciler's job. It does call Secrets Manager directly for write-only secret value operations so values never touch the DB.

**afs-reconciler (Go).** Single active replica via Kubernetes Lease leader election (two replicas for HA). On startup it performs a full reconcile of every resource; afterwards it reacts to `LISTEN afs_desired_state` notifications (payload `<table>:<team_id>:<id>`, sent by an AFTER trigger on every desired-state table from `-db` 000013), polls `generation <> observed_generation` every 30 seconds as a backstop for missed notifications, and runs a periodic full resync (default 10 minutes) to catch drift (D30). It also opens each budget period's spend counter (`afs.ensure_spend_counter`, emitting `budget.reset`), releases expired spend reservations every minute (`afs.release_expired_reservations`), clears expired ceiling overrides (lowering a budget above the base ceiling and emitting `budget.ceiling_override_expired`), and drops usage, activity and traffic partitions older than 13 months (`afs.drop_partitions_older_than(13)`) (D31, D34, D36). For each team it converges:

- Namespace `afs-t-<slug>` with labels `afs.io/team-id`, Pod Security Admission `restricted`.
- `ResourceQuota`, `LimitRange`.
- `NetworkPolicy` default deny all ingress/egress, then allow DNS and egress to `afs-gateway`. Per agent, a `CiliumNetworkPolicy` (selected by the `afs.io/agent-id` pod label) allows `toFQDNs` egress to the endpoints of every external system in `agent_external_access` with `disabled_at IS NULL` (service catalog entries that are on, minus team and agent opt-outs, plus the team's declared systems). Ports default to 443. Policy changes apply to running pods without a restart. Denied egress is logged through Hubble. Secrets whose `external_system_id` is off for an agent are left out of that agent's ExternalSecret.
- ServiceAccounts per agent, EKS Pod Identity associations to the team's IAM role. Pod Identity sets its own session tags (`kubernetes-namespace`, `kubernetes-service-account`, `kubernetes-pod-name`, `eks-cluster-name` and others) and cannot add custom ones, so team and agent ids are tags on the roles (D26, OQ-1).
- One StatefulSet with exactly one replica per agent (stable name, ServiceAccount and IAM session). There is no replica count: a team scales by adding agents.
- One ConfigMap per agent (`agent-<name>-config`) holding its resolved configuration values (`afs.agent_config_resolved`), loaded with `envFrom` and mounted read-only at `/etc/afs/config` (one file per name). A change to a namespace value re-renders every ConfigMap that links to it and rolls those agents (a pod-template hash annotation), because environment variables only change on restart. A ConfigMap edited by hand is restored.
- One persistent volume per agent from the StatefulSet's `volumeClaimTemplate` (EBS CSI, encrypted, `WaitForFirstConsumer`, tagged `afs-team-id` and `afs-agent-id`), mounted at `/var/lib/agent`. The StatefulSet's PVC retention policy is `Retain` for both scale-down and delete, so pausing or re-creating the StatefulSet never loses data; the reconciler alone deletes a volume, following the agent's on-delete rule. Snapshots are EBS snapshots through CSI `VolumeSnapshot`, taken on the agent's schedule, pruned to its retention count, and recorded in `agent_volume_snapshots`. The team's `ResourceQuota` includes `requests.storage`.
- IAM role `afs-<team id>` under path `/afs/<namespace>/`, tagged `afs-team-id` and `afs-team-slug`, with an ABAC policy whose conditions use `aws:PrincipalTag/afs-team-id` (from the role tag) and `aws:PrincipalTag/kubernetes-namespace` (from the Pod Identity session), and a permissions boundary `afs-<team id>-boundary` that allows `sts:AssumeRole` and `sts:TagSession` only on `arn:aws:iam::<account>:role/*` for the organization accounts matching the team's allowed-accounts filter. The boundary is re-rendered when the filter or the organization account list changes.
- A dedicated IAM role `afs-<agent id>` (path `/afs/<namespace>/`, tags `afs-team-id`, `afs-agent-id`, `afs-agent-name`) for each agent whose `iam_identity` is `dedicated`, with the team's boundary attached and its own Pod Identity association. Roles are named by immutable id, so two teams can each have an agent called `reviewer` and names stay under IAM's 64-character limit (D25). For each of the agent's cross-account links, an inline statement grants `sts:AssumeRole` and `sts:TagSession` on that exact role ARN. A Secret-free AWS config file (`agent-<name>-aws`) is mounted at `/etc/afs/aws/config` with `AWS_CONFIG_FILE` set, holding one profile per link (`role_arn`, `external_id`, `credential_source = EcsContainer`, `duration_seconds`, `role_session_name = <agent id>`), so the agent runs `aws --profile <name>` or the SDK equivalent.
- The AWS Organizations account list, mirrored hourly into `org_aws_accounts` (id, name, status). Each link is verified by assuming its role with the agent's identity on creation, daily and on demand; the result (`pending_trust`, `verified`, `failed`) is written to `agent_role_links`. Links whose account falls outside the filter or is suspended are set to `disabled` and removed from the agent's grants and profile file.
- Bedrock application inference profile per (team, model) with cost allocation tags.
- ExternalSecret (External Secrets Operator) objects that project referenced Secrets Manager entries into the namespace.
- Agent workloads rendered as Agentic Teammates custom resources (CRD).
- Log delivery (Fluent Bit output per team or CloudWatch subscription filters).

It records `observed_generation`, phase and conditions per resource in `resource_status`, which the API and UI display. Drift (live state differs from desired) is corrected and logged as an audit event with actor `system:reconciler`. Deletes use an ordered finalizer flow: scale agents to zero, apply each agent's on-delete rule to its volume (final snapshot, then delete or retain), schedule secrets for deletion (30-day recovery window), delete EFS access points, SQS inboxes, the dedicated NodePool and EKS access entries, revoke IAM, delete inference profiles, delete namespace, mark row `deleted`. Suspend scales to zero and attaches the Bedrock deny but keeps everything else. The full per-resource table is PRD TEAM-9.

Volume drift is handled like any other: a volume smaller than desired is expanded (online, EBS supports it); a PVC that is missing is re-created from the agent's latest completed snapshot when one exists (empty otherwise) and raises an alert; a volume bigger than desired, or of another storage class, is reported as a condition rather than changed, because EBS cannot shrink and a class change needs a data migration. EBS volumes live in one Availability Zone, so an agent reschedules within its volume's zone; moving it to another zone is a restore from snapshot.

**afs-edge (Go).** The only component reachable from the internet, added by the Paperclip team collaboration change ([PRD](../paperclip-team-collaboration-PRD.md), PC-D1, ADR-016). Runs in `afs-system`, multi-AZ, at least 3 replicas, behind one internet-facing ALB (platform Terraform) with an ACM certificate for `<collab.base_domain>` and `*.<collab.base_domain>` (Route 53 has an apex record and the wildcard; only the apex `/oauth2/callback` is served there) and an AWS WAF web ACL (managed rule groups, a per-IP rate rule, an optional corporate CIDR allow list). It maps the request's host (`<team-slug>.<collab.base_domain>`) to a team through the route table (`afs.collab_routes()`, refreshed on the change feed and every 30 seconds), signs people in with OIDC code + PKCE against the team's own provider (one fixed callback on the apex, a single-use handoff, and a host-only `__Host-afs-collab` cookie per team host that holds only an opaque session id; sessions live server-side in the database), authorizes every request with the same `internal/authz` code and role bindings as `afs-api` (`collaboration:access` for `GET` and `HEAD`, `collaboration:contribute` for everything else, decisions cached at most 60 seconds), accepts REST callers on `X-Afs-Authorization`, scans request bodies for credential patterns, limits and records access, and forwards to that team's `paperclip` Service (port 3100) and nothing else. It connects to the database as `afs_edge`, which can only execute ten `SECURITY DEFINER` functions (routes, settings, principals, access counts, one event, sessions and handoff), and uses Pod Identity for its AWS calls. It refuses any `Host` that is not the apex or a known team host (the ALB terminates TLS, so there is no SNI check). Its records go to stdout as JSON with `afs.team_id`, and the node log collector routes them to the team's log delivery like agent sign-ins. It never stores or logs Paperclip content. Externally visible behaviour: [API contract §4.4c](contracts/api-contract.md).

The reconciler gains, for a team with a collaboration agent only: the ClusterIP Service `paperclip` and Paperclip's environment and secret-provider settings on that agent's pod; an egress rule from each connected agent to the Paperclip pod on TCP 3100 and an ingress policy on that pod admitting only those agents, `afs-edge` and the reconciler; the admission additions of §4; and, in `managed` registration, the Paperclip roster, key and secret scans.

**afs-gateway (Go).** The only path from agents to Bedrock. Runs in `afs-system`, multi-AZ. The wire interface is the [gateway contract](contracts/gateway-contract.md) (D28).

1. Agent calls a Bedrock Runtime compatible path (`POST /model/{modelId}/converse`, `/converse-stream`, `/invoke`, `/invoke-with-response-stream`) or the Anthropic Messages compatible `POST /anthropic/v1/messages`, using its standard SDK. The pod gets `AFS_GATEWAY_URL`, `AWS_ENDPOINT_URL_BEDROCK_RUNTIME`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY=afs-gateway` (a placeholder, not a secret) and the gateway's CA (`/var/run/secrets/afs/gateway/ca.crt`, named in `AWS_CA_BUNDLE`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE` and `NODE_EXTRA_CA_CERTS`), so standard SDKs need no change.
2. Gateway identifies the caller by its source pod IP, mapped through the Kubernetes API and Cilium endpoint identity to namespace, service account and pod, hence `team_id`, `agent_id` or `pool_id`, and the worker pod. Cilium lets only team pods reach the gateway, binds each IP to its endpoint identity and encrypts node-to-node traffic with WireGuard, so the source cannot be spoofed. The SigV4 `Authorization` header and `ANTHROPIC_API_KEY` are ignored. A projected token (audience `afs-gateway`, `/var/run/secrets/afs/gateway/token`) is optional defence in depth: when sent it is checked with TokenReview and must name the same pod, else `401` (D57).
3. Gateway checks the model is allowed for the team, opens the period if needed (`afs.ensure_spend_counter`), then **reserves** the worst-case cost (`maxTokens` from the request, else `models.max_output_tokens`, × output price, plus request bytes ÷ 3 × input price) with `afs.reserve_spend_held`. If it returns NULL the request is rejected with `402 BudgetExceeded`, which SDKs do not retry. If the database cannot be reached it fails closed with `503 Unavailable`.
4. Gateway assumes the team's Bedrock role (`afs-<team id>-bedrock`) with session tags and invokes the team's application inference profile, adding the agent's tags as `requestMetadata` (at most 16 pairs, D27).
5. On response (or stream end) it settles with `afs.settle_reservation` to the actual token cost and writes a `usage_events` row (batched). A reservation never settled expires after `gateway.reservation_ttl_seconds` (default 900) and the reconciler releases it (D31).

Agents' own Pod Identity role has **no** `bedrock:*` permissions, so the gateway cannot be bypassed. When a hard cap is reached, the reconciler also attaches an explicit-deny inline policy to the team's Bedrock role (the IAM kill switch), so even a gateway bug cannot overspend. The deny is removed on budget reset or increase.

At higher scale the spend counters move to ElastiCache (Redis/Valkey) with Postgres as the durable ledger; the interface is designed for that swap.

**afs-billing-ingestor (Go).** Daily job. Reads CUR 2.0 (with EKS split cost allocation enabled) via Athena, attributes Bedrock cost by the `afs-team-id` cost allocation tag on inference profiles and EKS compute by namespace, writes `cost_daily` and `cost_reconciliations` (gateway estimate vs. billed actual, variance). Variance over `billing.variance_alert_pct` (default 5%) raises an alert to service admins. The billing job proposes price changes from the AWS Price List for approval; it never adjusts the catalog itself (BUD-9).

**Event outbox and notifications.** Every mutation writes an `outbox_events` row in the same transaction. A publisher (inside the reconciler process) sends them to an EventBridge bus `afs-events` with at-least-once delivery. The reconciler reconciles each row of `notification_channels` into one EventBridge rule plus target: an API destination for Slack, Jira and webhooks, SES for email (D46). Work order events (the `work_order.*` list of [API contract §7](contracts/api-contract.md#7-events-eventbridge-from-the-outbox): `created`, `assigned`, `repo_updated`, `pr_opened`, `merged`, `sla_warning`, `sla_breached`, `completed`, `failed`, `cancelled`) use the same path to notify owning teams (§9).

## 4. Multi-tenancy and isolation

| Layer | Control |
|---|---|
| Network | Namespace per team. Default-deny `NetworkPolicy` for ingress and egress (two named exceptions for Paperclip, below). Only DNS, gateway and the endpoints of the external systems each agent may use (service catalog → team → agent, each level only narrowing). No cross-namespace traffic. Admission policy (ValidatingAdmissionPolicy by default; Kyverno is the alternative, OQ-6) blocks teams from creating their own NetworkPolicies, Services of type LoadBalancer/NodePort, or hostNetwork pods (and, since the collaboration change, Ingress and Gateway API objects, `externalIPs`, `loadBalancerSourceRanges` and any Service that selects the collaboration pod other than the reconciler's `paperclip` Service) |
| Compute | Pod Security Admission `restricted`. ResourceQuota/LimitRange. Optional dedicated Karpenter NodePool per sensitivity tier (taints + tolerations) for teams needing node-level isolation |
| Kubernetes API | Agents' service accounts get no Kubernetes RBAC by default (`automountServiceAccountToken: false`; only the optional projected gateway token and, for work order reporting, the `afs-api` token are mounted). Humans have no kubectl access by default; team viewers can optionally get read-only via EKS access entries scoped to their namespace |
| AWS IAM | One IAM role per team, ABAC by the `afs-team-id` role tag and the Pod Identity `kubernetes-namespace` session tag. Secrets, S3 prefixes, log groups and inference profiles are all tagged with the team id, and the policy only matches its own tag |
| Secrets | Secrets Manager name set by AFS, never by users: `<service>/<namespace>/<agent-name>/<secret-name>` or `<service>/<namespace>/_shared/<secret-name>` (§6). IAM uses prefix rules on that path, with tag `afs-team-id` as a second check. KMS key per environment with an encryption context of team id |
| Data (AFS DB) | Every team-scoped table has `team_id`. API authorization filters on it. PostgreSQL row-level security as defense in depth (`afs.team_ids`, `afs.service_admin`, `afs.security_operator` session settings, database contract §3) |
| Spend | Separate inference profile, budget, counters and IAM deny per team |
| Logs | Separate log group / S3 prefix / destination per team |
| Public ingress | One AFS-owned entry: internet-facing ALB with WAF to `afs-edge` in `afs-system`. Teams own no load balancer, Ingress or route. The edge decides access per request with AFS role bindings and the team's own provider, forwards only to the team's `paperclip` Service, and strips AFS credentials. Per-team and service-wide kill switches (`mayExposeCollaboration`, `collab.public_endpoints`); no team namespace is reachable from outside except through it |

### 4.1 Exceptions for Paperclip collaboration

Team namespaces keep default deny; these are the only openings, all rendered by the reconciler, never by a team:

- **TEAM-3.** Egress from each *connected* agent to the Paperclip pod on TCP 3100 in the same namespace, and an ingress policy on the Paperclip pod that admits only connected agents of the same namespace, `afs-edge` pods and the reconciler. Unconnected agents and every other namespace stay denied. Paperclip never initiates a connection to another agent (pull only, PC-D5).
- **TEAM-4.** Admission policy still refuses what teams could use to publish. Only the reconciler may create the one `paperclip` ClusterIP Service in a team namespace; isolation tests prove a team cannot publish anything, including a second Paperclip.
- **Encryption in transit (PC-D7).** Paperclip serves plain HTTP, so the hops from `afs-edge` and from agents to Paperclip are HTTP inside Cilium's WireGuard transparent encryption and the namespace policy. This is the one recorded exception to the root PRD's rule that every hop is TLS; TLS 1.2+ holds from the internet to the ALB and from the ALB to `afs-edge`.
- **One identity.** The collaboration pod runs the Paperclip server and its Hermes orchestrator as one AFS agent: one ServiceAccount, IAM role, gateway identity, volume and audit trail (PC-D3).

Namespace isolation shares the kernel. That is acceptable for internal enterprise tenants; the dedicated-NodePool option exists for teams that handle regulated data, and gVisor/Kata runtime classes are a non-goal of this release.

## 5. Identity and access

### 5.1 Human identity

OIDC Authorization Code + PKCE for the web console; OIDC device authorization grant for the CLI (`afs sso login`); short-lived API keys (hashed in DB, max 90 days, scoped to one team and role) for pipelines. The API validates JWTs against the IdP's JWKS and maps `sub` to a `users` row (just-in-time provisioning on first login). A token is accepted from any enabled service-level provider; for a team-scoped request, a group binding counts only if the token came from that team's provider (`teams.identity_provider_id`, or the default when unset). Service-level group bindings (service admins) name the provider their group comes from. `ListSignInProviders` returns each provider's `consoleClientId` and public `cliClientId` (D48).

Agents and pools that report work order progress call `afs-api` with a second projected token (audience `afs-api`, `/var/run/secrets/afs/api/token`); `afs-api` validates it offline against the cluster's OIDC issuer JWKS (audience `afs-api`; no TokenReview, because `afs-api` never calls Kubernetes) and treats it as a *workload* principal that holds only `work-orders:report` on its own team's work orders, plus `GetMe` (D29).

### 5.2 Roles

| Role | Scope | Summary |
|---|---|---|
| `service_admin` | Global | Everything, including service settings, model catalog and pricing, creating/deleting teams, all teams' data, export/import, audit |
| `team_admin` | One team | Manage that team's agents, members, budgets (within the limit a service admin set), identities, secrets, configuration, log delivery, notification channels |
| `team_viewer` | One team | Read that team's configuration, status, usage and audit. Secrets show name, description and reference metadata, never values |
| `team_collaborator` | One team | Everything `team_viewer` can read, plus write in the team's Paperclip (`collaboration:contribute`) and use its REST API (`collaboration:api`), with no right to change AFS configuration (PC-D6) |
| `security_operator` | Global, work orders only | Create, cancel and read every work order and its progress; list and describe swarm templates; look up the team directory; no team access (`403` on every team route). Also held by service-level API keys for security tooling |

Role bindings can be granted to a user or to an IdP group (`subject_type = group`, matched on the `groups` claim), so enterprises manage membership in the IdP. A person can hold different roles on different teams. Budget **ceilings** (`max_budget_usd`) are set by service admins; team admins set budgets up to that ceiling.

### 5.3 Permission matrix

This is a summary by action. The authoritative catalog, with permission names and the security operator
column, is [API contract §3](contracts/api-contract.md#3-permission-catalog).

| Action | service_admin | team_admin | team_viewer |
|---|:-:|:-:|:-:|
| Create / delete team | ✓ | | |
| Update team settings (quotas are service admin only) | ✓ | ✓ | |
| External systems catalog: custom systems, service-level switch, allow a team to declare systems | ✓ | | |
| External systems: turn off for team or agent; declare team systems when allowed | ✓ | ✓ | |
| View effective external system access | ✓ | ✓ | ✓ |
| Suspend / resume team | ✓ | ✓ | |
| View team, status, events | ✓ | ✓ | ✓ |
| Create / update / delete agents, pause, restart, snapshot, expand volume (no scale: one agent is one pod) | ✓ | ✓ | |
| View agents | ✓ | ✓ | ✓ |
| Add / remove members, change roles | ✓ | ✓ (cannot grant service_admin) | |
| View members | ✓ | ✓ | ✓ |
| Create / rotate / delete secrets, bind to agents | ✓ | ✓ | |
| View secret metadata (never values) | ✓ | ✓ | ✓ |
| Manage agent identities | ✓ | ✓ | |
| Set a team's allowed AWS accounts | ✓ | ✓ (when the team manages its own accounts) | |
| Choose the team's sign-in provider (from the service's providers) | ✓ | ✓ | |
| Identity providers, service tags (fixed and required keys) | ✓ | | |
| Team tags: set required values, add own tags | ✓ | ✓ | |
| View a team's tags; reports grouped by tag (own teams) | ✓ | ✓ | ✓ |
| Approve or reject model price changes | ✓ | | |
| Add / remove / verify agent cross-account role links | ✓ | ✓ | |
| View allowed accounts, role links, trust policies | ✓ | ✓ | ✓ |
| Set budget (≤ ceiling), thresholds | ✓ | ✓ | |
| Set budget ceiling, temporary ceiling override (D34), `onExhaust: notify` for persistent teams (D33) | ✓ | | |
| View usage, cost, reconciliation | ✓ | ✓ | ✓ |
| View service-wide reports (all teams) | ✓ | | |
| View team and agent reports, export CSV | ✓ | ✓ | ✓ |
| Manage scheduled reports (D23) | ✓ | ✓ | |
| Manage log destinations, notification channels | ✓ | ✓ | |
| Issue and view team API keys (viewers do not see them, D50) | ✓ | ✓ | |
| View audit log (team) | ✓ | ✓ | ✓ |
| Service settings, model catalog, pricing | ✓ | | |
| Export / import bundles | ✓ | | |
| Set isolation tier, switch on viewer kubectl | ✓ | | |
| Create / scale / pause / delete pools and stages (ephemeral teams) | ✓ | ✓ | |
| View pools, stages, workers | ✓ | ✓ | ✓ |
| Swarm templates | ✓ | | |
| Create / cancel work orders, view all (also `security_operator`) | ✓ | | |
| View work orders assigned to or touching own team | ✓ | ✓ | ✓ |
| Report repository progress on an assigned work order | ✓ | ✓ | |
| Issue service-level security operator API keys | ✓ | | |
| Open the team's Paperclip through the public endpoint, read-only (`collaboration:access`; also `team_collaborator`) | ✓ | ✓ | ✓ |
| Write in Paperclip and use its REST API (`collaboration:contribute`, `collaboration:api`; also `team_collaborator`) | ✓ | ✓ | |
| Create the collaboration agent, switch the web UI and REST API, connect agents, rotate Paperclip keys | ✓ | ✓ | |
| Allow or forbid public collaboration per team (`mayExposeCollaboration`) and service-wide (`collab.*` settings) | ✓ | | |

Each action is a named permission (e.g. `agents:write`, `secrets:read-metadata`). The API's route table declares the permission for each route; one authorization function `Authorize(principal, permission, teamID)` is the only place decisions are made. `GET /v1/me` returns the caller's bindings and effective permissions per team so the CLI and web can hide or disable actions. **The client-side check is UX only; the API is the enforcement point.**

### 5.4 Agent identity

Each agent gets a Kubernetes ServiceAccount `agent-<name>` in its team namespace. Identities are modeled explicitly in `agent_identities`:

- `k8s_service_account` (always), used for gateway authentication.
- `aws_iam_role` via EKS Pod Identity. Default: the shared team role (`agents.iam_identity = 'team_shared'`). Option: a dedicated role `afs-<agent id>` under path `/afs/<namespace>/` (`'dedicated'`), with the team's permissions boundary, for least privilege and for cross-account access.
- Cross-account role links (`agent_role_links`, dedicated agents only): a target role ARN in another organization account, a profile name, a maximum session and an AFS-generated external ID. The account must match the team's allowed-accounts filter (`teams.allowed_aws_accounts`, glob patterns over account ids and names; `*` for every account), which service admins set. The filter is enforced three times: in the API, in the database (`afs.account_allowed`, by trigger) and in IAM (the team's permissions boundary). AFS shows the target account owner this trust policy:

  ```json
  {
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::<afs-account>:role/afs/<namespace>/afs-<agent id>" },
    "Action": ["sts:AssumeRole", "sts:TagSession"],
    "Condition": { "StringEquals": { "sts:ExternalId": "<external-id>", "aws:PrincipalTag/afs-team-id": "<team-id>" } }
  }
  ```

  Glob patterns, not regular expressions, because IAM policies match ARNs with wildcards only, so the same pattern can be checked in SQL and rendered into the boundary.
- Swarm pools (`agent_pools`) have their own ServiceAccount `pool-<name>`, a dedicated IAM role `afs-<pool id>` (path `/afs/<namespace>/`, tags `afs-team-id`, `afs-pool-id`, `afs-pool-name`) with the team's permissions boundary, and optional GitHub or external identities, all shared by the pool's workers (a Deployment). A pool can use a shared named role (`pool_role_links`): one role name deployed to one or many organization accounts (typically by a CloudFormation StackSet) that trusts the pool's role, with one profile per account. The same filter applies. Workers' sessions carry Pod Identity's own session tags, including `kubernetes-pod-name`; team and pool come from the role tags (D26).
- `github_app` installation or other external identity (e.g. a bot account in Jira), credentials held as a referenced secret.

CloudTrail attributes every agent call through the role (name and `afs-team-id` / `afs-agent-id` tags) and Pod Identity's session tags; in linked accounts through the role and the `role_session_name` set to the agent id (D26, D51).

## 6. Secrets management

- AFS stores **references only**: ARN, version stage, rotation settings, description. Never the value.
- **One creation mode.** The API takes a scope (team-shared or one agent), a name, a description and the value. It creates the secret in Secrets Manager under the managed path, writes the value (`CreateSecret` / `PutSecretValue`), discards it, and stores the ARN. Registering an arbitrary existing ARN is not supported, because it would bypass the hierarchy.
- **Managed hierarchy.** The Secrets Manager name is always `<service>/<namespace>/<agent-name>/<secret-name>`, `<service>/<namespace>/<pool-name>/<secret-name>` for pool secrets, or `<service>/<namespace>/_shared/<secret-name>` for team-shared secrets. `<service>` is the installation prefix (service setting `secrets.path_prefix`, default `afs`), and `<namespace>` is `afs-t-<slug>`. The database computes the path (`afs.secret_path`, with a 4-argument form for pool secrets) and rejects an ARN that does not match it. Team slug, agent name and secret name are immutable, so a path never changes. `_shared` cannot collide with an agent name, because agent names start with a letter.
- **Access by prefix.** `afs-api` may create and write values only under `<service>/*`. The team's External Secrets store reads `<service>/<namespace>/*`. A per-agent IAM role (AGT-6) reads `<service>/<namespace>/<agent-name>/*` and `<service>/<namespace>/_shared/*`; a pool's role reads `<service>/<namespace>/<pool-name>/*` and `_shared/*`. No human role reads values.
- Values are write-only. There is no read-value endpoint. The API returns `lastChangedAt`, `versionId` and rotation status.
- Bindings (`agent_secret_bindings`) say which agent receives which secret as an env var or file. A team-shared secret can be bound to any agent of the team; an agent secret only to its own agent (enforced in the database). The reconciler renders ExternalSecret objects; External Secrets Operator syncs them using the team's IAM role, so a team's ESO access is limited by ABAC to its own secrets.
- Rotation: Secrets Manager rotation Lambdas where applicable; ESO refresh interval 1h; a rotate action triggers a rolling restart of bound agents.
- **Zero impact on the container (SEC-6).** The agent needs no code, SDK, sidecar or call to receive anything. Each binding's ExternalSecret produces a namespace Secret that the pod template references: `env[].valueFrom.secretKeyRef` for env-var bindings and a projected volume item at the chosen path for file bindings. Configuration values come from the agent's ConfigMap (`envFrom` plus `/etc/afs/config`), cross-account profiles from `/etc/afs/aws/config`, tags from `/etc/afs/tags.json` and `AFS_TAGS`. The pod template carries a hash of every referenced value's version, so any change rolls the agent and environment variables never go stale. The Secrets Store CSI Driver (reading with the agent's own Pod Identity, nothing stored in the cluster) is an accepted alternative that would not change the container's view; an in-namespace endpoint for on-demand reads is a non-goal (PRD §3).

## 7. Budgets and cost

### 7.1 Model

- `budgets`: per team; `period` = `monthly` | `lifetime` (ephemeral teams); `amount_usd`; `thresholds` (default 50/80/100); `on_exhaust` = `block` (default) | `notify`; optional `expires_at`. `notify` is allowed only on persistent teams and only set by service admins (D33).
- Ceiling: `teams.max_budget_usd`, plus an optional temporary `ceiling_override_usd` with `ceiling_override_expires_at` set by service admins; `afs.team_ceiling(team)` returns the one in force (D34).
- `model_prices`: price per 1M input/output tokens per Bedrock model, effective-dated, maintained by service admins.
- `model_price_proposals`: `afs-billing` reads the AWS Price List daily (setting `pricing.price_list_sync`) and proposes each changed price; a service admin approves (a `model_prices` row is written, effective from its date or the approval, whichever is later) or rejects. One pending proposal per model.
- `spend_counters`: one row per budget period: `spent_usd`, `reserved_usd`. Hot path for the gateway. Opened on demand by `afs.ensure_spend_counter` (gateway) and at period start by the reconciler, which emits `budget.reset` (D31).
- `spend_reservations`: one row per held reservation with `expires_at` (`gateway.reservation_ttl_seconds`, default 900); released by the reconciler if never settled.
- `usage_events`: append-only ledger, partitioned by month.
- `cost_daily`: daily rollup by team/agent/model and source (`gateway` estimate, `cur` billed, `eks_compute`).

### 7.2 Enforcement path (near real time)

Reserve → invoke → settle, as in section 3.1. Thresholds emit `budget.threshold_crossed` events once per period per threshold. At 100% with `block`, the gateway rejects calls with `402 BudgetExceeded` and the reconciler applies the IAM deny; the team and its agents stay `Ready` with condition `BudgetExhausted=True` (D24). Agents receive a structured, non-retryable error ([gateway contract](contracts/gateway-contract.md) §7) and the Agentic Teammates runtime can pause gracefully.

### 7.3 Reporting

- Real-time view: from `spend_counters` and `usage_events` (seconds).
- Daily reconciled view: from CUR via the ingestor, including EKS compute (split cost allocation by namespace) and any non-gateway spend.
- Showback/chargeback export by cost center or any tag (CSV via API).
- Variance: `cost_reconciliations` flags a team-day `over_threshold` when gateway and billed figures differ by more than `billing.variance_alert_pct` (default 5); `afs-billing` emits `cost.variance_detected`.
- **Credential hygiene.** Agent logs pass through a Fluent Bit redaction filter before delivery: values that look like passwords, tokens or keys, and the values of the agent's bound secrets (loaded as hashes, never as plaintext), are replaced with `[redacted:<8-char hash prefix>]`. Connections to a system's sign-in endpoints are written to the team's log delivery as `agent.external_login` events (agent or pool worker, system, time); they are not stored in the database (D17).
- **Agent activity.** An activity collector in `afs-reconciler` writes one `agent_activity` row per running agent every five minutes. It combines the window's `usage_events` (model calls, tokens, cost), the agent's status endpoint (the Agentic Teammates runtime reports busy or idle and a short note of what it is doing), pod CPU and memory from the metrics API, and the pod's phase. *Working* = any model call, a busy report, or CPU above `reports.idle_cpu_millicores` (service setting, default 50). Paused, stopped, unhealthy and budget-blocked agents are recorded as such. `agent_activity_daily` gives time in state and utilization; `agent_activity_current` gives the current state and `idle_since`.
- **External traffic.** A traffic collector reads Cilium Hubble flow logs (L3/L4 flows with the DNS name each connection was for, and the policy verdict) and writes `external_traffic` rows per agent, host and verdict every five minutes, matched to the agent's external systems. Where an egress proxy terminates HTTP for a system, it adds request and error counts. Denied flows record the reason (system off at service, team or agent level, or not in the catalog), and more than `egress.denied_spike_threshold` (default 20) denials from one agent or pool in 5 minutes raises an `egress.denied_spike` event. No egress proxy is part of this release (OQ-8), so v1 reports connections and bytes only.
- **Report API.** `GET /v1/reports/{usage|costs|activity|traffic}` (service admins, all teams) and `GET /v1/teams/{teamId}/reports/{…}` and `GET /v1/teams/{teamId}/agents/{agentId}/reports/{…}` take `from`, `to`, `groupBy` (team, agent, model, system, day, hour) and filters, and returns JSON or CSV (`Accept: text/csv`). Queries read the daily views for ranges over two days and the five-minute tables otherwise. Scheduled reports (`report_schedules`) are created by team-admins and service admins only (`reports:schedule`, D23; viewers run reports on demand) and delivered by `afs-billing` as CSV to one of the team's own notification channels (D13). External traffic is reported as counts and bytes; AFS attaches no cost to external services (D14).
- **By tag, as it was.** Every `usage_events`, `cost_daily`, `agent_activity` and `external_traffic` row carries a `tag_set_id`: an immutable per-team snapshot of the team's service and team tags when the row was written (`afs.current_team_tag_set(team)`, cached by writers and refreshed on `team.tags_changed`). CUR lines map to tag sets built from the tags AWS billed with. `cost_daily_by_tag`, `agent_activity_daily_by_tag` and `external_traffic_daily_by_tag` roll figures up by those snapshots, so a tag change affects later figures only (D20); the report API takes `groupBy=tag:<key>` and `tag.<key>=<value>` filters.
- Activity and traffic tables are partitioned by month (`afs.ensure_activity_partition`, `afs.ensure_traffic_partition`); five-minute rows and usage events are kept 13 months and then dropped by the reconciler (`afs.drop_partitions_older_than(13)`), daily rollups indefinitely. `audit_log` is never deleted in this release (D36, OQ-4).

### 7.4 Cost allocation tags

- **System tags** `afs-team-id` and `afs-agent-id`: set by AFS, never configurable, on every resource and Bedrock call.
- **Service tags** (`service_tags`): *fixed* (one value for all teams) or *required* (each team supplies a value, optional allowed list and default). A new team must supply required keys without a default in the creating transaction (deferred constraint trigger).
- **Team tags** (`team_tags`): required values plus optional keys of the team's own; the effective set (system, service and team tags) is at most 40 keys, leaving room under AWS's 50 for tags the EBS CSI driver adds (D27).
- `team_effective_tags` / `agent_effective_tags` are what the reconciler applies (IAM roles, EBS volumes and snapshots, application inference profiles, Secrets Manager secrets, via `TagResource` on change) and what the gateway sends as Bedrock `requestMetadata` on each call (at most 16 pairs: system tags, then service fixed and required, then team tags in key order; cached per agent, refreshed on `team.tags_changed`). Pods get `/etc/afs/tags.json` and `AFS_TAGS`. CUR sees the keys once service admins activate them as cost allocation tags. `afs-billing` records daily which keys CUR has seen and their activation status (`cost_allocation_tag_status`), and S9 shows a one-time activation notice until a service admin acknowledges it by setting `billing.tag_activation_acknowledged` to `true` (`PutSetting`; TAG-7).

## 8. Desired state, versioning and portability

- Every desired-state row has `version` (optimistic concurrency, exposed as `ETag`/`If-Match`) and `generation` (incremented on spec change). The reconciler writes back `observed_generation`.
- `config_revisions`: a trigger snapshots every change to versioned tables (who, when, full JSON), giving history and rollback ("restore revision N").
- `audit_log`: append-only (UPDATE/DELETE revoked from the app role and blocked by trigger).
- **Backups:** RDS automated backups with PITR, daily snapshot copied cross-region and cross-account (AWS Backup vault with vault lock).
- **Export bundle:** `POST /v1/exports` asks the reconciler to produce a versioned, SHA-256-checksummed JSON (or YAML) document with `schemaVersion`, all teams, agents (including volume settings and configuration values), namespace configuration values, agent IAM identity and cross-account links with their external IDs, each team's allowed-accounts filter, the external systems catalog, team-declared systems and opt-outs, members, bindings, budgets, configuration, secret *references* and each agent's latest volume *snapshot reference*. Import can restore volumes from those snapshots once they are shared with or copied to the target account and region. The reconciler writes it to S3 and stores a pre-signed download URL on the export row; `afs-api` never touches S3 (D49).
- **Import:** `POST /v1/imports` with the bundle itself as the request body (up to 100 MB) and a mapping (old account id → new, ARN rewrites, cluster id), dry-run by default, showing a plan (create/update/skip) before apply; `afs-api` applies it as desired-state writes, one transaction per team (D49). Secrets must already exist (replicated via Secrets Manager multi-region replication or recreated) in the target account.
- **Restart behavior:** the reconciler's startup full-reconcile re-applies everything. A brand-new cluster plus a restored DB converges to the full environment with no manual steps.

## 9. Ephemeral teams, swarms and work orders

**Ephemeral teams.** `teams.kind = ephemeral` requires `expires_at` (at most `teams.ephemeral_max_days`
ahead, default 90), a lifetime budget that blocks at the cap, and `teardown_rule`: `at_expiry`,
`at_cap_or_expiry` or `at_work_complete`. The database checks these at commit. The reconciler reads
`teams_due_for_teardown` every minute; for each team it scales agents and pools to zero, applies the IAM
deny, deletes the namespace and the team's IAM roles, then sets `state = deleted`, `torn_down_at` and
`teardown_reason` and publishes `team.torn_down`. Configuration revisions, usage and audit stay. A team's
kind never changes. Teardown removes the same resources as a delete; PRD TEAM-9 lists them all.

**Swarms and pools.** A swarm is an ephemeral team with pools (`agent_pools`), optionally grouped into
ordered `swarm_stages`, and handoffs between pools (`pool_handoffs`). The reconciler renders each pool as
a Deployment of `workers` replicas (0 to 200) with the pool's ServiceAccount, a generic ephemeral volume
of `scratch_size_gib` per worker, and, when `shared_volume = efs`, one EFS access point mounted by every
worker. Each pool that receives handoffs gets one SQS inbox queue (`afs-<team ulid>-<short hash>`, under
SQS's 80-character limit) that only the roles of pools with a handoff to it may write and the receiving
pool may read. The receiver gets `AFS_INBOX_QUEUE_URL`; each sender gets
`AFS_HANDOFF_<TO_POOL_NAME_UPPER_SNAKE>_QUEUE_URL` for the receiver's inbox, with no change to the
container (SEC-6, D32). Pool secrets (`secrets.pool_id`, path
`<prefix>/<namespace>/<pool>/<name>`), bindings (`pool_secret_bindings`), configuration
(`pool_config_values`) and opt-outs follow the agent rules. Pools get a namespace-scoped `NetworkPolicy`
per pool from `pool_external_access`. Usage, activity and traffic rows carry `pool_id` and `worker_pod`;
the gateway identifies a worker by its source pod IP, which gives the pool and the worker pod name (D57).

**Isolation tier and viewer kubectl.** `teams.isolation_tier = dedicated` makes the reconciler create a
Karpenter NodePool `afs-t-<slug>` with a taint and label for the team, and add the toleration and node
selector to every pod in the namespace (enforced by admission policy). The NodePool's nodes carry the
team's tags. `teams.viewer_kubectl` makes the reconciler create an EKS access entry for the IAM role the
identity provider federates to (OQ-9) with the access policy `AmazonEKSViewPolicy` scoped to the namespace, minus
secrets (a namespace Role and RoleBinding for group `afs:<team>:viewers` instead of the managed policy
where secrets must be excluded).

**Work orders.** Security operators (`role_bindings.role = security_operator`, or a service-level API key
with that role) call `POST /v1/work-orders`. EventBridge events of detail type `afs.work_order.requested`
on the service bus go to an SQS queue the reconciler drains, inserting work orders with `source =
eventbridge` and the event id (deduplicated by a unique constraint). For each open work order with a
template, the reconciler creates the remediation team from `swarm_templates.spec` (teardown rule
`at_work_complete`, lifetime budget from the work order or template, expiry from the template's TTL),
sets `team_id` and `status = assigned`. Agents and pools of that team report progress through
`PATCH /v1/work-orders/{id}/repos/{host}/{owner}/{repo}` as workload principals (their projected
`afs-api` token, D29), and the reconciler also polls GitHub for the state of recorded pull requests
through one GitHub App installation per organization (OQ-5). Notifications (`work_order_notifications`,
unique per work order, repository, kind and recipient) go to the owning team's channels or, for outside
contacts, by email through the service-level channel named in setting
`work_orders.notification_channel_id`. `work_order_progress` gives counts and the SLA state; the
reconciler sends one SLA warning `work_orders.sla_warning_hours` before due and one breach notice after.
When every repository is merged, not affected or skipped the work order is done and its team is due for
teardown.

## 10. REST API design

Base path `/v1`. JSON. Resource-oriented. camelCase fields. All IDs are prefixed ULIDs-as-text (`team_01J…`, `agt_01J…`) for readability in CLI output.

The [API contract](contracts/api-contract.md) is the single list of operations, paths, permissions, CLI
commands, SDK methods, resource shapes, errors and events; this section only explains the design.

- **Pagination:** `?maxResults=50&nextToken=<token>` → `{ "items": [...], "nextToken": "<token>" }` (AWS style, maps directly onto CLI `--max-items`/`--starting-token`).
- **Concurrency:** `ETag` on GET, `If-Match` required on PUT/PATCH/DELETE of an existing resource (`412` on mismatch, `428` when missing).
- **Idempotency:** `Idempotency-Key` on creates and actions, stored per caller in `idempotency_keys` for `api.idempotency_key_ttl_seconds` (default 1 hour). Responses carrying a one-time `secretKey` are stored without it (D52).
- **Errors:** `{code, message, requestId, details}` with the codes of contract §6. `BudgetExceeded` (`402`) is returned only by the gateway, never by `afs-api` (D28).
- **Async status:** mutating calls return the desired state with `status.phase = Pending`; clients poll `…/status` until `Ready`, `Degraded` or `Failed`.
- **Headers:** `X-Request-Id` on every response (stored in audit), `X-Afs-Contract-Version` (D47). CORS is allowed only from `api.cors_origins` (D43).
- **Callers:** people (OIDC), team and service-level API keys, and workload principals (agents and pools with a projected `afs-api` token, D29).
- There is no agent scale operation (AGT-7) and no search endpoint (D44). Cost tag activation is acknowledged through `PutSetting billing.tag_activation_acknowledged`.

The OpenAPI 3.1 document (`api/openapi.yaml`) is the machine-readable contract. The TypeScript SDK types are generated from it and wrapped by hand-written ergonomic clients; the Go server uses it for request validation tests.

## 11. CLI design (`afs`)

Follows AWS CLI conventions. Service and operation names are the CLI column of [API contract §4](contracts/api-contract.md#4-operations).

```
afs <service> <operation> [--parameters] [global options]

afs configure                       # interactive; writes ~/.afs/config
afs configure sso                   # provider, issuer and public CLI client id from sso list-providers
afs sso login --profile prod
afs teams list-teams --output table
afs teams create-team --cli-input-json file://team.json
afs teams describe-team --team-id team_01J...
afs agents list-agents --team-id team_01J... --query "items[?status.phase=='Ready'].name"
afs agents create-agent --team-id team_01J... --cli-input-json file://agent.json
afs agents create-agent --generate-cli-skeleton
afs secrets create-secret --team-id team_01J... --scope team --name github-token --secret-value file://token.txt
afs budgets put-budget --team-id team_01J... --amount-usd 5000 --period monthly --thresholds 50 80 100 --if-match 7
afs budgets get-usage --team-id team_01J... --from 2026-11-01 --group-by model --output csv
afs members add-member --team-id team_01J... --user-email dev@corp.example --role team_viewer
afs work-orders create-work-order --cve-id CVE-2026-1234 --severity high --template-id swt_01J... \
    --repos github.com/acme/ledger=team_01J...,ops@corp.example
afs admin create-export
```

- **Services:** `configure`, `sso`, `teams`, `members`, `api-keys`, `agents`, `pools`, `secrets`, `budgets`, `reports`, `audit`, `work-orders`, `swarm-templates`, `models`, `admin`. Log destinations, notification channels, configuration values, external systems and revisions are operations of `teams`; identities and role links of `agents`; usage and costs of `budgets`.
- **Operation verbs:** `list-*`, `describe-*`/`get-*`, `create-*`, `update-*`, `delete-*`, `put-*` (replace), plus actions (`suspend-team`, `restart-agent`, `rotate-secret`, `scale-pool`, `enable-swarm-template`).
- **Global options:** `--profile`, `--endpoint-url`, `--output json|table|text|yaml|csv` (`csv` only on operations marked *CSV*, not with `--query`, D39), `--query` (JMESPath), `--no-paginate`, `--max-items`, `--page-size`, `--starting-token`, `--cli-input-json`, `--generate-cli-skeleton`, `--debug`, `--no-cli-pager`, `--color`, `--version`.
- **Safe updates:** `--if-match <version>`; without it the CLI reads, then writes, and prints the version it applied to (D40).
- **Secret values:** `--secret-value` takes `file://`, `fileb://` or `-` (stdin), or prompts without echo; never a plain argument.
- **Work order owners:** `--repos host/owner/repo[=<owner>[,<owner>]]`; without `=` the API resolves the owner from the teams' `AFS_OWNED_REPOS` configuration value; an owner with `@` is an email, one starting `team_` a team id; no slug lookup (D38).
- **Config files:** `~/.afs/config` (profiles: endpoint, sso provider, default team, output) and `~/.afs/credentials` / SSO token cache under `~/.afs/sso/cache`. Env vars: `AFS_PROFILE`, `AFS_ENDPOINT_URL`, `AFS_API_KEY`, `AFS_DEFAULT_OUTPUT`.
- **Paging:** auto-paginates by default like the AWS CLI; prints `NextToken` when `--max-items` truncates; CSV pages share one header row, with the next token read from the `X-Afs-Next-Token` response header.
- **Errors:** `An error occurred (AccessDenied) when calling the CreateAgent operation: ...`, exit code 254 for service errors, 252 for usage errors, 255 for others (AWS CLI codes). A locally expired SSO token exits 255 with the `afs sso login` hint before any call (D41).
- **RBAC:** the CLI calls `GET /v1/me` (cached 5 minutes) only to give helpful messages; the API's 403 is authoritative.

## 12. Web console architecture (TypeScript 7)

Clean architecture with the dependency rule pointing inward. Screens are in PRD §5.

```
apps/console/src/
  domain/          entities, value objects, policies (pure TS, no imports from outer layers)
    team.ts  agent.ts  budget.ts  permission.ts  money.ts
  application/     use cases + ports (interfaces the outer layers implement)
    ports/ TeamRepository.ts  AgentRepository.ts  SessionPort.ts ...
    usecases/ ListTeams.ts  CreateAgent.ts  SetBudget.ts  GetCurrentPrincipal.ts ...
  infrastructure/  adapters implementing ports with @afs/sdk, OIDC PKCE auth, storage
    sdk/ SdkTeamRepository.ts ...   auth/ OidcSession.ts
  presentation/    React components, routes, view models, hooks (depends on application)
    routes/  components/  viewmodels/  hooks/
  main/            composition root: wires adapters into use cases, provides via context
```

- Runtime: Bun for install, scripts, tests and the dev server, with `bun.lock`; Node.js 22 is the fallback runtime only, for a tool that does not run on Bun. No pnpm or npm lockfiles (D8, website ADR-004).
- Stack: React 19, React Router, TanStack Query (caching in presentation, not in domain), Vite for bundling, `tsc` 7 for type-checking (`--noEmit`), Vitest for unit tests of domain and use cases, Playwright for e2e.
- Hosting: a static bundle on S3 behind CloudFront per environment; runtime configuration (API URL, environment name, provider list fallback) from `/config.json`, so one build serves every environment (D43).
- Sign-in: OIDC authorization code + PKCE, tokens in memory only; a provider picker when more than one provider exists, skipped by `?provider=` and `?teamId=` deep links (D42).
- Permission checks: `can()` reads the per-team `permissions[]` that `GetMe` returns; `domain/permission.ts` holds the catalog for tooltips and the drift test. View models use `can()` to disable or hide controls. The API remains authoritative; a 403 surfaces as an "access denied" banner.
- Header search filters the teams, agents and pools the caller can list (and work orders for security operators); there is no search API (D44).
- No secret value is ever held in client state beyond the input field during a create/rotate submit.

## 13. Repository layout

Docs-only wrapper root plus four independent child repositories (same pattern as `stainedhead/agentic-teams`):

```
enterprise-agent-factory-service/              docs-only root: PRD, this design, UI mockups, cross-repo specs
  enterprise-agent-factory-service-db/         SQL + Go module (git-ignored by the root)
    migrations/        NNNNNN_name.{up,down}.sql, embedded (go:embed)
    bootstrap/roles.sql
    migrate/           migration runner used by afs-api and afs-migrate
    cmd/afs-migrate/
  enterprise-agent-factory-service-restapi/    Go 1.27
    api/openapi.yaml   REST contract
    cmd/afs-api  cmd/afs-reconciler  cmd/afs-gateway  cmd/afs-billing
    internal/domain  internal/usecase  internal/authz  internal/adapter/{httpapi,postgres,k8s,aws}
    deploy/helm/  deploy/terraform/
  enterprise-agent-factory-service-cli/        Go 1.27
    cmd/afs  internal/cli  (client generated from the OpenAPI contract)
  enterprise-agent-factory-service-website/    TypeScript 7 Bun workspace (Node.js 22 fallback runtime, no pnpm)
    packages/sdk/      @afs/sdk
    apps/console/      web management console (clean architecture)
```

## 14. Observability and operations

- OpenTelemetry traces and metrics from all Go services; Prometheus `/metrics`.
- Key SLIs: API p99 latency, reconcile lag (`now - updated_at` for un-observed generations), outbox delay, drift corrections per hour, gateway reservation failures and expired reservations released, gateway added latency, CUR variance.
- SLO alerting: multi-window burn-rate alerts on API and gateway availability, gateway added latency, reconcile lag and outbox delay (PRD §7).
- Runbooks: restore from PITR, rebuild a cluster from DB, rotate KMS key, revoke a team (emergency IAM deny), import bundle into a new account.

## 15. Key decisions and alternatives considered

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Source of truth | PostgreSQL + reconciler | CRDs in etcd (pure operator) | Portability across clusters, SQL reporting, audit, backups independent of cluster |
| Spend enforcement | Gateway reservation + IAM deny backstop | AWS Budgets actions | Budgets lag hours; reservations are per request |
| Agent → Bedrock auth | Gateway identifies the pod by source IP (Cilium identity, D57); gateway assumes team role | Agents call Bedrock directly | Direct calls cannot be metered or capped in real time |
| Secrets | Secrets Manager refs + ESO | Store encrypted values in DB | Keeps AFS out of the secret blast radius |
| CLI language | Go | Python (like AWS CLI) | Single static binary, shares API types |
| Network policy | Cilium (decided) | VPC CNI network policy | FQDN egress rules for SaaS endpoints |
| Egress control | External systems catalog with service → team → agent opt-outs, rendered as per-agent FQDN policy | Free-form host allow-list per team | Named, documented, centrally governed services; per-agent least privilege; one place to see who can reach what |
| Public collaboration endpoint | One AFS-owned ALB, WAF and `afs-edge` doing SSO and authorization per request | A load balancer or Ingress per team; trusting Paperclip's own login | One governed entry, flat cost, each team keeps its own provider, and removing a binding cuts access in 60 seconds whatever Paperclip says |
| Cross-account access | Dedicated agent role + role links with external IDs, inside a per-team glob filter | Shared team role trusted by every target account | Least privilege per agent, CloudTrail attribution in the target account, and a guardrail central teams control |
