# PRD: Paperclip team collaboration

| | |
|---|---|
| **Status** | Draft for review (2026-11-22), revised after the `review-prd` pass the same day |
| **Kind** | Change PRD to the feature-complete [initial PRD](enterprise-agent-factory-service-initial-PRD.md). Requirements here add to it; where they change an existing requirement, the change is named (section 6.8) |
| **Author** | J (Enterprise Architecture), drafted with Claude |
| **Jira** | N/A |
| **Repositories** | `enterprise-agent-factory-service` (this root: PRD, contracts, design), `-db`, `-restapi`, `-cli`, `-website` (`@afs/sdk` and the console) |
| **Upstream** | [agentic-teams](https://github.com/stainedhead/agentic-teams) and its [agentic-team-w-paperclip](https://github.com/stainedhead/agentic-team-w-paperclip) images; [Paperclip](https://github.com/paperclipai/paperclip) |

---

## 1. Summary

Each team's agents need one place to coordinate, and the team's people need one place to watch and steer
that work. In the Agentic Teammates design that place is **Paperclip**: a kanban board, chat and
user-defined groupings of agents, and the system of record agents pull work from and report progress to.
The `agentic-team-w-paperclip` project ships a Paperclip-enabled container image (Paperclip server plus a
Hermes instance) beside the plain harness image (Hermes, OMP and OpenCode).

This change makes Paperclip a first-class part of every AFS team:

- A team may run **exactly one collaboration agent**: an AFS agent built from a Paperclip-enabled template.
  It is one agent, one identity and one pod, like every other agent. Paperclip's orchestrator agent and the
  Hermes instance inside that pod share that one identity.
- The team's other agents **connect to it inside the namespace**, pull work from it and report to it. AFS
  delivers the connection settings and each agent's Paperclip credential with zero impact on the container.
- People reach Paperclip's **web UI** and **REST API** through a **public endpoint** that AFS owns:
  internet-facing load balancer, AWS WAF, TLS, and single sign-on through the same Okta or Entra ID provider
  the team already uses, with AFS role checks on every request. The team turns the web UI and the REST API
  on or off **independently**.

The public endpoint is a deliberate opening in the isolation controls of TEAM-3 and TEAM-4. This PRD
defines that opening narrowly and adds the controls the new risks need: prompt injection through
Paperclip content, secrets leaking into Paperclip, shared identity inside the pod, and the one-instance rule.

## 2. Problem

- **No coordination surface.** Paperclip appears nowhere in the current design. Agents in a team have no
  shared board or chat, and the team's people have no AFS-supported way to assign, review or monitor
  agent work.
- **The isolation model forbids what Paperclip needs.** Team namespaces deny all ingress (TEAM-3), admission
  policy blocks LoadBalancer and NodePort Services (TEAM-4), and `afs-api` sits behind an internal ALB only.
  A team cannot publish Paperclip, and must not be able to publish anything else.
- **Paperclip has its own identity, secret and agent models.** Its self-hosted sign-in is email and
  password (Better Auth); it has no OIDC SSO. It keeps its own agent roster and API keys, its own company
  secrets, and can run several local agents inside its own process. Each of those would bypass an AFS
  control (SSO and RBAC, the managed secret hierarchy, one identity per pod) unless AFS frames it.
- **Content is an attack path.** Paperclip issues, comments and chat, including items synced from Jira and
  GitHub and anything written through a public endpoint, become instructions for every agent that pulls
  from it.

## 3. Goals and non-goals

### Goals

| ID | Goal | Measure |
|---|---|---|
| PG1 | A team-admin can give the team a working Paperclip without a platform ticket | Collaboration agent created to Paperclip web UI reachable by a team member through SSO in under 15 minutes |
| PG2 | Every agent in the team can use Paperclip with no change to its container | Connected agents receive `PAPERCLIP_API_URL`, `PAPERCLIP_AGENT_ID` and `PAPERCLIP_AGENT_API_KEY` by env and pull work on first start |
| PG3 | The public path is narrow and fully governed | Only people with an AFS role on the team, signed in through the team's provider, or holders of a team API key with the right role, reach a team's Paperclip; zero cross-team reachability in isolation tests; nothing else in any team namespace is reachable from outside |
| PG4 | Web UI and REST API can each be switched off by the team | A disabled surface refuses requests within 60 seconds (p95) of the change |
| PG5 | Identity stays one agent, one identity, one pod | Every model call, AWS call and egress flow from the collaboration pod attributes to the collaboration agent |
| PG6 | Secrets stay in the managed hierarchy | No Paperclip secret, boot key or agent key exists outside `<service>/<namespace>/…` in Secrets Manager; credential-shaped text written by people through the endpoint is refused |

### Non-goals (this change)

- Building or forking Paperclip, Hermes or the images. AFS configures them, as the Agentic Teammates
  project does (`agentic-team-w-paperclip` ADR-0010).
- More than one Paperclip instance per team, or one Paperclip shared by several teams.
- Paperclip **pushing** work into agents (Paperclip's `hermes_gateway` adapter calling an agent's Hermes API
  server). Work flows by pull only, as `agentic-team-w-paperclip` ADR-0007 already does: agents call
  Paperclip; Paperclip never opens a connection into another agent's pod.
- Paperclip-local agents beyond the one orchestrator (more `hermes_local` or other local-adapter agents in the
  collaboration pod). Each other Paperclip roster member must be an AFS agent with its own pod (COL-12).
- Swarm pools connecting to Paperclip. Pools hand work over SQS (AGT-8); a pool's workers share an
  identity, so one Paperclip agent key would be shared by many pods.
- Inbound webhooks from the internet into Paperclip (for example a GitHub webhook for its issues sync).
  Paperclip connectors that poll, and OAuth flows a signed-in person completes in the browser, work.
- An external database for Paperclip. It keeps its embedded PostgreSQL on the agent's persistent volume.
- Removing Paperclip's own sign-in. Until Paperclip trusts an authenticating proxy, people sign in twice
  (PC-OQ-1). The AFS sign-in is the security control; the Paperclip account is identity inside Paperclip.
- Budgets inside Paperclip. Paperclip's own budget features may be used, but the AFS hard cap is the one
  that is enforced (BUD-2).

## 4. Users and roles

| Who | Wants |
|---|---|
| Team-admin | Create the collaboration agent, choose which surfaces are public, connect agents, see who uses it |
| Team collaborator (new role, PC-D6) | Assign and discuss work with agents in Paperclip without the power to change the team's AFS configuration |
| Team viewer | Watch agent work in Paperclip, read-only |
| Service admin | Allow or forbid public collaboration per team and service-wide, see every endpoint, break glass |
| Security | Know the public path is governed, logged and limited; know secrets do not leak into it |
| Automation author | Call Paperclip's REST API from a pipeline with a team API key |
| Agent (workload) | Find Paperclip and its own credential in its environment, pull work and report, with no setup |

### Permission changes

New permissions, implemented once in `-restapi/internal/authz` and mirrored in the console's
`domain/permission.ts` (API contract §3):

| Permission | Viewer | Collaborator | Team-admin | Service admin | Security operator | Notes |
|---|:-:|:-:|:-:|:-:|:-:|---|
| `collaboration:read` | ✓ | ✓ | ✓ | ✓ | | Settings, status, hostname, connected agents |
| `collaboration:manage` | | | ✓ | ✓ | | Web UI and REST API switches, registration mode, connections |
| `collaboration:access` | ✓ | ✓ | ✓ | ✓ | | Sign in to Paperclip through the endpoint; safe methods only (`GET`, `HEAD`) |
| `collaboration:contribute` | | ✓ | ✓ | ✓ | | Every method through the endpoint (create and change issues, comments, chat, groupings) |
| `collaboration:api` | | ✓ | ✓ | ✓ | | Use the REST API surface (header credential); with `collaboration:contribute` for writes |
| `teams:set-guardrails` (existing) | | | | ✓ | | Gains `mayExposeCollaboration` |

The **team collaborator** role (`team_collaborator`) holds every viewer permission plus
`collaboration:contribute` and `collaboration:api`. Team-admins grant it like the viewer role (ACC-2). Team
API keys may carry it. Security operators get nothing here; workload principals get nothing here (agents
reach Paperclip inside the namespace with their Paperclip key, never through the endpoint).

## 5. User experience

Follows the console rules of the initial PRD §5.1. No new mockups are made in this PRD; the spec phase adds
`docs/ui/30-ta-collaboration.png` and `31-tv-collaboration.png` from HTML sources, and this list is updated
in the same change.

**T16 · Collaboration (Paperclip)** (new; team navigation *Team → Collaboration*). Page header with *Info*,
*Open Paperclip* (primary, opens the team hostname in a new tab; disabled with the reason when the web UI is
off or the agent is not `Ready`) and *Actions* (*Edit endpoints*, *Rotate Paperclip keys*, *Delete
collaboration agent*, which links to T2). Panels:

- **Status**: collaboration agent (link to T2), phase and conditions (`EndpointReady`, `PaperclipReady`,
  `RegistrationHealthy`, `UnmanagedPaperclipAgents`), hostname, web UI and REST API state as dot + word.
- **Public endpoints**: two switches, *Web UI* and *REST API*, each with what it exposes and who may use it,
  disabled with the tooltip "Not allowed for this team by the service" when `mayExposeCollaboration` is off,
  or "Public collaboration is off for the service" when the service setting is off. Changing a switch shows
  the equivalent `afs collaboration put-collaboration` command.
- **Connected agents**: table of the team's agents with *Connected* (on/off), Paperclip agent id, link state
  (`pending`, `linked`, `failed`, `disabled`), last sync, and a filter. Selecting rows enables *Connect* and
  *Disconnect*.
- **Paperclip-managed secrets**: names and metadata of secrets Paperclip itself created under its reserved
  prefix (SEC-7), read-only for everyone, with the managed path.
- **Recent access**: sign-ins and denied requests over the last 7 days from the edge's records (counts per
  day and per person; no request bodies).

**V3 · Collaboration, read-only** (viewers and collaborators): the same page with an information banner;
switches and actions disabled with "Requires team-admin". *Open Paperclip* works for anyone with
`collaboration:access`.

Changes to existing screens:

- **T3 · Create agent**: a *Role* step offers *Worker* (default) or *Collaboration (Paperclip)*. Collaboration
  lists only templates with the `paperclip` capability, requires a dedicated IAM identity, sets the snapshot
  schedule to daily (changeable, never off), and is disabled with "This team already has a collaboration
  agent" when one exists. Worker agents get a *Connect to Paperclip* switch (on by default when the team has
  a collaboration agent).
- **T2 · Agents**: a *Collaboration* badge on the collaboration agent; a *Paperclip* column (link state).
- **T1 / V1 · Team overview**: a *Collaboration* tile with hostname, surface states and *Open Paperclip*.
- **T4 / V2 · Secrets**: secrets AFS generated for Paperclip show *Managed by AFS* (value never shown,
  rotate allowed); Paperclip-created secrets show *Managed by Paperclip* (read-only, no rotate or delete).
- **T6 · Members**: the role picker adds *Team collaborator*.
- **S2 / S3 · Teams and create team**: guardrail checkbox *May publish collaboration endpoints* (on by default).
- **S10 · Service settings**: a *Collaboration* tab with the settings of section 6.9, and the
  service-level list of every team's endpoint (team, hostname, web UI, REST API, state, last access).

## 6. Functional requirements

All requirements are in scope. Priorities order the build only: **P0** first (collaboration agent, in-namespace
connection, web UI endpoint), then **P1** (REST API endpoint, managed registration, content scanning),
then **P2** (member sync, reports).

### 6.1 Collaboration agent

| ID | Requirement | Pri |
|---|---|---|
| COL-1 | An agent has a **role**: `worker` (the default, every existing agent) or `collaboration`. A team has at most one non-deleted collaboration agent; a second create is refused with `409 Conflict` (`details.reason = collaboration_agent_exists`), enforced by the API and by a unique index in the database. The role is set at create and cannot change | P0 |
| COL-2 | A collaboration agent must use an agent template that has the `paperclip` capability (AGT-11; the template catalog gains a `capabilities` list). Templates without it cannot be used for the role, and a `paperclip` template cannot be used for a worker | P0 |
| COL-3 | A collaboration agent always has a **dedicated IAM identity** (AGT-6). Its role reads its own secret path and `_shared`, and may create, write and delete secrets under its reserved Paperclip prefix only (SEC-7) | P0 |
| COL-4 | **One identity in the pod.** The collaboration pod runs the Paperclip server and its Hermes instance as one agent: one ServiceAccount, one IAM role, one gateway identity (by source pod, IF-5), one persistent volume, one audit trail. Paperclip's orchestrator agent runs inside that pod (Paperclip's `hermes_local` adapter) and is that same AFS agent. Its model calls go through the AFS gateway and count against the team budget like any agent's | P0 |
| COL-5 | Paperclip's data (`PAPERCLIP_HOME`, including its embedded PostgreSQL) lives on the agent's persistent volume at `/var/lib/agent/paperclip`. The snapshot schedule defaults to daily with 14 kept and cannot be set to off for this role. The on-delete rule defaults to snapshot then delete | P0 |
| COL-6 | The reconciler renders, for the collaboration agent only: a ClusterIP Service `paperclip` in the namespace on port 3100; Paperclip's runtime settings by environment (`PAPERCLIP_DEPLOYMENT_MODE=authenticated`, `PAPERCLIP_DEPLOYMENT_EXPOSURE=public`, `PAPERCLIP_PUBLIC_URL=https://<hostname>`, `PAPERCLIP_ALLOWED_HOSTNAMES` with the hostname and the Service name, `HOST=0.0.0.0`, `PAPERCLIP_HOME`); and the Paperclip secret provider settings of SEC-7. The pod's Hermes API server port is not exposed by any Service | P0 |
| COL-7 | **Boot secrets by AFS.** When a collaboration agent is created, `afs-api` generates Paperclip's boot secrets (32 random bytes each, hex) and stores each as an agent secret under the managed path with `managedBy = afs`: `paperclip-better-auth-secret`, `paperclip-tool-action-signing-secret` and `paperclip-secrets-master-key`, bound as `BETTER_AUTH_SECRET`, `PAPERCLIP_TOOL_ACTION_SIGNING_SECRET` and `PAPERCLIP_SECRETS_MASTER_KEY`. No person ever sees them; the image's entrypoint never generates or writes them to the volume. *Rotate Paperclip keys* rotates the signing secrets (signing everyone out) but never the master key, whose rotation is refused with `ValidationError` because it would make Paperclip's stored identities undecryptable | P0 |
| COL-8 | Lifecycle follows TEAM-9 and AGT-1 for agents: pause, suspend and budget exhaustion keep the data and the endpoint record; while the pod is down the endpoint answers `503` with a page naming the reason (`paused`, `team_suspended`, `starting`). When the budget is exhausted the Paperclip server keeps serving people; only its orchestrator's model calls are refused (`402`). Deleting the collaboration agent disables both surfaces, removes the route and disconnects every agent (their Paperclip env and key bindings are removed and they roll) | P0 |
| COL-9 | A collaboration agent may be created in a persistent or an ephemeral team. Swarm templates may include one (P5), so a swarm's people can watch it | P1 |

### 6.2 Connecting the team's agents

| ID | Requirement | Pri |
|---|---|---|
| COL-10 | Each worker agent has `collaboration.connect` (default `true` when the team has a collaboration agent at the agent's creation, else `false`). A connected agent receives, by environment with zero impact on its container (SEC-6): `PAPERCLIP_API_URL=http://paperclip.<namespace>.svc.cluster.local:3100`, `PAPERCLIP_AGENT_ID` (its Paperclip roster id) and `PAPERCLIP_AGENT_API_KEY` (a secret binding). Changing the flag rolls the agent. Agents that exist before the collaboration agent is created are not connected automatically; T16 connects them in bulk | P0 |
| COL-11 | **Network.** The reconciler adds, for each connected agent, an egress rule to the Paperclip pod on TCP 3100 in the same namespace, and renders an ingress policy on the Paperclip pod that admits only: connected agents of the same namespace, `afs-edge` pods (section 6.3) and the reconciler. Every other ingress stays denied, including from the team's unconnected agents and from every other namespace. Paperclip never initiates a connection to another agent (pull only). The collaboration agent's own egress is governed by the external systems catalog (EXT-4, EXT-5) like any agent | P0 |
| COL-12 | **Registration modes.** `manual` (default for P0): the team-admin registers each agent in Paperclip, then records the agent's Paperclip roster id on the agent and stores its Paperclip key as an agent secret named `paperclip-agent-api-key` (SEC-2), which AFS binds as `PAPERCLIP_AGENT_API_KEY`. `managed` (P1): the reconciler keeps Paperclip's roster in step with AFS. For each connected agent it creates the Paperclip agent (name and AFS agent id as metadata, remote adapter, persona from the agent), writes the key Paperclip returns straight to Secrets Manager at the agent's `paperclip-agent-api-key` path (`managedBy = afs`), binds it and records the roster id. Pausing an AFS agent pauses its Paperclip agent; disconnecting or deleting it revokes the key in Paperclip and deletes the secret. The reconciler authenticates to Paperclip with a board API key that Paperclip issues once at bootstrap (PC-OQ-2) and that is stored as an AFS-managed secret of the collaboration agent; the reconciler's role may read only secrets with that exact name | P0 manual, P1 managed |
| COL-13 | **Roster guard.** In `managed` mode the reconciler reads Paperclip's roster every 10 minutes. Any Paperclip agent that is neither the orchestrator nor linked to an AFS agent sets condition `UnmanagedPaperclipAgents=True` on the collaboration agent with their names, and emits `collaboration.unmanaged_agents_found` once per new name. A local-adapter agent other than the orchestrator is reported the same way, because it would share the collaboration pod's identity (COL-4, PC-D3) | P1 |
| COL-14 | Link status per agent (`pending`, `linked`, `failed`, `disabled`, plus `lastSyncedAt` and the last error) is recorded by the reconciler and returned on the agent and on `ListCollaborationLinks` | P1 |

### 6.3 Public endpoint (`afs-edge`)

| ID | Requirement | Pri |
|---|---|---|
| COL-15 | **One governed entry point.** `-restapi` adds a service, `afs-edge` (Go), in `afs-system`, multi-AZ, at least 3 replicas. It is the only component reachable from the internet. An internet-facing ALB (platform Terraform, not the reconciler) in public subnets forwards to `afs-edge` only, with a wildcard ACM certificate for `*.<collab.base_domain>`, TLS policy TLS 1.2 minimum with TLS 1.3 preferred, HTTP redirected to HTTPS, and an AWS WAF web ACL (section 6.5). Each team's hostname is `<team-slug>.<collab.base_domain>`; DNS is one wildcard record, so team names do not appear in certificate transparency logs or zone listings | P0 |
| COL-16 | **Routing.** `afs-edge` maps the request's host to a team and forwards to that team's `paperclip` Service, and to nothing else. It reads the route table (team, hostname, surfaces enabled, agent ready) from the database through a read-only role and refreshes it on the change feed (D30) and every 30 seconds. An unknown host, a team without a collaboration agent, or a host whose surfaces are both off returns `404` with no detail. The ALB, WAF and edge never route by path into a namespace, and the edge refuses requests whose `Host` and SNI differ | P0 |
| COL-17 | **Web UI sign-in.** When the web UI is on, a browser without a valid edge session is redirected to the team's sign-in provider (ACC-1, the provider the team chose) using authorization code with PKCE. The callback is one fixed URL per environment (`https://<collab.base_domain>/oauth2/callback`, so each provider registers one redirect URI); after it, the edge hands off to the team host with a one-time code (60 seconds, single use) and sets a host-only cookie `__Host-afs-collab` (Secure, HttpOnly, SameSite=Lax), so a session for one team is never sent to another team's host. Session lifetime is `collab.session_ttl_minutes` (default 480), with re-authentication at expiry. Each sign-in provider gains an optional collaboration client (`collabClientId` and a Secrets Manager reference for its client secret, never the value, ACC-1), set by service admins on S10; a provider without one cannot serve the web UI surface (PC-OQ-6) | P0 |
| COL-18 | **Authorization on every request.** The edge decides with the same `internal/authz` code as `afs-api`, from the caller's AFS role bindings on the host's team (users and IdP groups through the team's provider, D21): `collaboration:access` admits `GET` and `HEAD`; every other method needs `collaboration:contribute`. A caller with no binding on the team gets `403` and never sees the team's content. Decisions are cached at most 60 seconds, so removing a binding cuts access within 60 seconds whatever the Paperclip account says | P0 |
| COL-19 | **REST API surface.** When the REST API is on, a caller presents an AFS credential in `X-Afs-Authorization: Bearer <token>`: an access token from the team's sign-in provider, checked with the same issuer, audience and expiry rules as `afs-api` (so the CLI's SSO token works) or a team API key (ACC-4) holding `collaboration:api`. The caller's Paperclip credential (a Paperclip board or agent API key) stays in `Authorization`, untouched. The edge validates and strips `X-Afs-Authorization`, applies COL-18, and forwards. Requests that carry the edge session cookie are web UI traffic; requests that carry the header are API traffic; a request with both is refused with `400` | P1 |
| COL-20 | **Independent switches.** `webUiEnabled` and `restApiEnabled` are set per team by team-admins (`collaboration:manage`). With the web UI off, sign-in is refused and existing sessions stop working; with the REST API off, header credentials are refused; with both off, the host returns `404`. Defaults when a collaboration agent is created: web UI on, REST API off. Either switch can only be on while the team's `mayExposeCollaboration` guardrail and the service setting `collab.public_endpoints` are on; turning either guardrail off turns the surfaces off without changing the team's stored choice, and the console says why | P0 |
| COL-21 | **What the edge forwards.** It removes the AFS cookie, `X-Afs-Authorization`, `X-Amzn-*` and any `X-Forwarded-*` the client sent, sets its own `X-Forwarded-For`, `X-Forwarded-Proto` and `X-Request-Id`, and never forwards to Paperclip anything that identifies the AFS session. It adds `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy` and a frame-ancestors policy to responses. Request bodies are limited to `collab.max_body_mb` (default 25). WebSocket and server-sent event streams Paperclip uses for chat are supported, with an idle timeout of 10 minutes | P0 |
| COL-22 | **No other way in.** Admission policy (TEAM-4) also refuses, in team namespaces, `Ingress` objects, Gateway API routes and gateways, Services with `externalIPs` or `loadBalancerSourceRanges`, and any Service other than the reconciler's `paperclip` Service that selects the collaboration pod. Only the reconciler may create the `paperclip` Service. Isolation tests prove a team cannot publish anything, including a second Paperclip | P0 |
| COL-23 | **Service-level control.** Service setting `collab.base_domain` (unset means the feature is off and every endpoint is disabled), `collab.public_endpoints` (service-wide switch, default on) and per-team guardrail `mayExposeCollaboration` (default `true`, service admins only) govern exposure. Optional service setting `collab.allowed_source_cidrs` (default empty, meaning any) is rendered into the WAF as an allow list for organizations that want the endpoint reachable only from corporate egress | P0 |

### 6.4 Secrets and content

| ID | Requirement | Pri |
|---|---|---|
| SEC-7 | **Paperclip's own secrets stay in the hierarchy.** Paperclip's secret provider is set to AWS Secrets Manager (`PAPERCLIP_SECRETS_PROVIDER=aws_secrets_manager`) with prefix `<service>/<namespace>/<collaboration-agent-name>/paperclip/`, the environment KMS key and the team's tags, using the collaboration agent's own role. So the connector tokens and company secrets people enter in Paperclip land in the managed hierarchy, under the team's IAM and KMS controls, and are deleted with the team (TEAM-9). AFS lists them (name, created, last changed; never the value) as `managedBy = paperclip`; the reconciler refreshes the list hourly from Secrets Manager metadata. They cannot be bound to other agents. This is the one bounded exception to SEC-2's "create through AFS only" (PC-D4) | P0 |
| COL-24 | **Credential scanning on the way in.** For every request the edge forwards with a body (web UI and REST API), it scans text for credential patterns (AWS access keys, GitHub and Slack tokens, private key blocks, JWTs, Okta and Entra client secrets, and generic `password=` / `secret=` assignments). With `collab.content_scan = block` (the default) a match is refused with `422` (`code = SecretDetected`, naming the pattern type, never the value), and the person is told to store it as an AFS secret instead. `warn` forwards it and records the detection; `off` disables scanning. Detections are counted per team and person and emit `collaboration.secret_detected` (no value, no fragment) | P1 |
| COL-25 | **Scanning what agents write.** Agents write to Paperclip inside the namespace, not through the edge. In `managed` mode the reconciler scans new and changed Paperclip issues and comments every 10 minutes with the same patterns and, on a match, emits `collaboration.secret_detected` with the item's Paperclip id and the agent that wrote it, so a team-admin can remove it and rotate the credential. It never copies Paperclip content into the AFS database or logs | P1 |
| COL-26 | AFS never stores, logs or exports Paperclip content. Edge access records carry team, person or key prefix, method, path template, status, bytes and timing only. Export bundles (CFG-5) carry the collaboration settings and the agent's latest snapshot reference, not Paperclip data | P0 |

### 6.5 Prompt injection and abuse

Paperclip content is untrusted input for every agent that reads it. AFS cannot decide what is an injection;
it limits who can write, how much damage an injected agent can do, and how fast an abuse is seen.

| ID | Requirement | Pri |
|---|---|---|
| COL-27 | **Only known people write.** No anonymous access: every request through the edge is authenticated and authorized (COL-18, COL-19). Viewers are read-only by method. Writers are team-admins, collaborators and service admins, or team API keys with the collaborator or team-admin role. Paperclip sign-up is closed (invite only), and in `managed` mode the reconciler checks it and sets `PaperclipReady=False` with reason `OpenSignUp` if it is open | P0 |
| COL-28 | **Blast radius stays per agent.** Connecting to Paperclip grants an agent nothing else: its egress (EXT-4), secrets (SEC-3), IAM role (AGT-6) and budget (BUD-2) are unchanged, and Paperclip cannot reach into an agent (COL-11). The collaboration agent gets no secret bindings of other agents, and its role cannot read other agents' secret paths | P0 |
| COL-29 | **Low-trust work is marked.** Paperclip's `low_trust_review` trust preset is recommended for projects that ingest external content (synced Jira and GitHub items, untrusted pull requests). The T16 page and the user docs explain it; AFS does not set Paperclip policy itself | P1 |
| COL-30 | **Edge limits.** WAF managed rule groups (core rule set, known bad inputs, IP reputation, anonymous IP list), a rate-based rule of 2,000 requests per 5 minutes per source IP, and edge limits per principal (20 requests per second, burst 40, `429` with `Retry-After`, the same as `afs-api`). More than `collab.denied_spike_threshold` (default 50) denied requests (`401`, `403`, `422`) on one team in 5 minutes emits `collaboration.denied_spike` to team-admins and service admins | P0 |
| COL-31 | **Records.** Every sign-in, sign-out, denied request and switch change is recorded. Sign-ins and denials go to the team's log delivery as edge events (like agent sign-ins, D17) with the redaction of OPS-4; switch and guardrail changes are audited and versioned (CFG-3). The service keeps 13 months of edge records for the platform in CloudWatch. Service admins hold every permission on every team, so they can enter any team's Paperclip; each such sign-in is marked as a service admin entry in the team's records and shown on T16, so the team can see it | P0 |

### 6.6 People in Paperclip

| ID | Requirement | Pri |
|---|---|---|
| COL-32 | The first Paperclip instance admin is the team-admin who created the collaboration agent: in `managed` mode the reconciler completes Paperclip's bootstrap and sends that person the one-time admin invite through the team's notification channels; in `manual` mode the T16 page shows how to run the bootstrap from the agent's log instructions (PC-OQ-2) | P0 |
| COL-33 | **Member sync** (`managed` mode): for each person with a user binding on the team, the reconciler creates a Paperclip invite (collaborators and team-admins as members, viewers as viewers where Paperclip supports it) and, when the binding is removed, deactivates that Paperclip account. People who reach the team only through an IdP group are invited on their first edge sign-in. Access is still decided by the edge (COL-18), so a stale Paperclip account cannot be used | P2 |

### 6.7 API, events and reports

| ID | Requirement | Pri |
|---|---|---|
| COL-34 | New operations (API contract §4.4b, to be added): `GetTeamCollaboration`, `PutTeamCollaboration`, `ListCollaborationLinks`, `ConnectAgentToCollaboration` / `DisconnectAgentFromCollaboration`, `RotateCollaborationKeys`, and service-level `ListCollaborationEndpoints`. `CreateAgent` and `GetAgent` gain `role` and `collaboration` {`connect`, `paperclipAgentId`, `linkState`}; `UpdateTeam` gains `mayExposeCollaboration`; `ListSecrets` returns `managedBy` (`user`, `afs`, `paperclip`) and filters by it. Every mutation is audited; those with event types below write outbox events | P0 |
| COL-35 | New events (API contract §7): `collaboration.updated` (switches, registration mode), `collaboration.endpoint_state_changed` (reconciler, `EndpointReady` changes), `collaboration.secret_detected`, `collaboration.denied_spike`, `collaboration.unmanaged_agents_found`, `agent.collaboration_linked` and `agent.collaboration_unlinked` | P0 |
| COL-36 | Reports gain *Collaboration* measures at team and service level: daily sign-ins, unique people, requests by surface, denied requests by reason, secret detections. Usage only, never content (RPT-1 conventions). The edge writes five-minute counts per team, person or key prefix, surface and outcome through one database function; T16's *Recent access* panel reads them | P2 |

### 6.8 Changes to existing requirements

| Existing | Change |
|---|---|
| TEAM-3 | Default deny stays. Two named exceptions in the team namespace, both rendered by the reconciler only: connected agents to the Paperclip pod on 3100, and ingress to the Paperclip pod from `afs-edge` and the reconciler (COL-11) |
| TEAM-4 | Also blocks Ingress, Gateway API objects, `externalIPs`, `loadBalancerSourceRanges` and any Service selecting the collaboration pod other than the reconciler's (COL-22) |
| TEAM-9 | The collaboration agent follows the agent rows. New row *Public endpoint*: suspend → `503 team_suspended`; resume → restored; delete → route removed, hostname released after 30 days so links cannot be taken over by a new team with the same slug |
| AGT-7 | Unchanged: the collaboration agent is one identity and one pod. COL-4 states how Paperclip and Hermes share it |
| AGT-11 | Templates gain `capabilities` (for example `paperclip`) |
| SEC-2, SEC-5 | Exception for Paperclip-created secrets under the reserved prefix `<service>/<namespace>/<agent>/paperclip/` (SEC-7) and for AFS-generated secrets (`managedBy = afs`) |
| ACC-2 | New team role `team_collaborator` (PC-D6) |
| Solution design §3, §4 | New component `afs-edge`; public ALB and WAF; the isolation table gains a *Public ingress* row |
| Root PRD §7, Encryption | One recorded exception: the in-namespace hop from `afs-edge` and agents to Paperclip is HTTP inside Cilium's WireGuard transparent encryption, because Paperclip serves plain HTTP (PC-D7) |

### 6.9 Service settings (added to the initial PRD §6.13)

| Key | Default | Allowed values | Used by |
|---|---|---|---|
| `collab.base_domain` | unset | DNS name; unset turns the feature off | COL-15, COL-23 |
| `collab.public_endpoints` | `true` | boolean | COL-20, COL-23 |
| `collab.allowed_source_cidrs` | `[]` | array of IPv4 or IPv6 CIDRs; empty means any | COL-23 |
| `collab.session_ttl_minutes` | `480` | 15 to 1440 | COL-17 |
| `collab.content_scan` | `"block"` | `block`, `warn`, `off` | COL-24 |
| `collab.max_body_mb` | `25` | 1 to 100 | COL-21 |
| `collab.denied_spike_threshold` | `50` | 1 to 100000 denied requests per team in 5 minutes | COL-30 |

## 7. User stories and acceptance criteria

Product stories continue the initial PRD's numbering. Repository stories continue each repository PRD's
numbering and cite the product story they refine. Acceptance criteria are Given / When / Then and are the
basis of end-to-end tests in the dev environment.

### 7.1 Product stories

**US-27 · Give the team a Paperclip.** As a team-admin, I want to create my team's collaboration agent from a
Paperclip template, so that my people and agents have one board and chat. *(COL-1..8, SEC-7, T3, T16)*
- Given a team without a collaboration agent and a template with the `paperclip` capability, when I create
  an agent with role *Collaboration*, then it becomes `Ready` within 5 minutes (p95), its pod runs Paperclip
  and Hermes under one ServiceAccount, a dedicated IAM role and one volume, and T16 shows its hostname.
- Given the team already has one, when I or the API try to create a second, then the console disables the
  option and the API returns `409 Conflict` with `details.reason = collaboration_agent_exists`.
- Given a template without the `paperclip` capability, when I choose role *Collaboration*, then the API
  returns `ValidationError` naming the template.
- When the agent is created, then `paperclip-better-auth-secret`, `paperclip-tool-action-signing-secret` and
  `paperclip-secrets-master-key` exist under the agent's managed path with `managedBy = afs`, are bound as
  the env vars Paperclip reads, appear on T4 without any value, and `/var/lib/agent/paperclip/.secrets` does not exist on the volume.
- Given the collaboration agent's Hermes calls a model, then the call goes through the gateway, is recorded
  against the collaboration agent, and is refused with `402` when the team's budget is exhausted while the
  Paperclip web UI keeps serving.

**US-28 · Agents use Paperclip without setup.** As a team-admin, I want my agents connected to Paperclip by
default, so that they pull work and report on their first start. *(COL-10..14)*
- Given a collaboration agent and a new worker agent with *Connect to Paperclip* on, then the worker's pod has
  `PAPERCLIP_API_URL`, `PAPERCLIP_AGENT_ID` and `PAPERCLIP_AGENT_API_KEY` and can open TCP 3100 to the Paperclip
  pod, and nothing else new.
- Given a worker with *Connect* off, or a pod in another namespace, when it connects to the Paperclip pod,
  then the connection is denied and recorded by Hubble as a denied flow.
- Given `managed` registration, when I connect an agent, then within 2 minutes a Paperclip agent exists with
  the AFS agent id in its metadata, the key is in Secrets Manager at the agent's `paperclip-agent-api-key`
  path, the link state is `linked`, and no person saw the key.
- When I disconnect or delete that agent, then its Paperclip key no longer authenticates, the secret is
  scheduled for deletion and the link state is `disabled`.
- Given someone adds a local-adapter agent inside Paperclip, then within 10 minutes the collaboration agent
  shows `UnmanagedPaperclipAgents=True` naming it and `collaboration.unmanaged_agents_found` is emitted once.

**US-29 · People sign in with SSO.** As a team member, I want to open my team's Paperclip from the internet with
my usual company sign-in, so that I can follow and steer agent work. *(COL-15..18, COL-20, COL-21)*
- Given the web UI is on and I have any team role, when I open `https://<slug>.<base domain>`, then I am sent to
  the team's provider, return to Paperclip, and my browser holds a host-only `__Host-afs-collab` cookie.
- Given I am a viewer, when I create or edit an issue, then the edge returns `403`; given I am a collaborator,
  the same request reaches Paperclip.
- Given I have no role on team A but a role on team B, when I open A's hostname, then I get `403` after sign-in
  and no A content; my B session cookie is never sent to A's host.
- Given my binding is removed, then within 60 seconds my next request is refused, whatever my Paperclip account.
- Given an unknown hostname, or a team with both surfaces off, then the response is `404` with no team detail.

**US-30 · Turn surfaces on and off.** As a team-admin, I want to switch the web UI and the REST API independently,
so that we publish only what we use. *(COL-19, COL-20, COL-23)*
- Given a new collaboration agent, then the web UI is on and the REST API off.
- When I turn the REST API on, then within 60 seconds (p95) a request with a valid `X-Afs-Authorization` and
  a Paperclip key reaches Paperclip; when I turn it off, the same request gets `403` with
  `details.reason = surface_disabled` within 60 seconds.
- When I turn the web UI off, then new sign-ins and existing sessions are refused within 60 seconds.
- Given a service admin turns `mayExposeCollaboration` off for my team, then both surfaces stop, my stored
  choices are kept, and the switches are disabled with a tooltip naming the guardrail.
- Given I am a viewer or collaborator, when I call `PutTeamCollaboration`, then `403 AccessDenied` and an audit
  record of the denial.

**US-31 · Call the Paperclip API from a pipeline.** As an automation author, I want to call Paperclip's REST
API with a team API key, so that pipelines can create and update work. *(COL-19, ACC-4)*
- Given a team API key with the collaborator role and the REST API on, when the pipeline sends it in
  `X-Afs-Authorization` with a Paperclip board key in `Authorization`, then Paperclip receives the request with
  `Authorization` unchanged and no `X-Afs-Authorization`.
- Given a viewer-role API key, then `GET` succeeds and `POST` gets `403`.
- Given a request with both the session cookie and the header, then `400`.
- Given more than 40 requests in one second from one key, then `429` with `Retry-After`.

**US-32 · Keep secrets out of Paperclip.** As security, I want credentials kept out of Paperclip's content and in
the managed hierarchy, so that a public endpoint does not become a secret store. *(SEC-7, COL-24..26)*
- Given `collab.content_scan = block`, when a person posts a comment containing an AWS access key pair, then
  the edge returns `422 SecretDetected` naming the pattern type, Paperclip never receives it, and
  `collaboration.secret_detected` carries no part of the value.
- When a person adds a connector token in Paperclip's secret settings, then the secret is created at
  `<service>/<namespace>/<agent>/paperclip/…` with the team's tags and KMS key, and T4 lists it as
  *Managed by Paperclip* without a value.
- Given the collaboration agent's role, when it tries to read another agent's secret path or write outside its
  `paperclip/` prefix, then IAM denies it.
- Given an agent writes a GitHub token into an issue (`managed` mode), then within 10 minutes
  `collaboration.secret_detected` names the item and the agent.
- No AFS table, log line or export bundle contains Paperclip issue, comment or chat text (scanned in tests).

**US-33 · Govern public collaboration.** As a service admin, I want to control exposure service-wide and per
team and see every endpoint, so that the public surface stays known and limited. *(COL-22, COL-23, COL-30,
COL-31, S10)*
- Given `collab.base_domain` is unset, then no team can turn a surface on and `PutTeamCollaboration` returns
  `ValidationError` naming the setting.
- When I turn `collab.public_endpoints` off, then every team's endpoint returns `404` within 60 seconds and
  teams' stored choices are kept.
- Given `collab.allowed_source_cidrs` is set, then a request from outside those ranges is blocked by the WAF.
- Given a team-admin, when they try to create an Ingress, a Gateway API route, a LoadBalancer Service or a second
  Service selecting the Paperclip pod, then admission refuses it.
- Given 51 denied requests on one team in 5 minutes, then `collaboration.denied_spike` reaches the team-admins'
  and service admins' channels within 2 minutes.
- `ListCollaborationEndpoints` lists every team's hostname, surfaces, state and last access; team callers get `403`.

### 7.2 `-db` stories (migration 000020, minor release)

*Proven by* lines name the integration tests the change adds; none exist yet.

**DB-US-44 · One collaboration agent per team.** *(refines US-27)*
- `agents.role` is `text NOT NULL DEFAULT 'worker' CHECK (role IN ('worker','collaboration'))`; existing rows
  become `worker`; an update of `role` raises `23514`.
- A partial unique index on `(team_id) WHERE role = 'collaboration' AND deleted_at IS NULL` (the pattern of
  `agents_team_name_uq`) makes a second collaboration agent raise `23505`. Adding the column with a constant
  default does not rewrite `agents` (lock impact noted in the migration header).
- A trigger refuses a collaboration agent whose template lacks `paperclip` in `agent_templates.capabilities`, or
  whose `iam_identity` is not `dedicated`, with `23514`; and a worker agent on a `paperclip` template.
- `agent_templates.capabilities text[] NOT NULL DEFAULT '{}'` with a check on known values.
- Proven by: `TestCollaborationAgent/*` (second insert `23505`, role change `23514`, template and identity checks).

**DB-US-45 · Collaboration settings.** *(refines US-30, US-33)*
- New desired-state table `team_collaboration` (`team_id` PK and FK, `agent_id` with composite FK
  `(team_id, agent_id)`, `web_ui_enabled`, `rest_api_enabled`, `registration_mode` in `manual|managed`,
  `version`, `generation`, `created_at/by`, `updated_at`), with `afs.touch_row()`, `afs.record_revision()`,
  the change-feed trigger (D30), RLS for `afs_app` by `afs.caller_sees_team(team_id)`, and rows in
  `seedOtherTeams`.
- `teams.may_expose_collaboration boolean NOT NULL DEFAULT true`, writable by service admins only (the
  guardrail trigger raises `42501` for others).
- The seven `collab.*` settings of §6.9 are seeded with their ranges; a value outside a range raises `23514`.
- `role_bindings.role` and `api_keys.role` accept `team_collaborator` for team bindings and team keys only
  (`23514` at service level).
- Proven by: `TestTeamCollaboration/*`, `TestRowLevelSecurityIsolatesTeams/team_collaboration`,
  `TestCrossTeamWritesChangeNothing/team_collaboration`, `TestServiceSettingRanges/collab.*`.

**DB-US-46 · Agent links and managed secrets.** *(refines US-28, US-32)*
- `agent_collaboration` (`team_id`, `agent_id` composite FK, `connect boolean`, `paperclip_agent_id text`,
  `link_state` in `pending|linked|failed|disabled`, `last_synced_at`, `last_error`), where `afs_app` writes
  `connect` and, in `manual` mode, `paperclip_agent_id`, and only `afs_reconciler` writes `link_state`,
  `last_synced_at` and `last_error` (column grants). RLS and isolation tests as DB-US-1.
- `secrets.managed_by text NOT NULL DEFAULT 'user' CHECK (managed_by IN ('user','afs','paperclip'))`. Rows
  with `paperclip` are written only by `afs_reconciler`, have ARNs under `afs.secret_path(...) || 'paperclip/'`
  (checked), and cannot be bound (`agent_secret_bindings` insert raises `23514`).
- The secret name `paperclip` and names starting `paperclip-` are reserved for `managed_by = 'afs'` on a
  collaboration agent (`23514` otherwise), so no user secret can sit at or beside the `paperclip/` prefix.
- Proven by: `TestAgentCollaboration/*`, `TestManagedSecrets/*`, isolation subtests.

**DB-US-47 · Edge read access.** *(refines US-29)*
- New login-less role `afs_edge` with `EXECUTE` on two `SECURITY DEFINER` functions only:
  `afs.collab_routes()` (team id, slug, hostname, surfaces, guardrails, ready flag, provider id) and
  `afs.collab_principal(team_id, subject, provider_id, groups[])` and its API-key form (bindings and roles; never
  key hashes outside the function), plus `afs.record_collab_access(...)`, which inserts five-minute counts
  into a partitioned `collaboration_access` fact table (13-month retention like the other fact tables, D36;
  RLS for `afs_app` readers). No table privileges.
- `identity_providers` gains nullable `collab_client_id` and `collab_client_secret_arn` (a reference, never a
  value), written by service admins only.
- Proven by: `TestEdgeRole/*` (no direct select on any table; functions return only the named columns).

### 7.3 `-restapi` stories

**RA-US-19 · Collaboration API.** *(refines US-27, US-30, US-33)*
- `GetTeamCollaboration`, `PutTeamCollaboration` (`If-Match`), `ListCollaborationLinks`,
  `ConnectAgentToCollaboration`, `DisconnectAgentFromCollaboration`, `RotateCollaborationKeys`,
  `ListCollaborationEndpoints` are in `api/openapi.yaml`, each with its permission, allowed and denied tests per
  role (viewer, collaborator, team-admin, service admin, security operator, workload).
- `CreateAgent` with `role: collaboration` generates the three boot secrets in Secrets Manager in the same
  request and stores only ARNs; a failure to write them returns `503 Unavailable` and creates nothing.
- `RotateCollaborationKeys` rotates the two signing secrets and refuses the master key with `ValidationError`.
- On a suspended team every mutation here returns `409` (`team_suspended`).

**RC-US-19 · Render the collaboration agent.** *(refines US-27, US-28)*
- The reconciler renders the `paperclip` Service, the Paperclip environment of COL-6, the SEC-7 provider
  settings and the network policies of COL-11, and nothing else for the role; envtest proves a worker gets
  none of them.
- Connected agents get the three `PAPERCLIP_*` values; changing `connect` rolls the pod (pod-template hash).
- Admission additions of COL-22 refuse each object kind in envtest, and accept the reconciler's own Service.
- `EndpointReady` is `True` only when the pod is ready, the Service has endpoints and the route is published.

**RC-US-20 · Managed registration and scanning.** *(refines US-28, US-32)*
- Against a fake Paperclip API: create, pause, revoke and roster read; the key goes straight from the response
  to Secrets Manager and is never logged (log capture test); `UnmanagedPaperclipAgents` and the event fire
  once per new name; credential patterns in fake issues emit `collaboration.secret_detected` with no value.
- The reconciler's IAM policy reads only `.../paperclip-board-api-key` secrets (policy render test).

**EDGE-US-1 · Route and authenticate.** *(refines US-29, US-31)*
- Host to team mapping, `404` for unknown hosts and disabled teams, SNI and Host mismatch refused.
- OIDC code + PKCE per team provider against a fake IdP; one callback URL; one-time handoff code single use,
  expired after 60 s; host-only cookie; session never valid on another team's host.
- `X-Afs-Authorization` with an SSO token or a team API key; `Authorization` forwarded unchanged; both
  credentials → `400`.

**EDGE-US-2 · Authorize, limit and record.** *(refines US-29, US-30, US-33)*
- `internal/authz` decides; method rule for `collaboration:access`; denied tests for every role and surface.
- A removed binding is refused within 60 s (cache TTL test); a switch change is applied within 60 s.
- Per-principal limits return `429`; headers of COL-21 are stripped and added; body limit enforced; WebSocket
  and SSE proxied.
- Credential scanning: one table test per pattern, `block`, `warn` and `off`; the `422` body and the event never
  contain the matched text.
- Access records go to the team's log delivery with redaction and contain no body text.
- `afs-edge` holds ≥ 90% coverage in its use-case package; adds < 20 ms p99 in the load test.

**INF-US-1 · Public entry.** *(refines US-29, US-33)*
- Terraform: internet-facing ALB in public subnets, target group of `afs-edge` pods only, wildcard ACM
  certificate, TLS policy, HTTP→HTTPS, WAF ACL with the COL-30 rules and the optional CIDR allow list,
  wildcard Route 53 record, access logs to S3. `terraform test` checks each. The edge pods admit traffic only
  from the ALB security group.

### 7.4 `@afs/sdk` stories (`-website` `packages/sdk`)

**WEB-US-43 · SDK for collaboration.** *(refines US-27, US-30, US-31, US-33)*
- Regenerated from the contract: `collaboration.get()`, `collaboration.put()`, `collaboration.links.list()`,
  `collaboration.connectAgent()`, `collaboration.disconnectAgent()`, `collaboration.rotateKeys()`,
  `admin.collaborationEndpoints.list()`; `agents.create()` accepts `role` and `collaboration`; `secrets.list()`
  accepts a `managedBy` filter. Contract replay tests pass; TSDoc on each export.
- A hand-written helper `collaboration.endpointUrl(team)` returns the web UI and API base URLs from
  `GetTeamCollaboration`; the SDK does not proxy Paperclip calls and never handles a Paperclip key.

### 7.5 Console stories (`-website` `apps/console`)

**WEB-US-44 · Collaboration page.** *(refines US-27, US-28, US-30)*
- T16 and V3 as section 5 describes; *Open Paperclip* disabled with its reason when the web UI is off or the
  agent is not ready; switches gated by `can('collaboration:manage')` and still handle `AccessDenied`; each
  change shows the CLI equivalent.
- Viewers and collaborators see V3 with every control disabled and the tooltip "Requires team-admin".
- Paperclip-managed secrets are listed read-only; no value is ever requested or held in state.

**WEB-US-45 · Create agent and team guardrail.** *(refines US-27, US-33)*
- T3 role step: *Collaboration* offers only `paperclip` templates, forces a dedicated identity and a snapshot
  schedule that cannot be off, and is disabled when a collaboration agent exists. Workers get *Connect to
  Paperclip*.
- S2/S3 guardrail checkbox for service admins only; S10 *Collaboration* tab with the settings and the endpoint
  list. Architecture test stays green. WCAG 2.2 AA (axe) on T16, V3 and the changed steps.

### 7.6 CLI stories

**CLI-US-24 · Collaboration commands.** *(refines US-27, US-28, US-30, US-33)*
- New service `collaboration`: `describe-collaboration`, `put-collaboration`, `list-collaboration-links`,
  `connect-agent`, `disconnect-agent`, `rotate-collaboration-keys`; `admin list-collaboration-endpoints`;
  `agents create-agent --role collaboration` and `--collaboration-connect | --no-collaboration-connect`;
  `secrets list-secrets --managed-by`. Each has help, an example, table columns and goldens, and an
  `AccessDenied` test (exit 254).

**CLI-US-25 · Call the Paperclip API.** *(refines US-31)*
- A local command `afs collaboration invoke-api --team-id <id> --method <verb> --path <path> [--body file://…]
  --paperclip-key-file <file>` sends one request to the team's REST API surface with the profile's SSO token or
  API key in `X-Afs-Authorization` and the Paperclip key from the file (or stdin) in `Authorization`, and prints
  the response. No token or key appears on stdout, stderr, `--debug` output or the command line (redaction
  tests). The REST API being off maps to exit 254 with the AWS-style message.

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | `afs-edge` adds < 20 ms p99 to a request (excluding Paperclip); route and switch changes apply within 60 s (p95); sign-in round trip < 3 s (p95) excluding the IdP |
| Scale | 200 teams; 50 concurrent people and 100 requests per second per team through the edge; 5,000 concurrent WebSocket or SSE streams across the service |
| Availability | Edge 99.9% monthly, multi-AZ, at least 3 replicas with a disruption budget. A team's Paperclip is a single pod (AGT-7), so its availability is that of one pod: restart and reschedule within its volume's zone in under 5 minutes (p95); the edge's `503` page says so. Higher availability for Paperclip is PC-OQ-5 |
| Security | OWASP ASVS L2 for `afs-edge`; external penetration test of the public endpoint before production; security review sign-off (M4 exit) covers TEAM-3/TEAM-4 exceptions; no long-lived credentials in the edge (Pod Identity for its AWS calls, read-only DB role); edge sessions server-side or signed with a key from Secrets Manager rotated every 30 days |
| Encryption | TLS 1.2+ at the ALB and from the ALB to the edge; edge to Paperclip and agents to Paperclip inside Cilium WireGuard (PC-D7); Paperclip data at rest on the KMS-encrypted EBS volume and snapshots; Paperclip secrets under the environment KMS key |
| Observability | Edge OpenTelemetry traces and metrics (requests, latency, denials by reason, sessions, scan detections); dashboards and multi-window burn-rate alerts on edge availability and latency; reconciler metrics for registration and scanning |
| Privacy | No Paperclip content in AFS storage, logs, traces or events; edge records hold path templates, not raw paths with ids where Paperclip puts content in a path |
| Recovery | Paperclip restores from the collaboration agent's snapshots (AGT-9, CFG-5); the boot secrets and the master key are in Secrets Manager, so a volume restored in the same environment decrypts. Import into another environment (CFG-5) carries no secret values, so it generates new boot secrets; Paperclip then cannot decrypt the agent identities it stored and refuses those runs until the master key is copied by the restore runbook (PC-OQ-8). RPO is the snapshot interval (default 24 h), recorded as such |

## 9. Architecture summary

```
Internet ──► Route 53 *.collab.<domain> ──► public ALB (TLS, WAF) ──► afs-edge (afs-system, ≥3 pods)
                                                                     │ host → team, SSO, authz, scan
                                                                     ▼
                ┌─────────────── ns afs-t-<slug> ──────────────────────────────────────────┐
                │  Service paperclip:3100 ──► collaboration agent pod (one identity)       │
                │                              ├─ Paperclip server (+ embedded Postgres)   │
                │                              └─ Hermes (orchestrator, hermes_local)      │
                │  worker agents (connected) ──► paperclip:3100   (pull work, report)       │
                └──────────────────────────────────────────────────────────────────────────┘
afs-reconciler ──► paperclip:3100 (managed registration, roster guard, scanning)
collaboration pod ──► afs-gateway (Bedrock) · Secrets Manager <svc>/<ns>/<agent>/paperclip/* · catalog egress
```

The solution design gains §4 row *Public ingress* and a §3.1 component entry for `afs-edge`; the
contracts gain the operations, permissions, events and tables named above. Each change lands in the
provider first: `-db` 000020, then `-restapi` (`api/openapi.yaml`, edge, reconciler, Terraform), then
`@afs/sdk` and the console, and the CLI.

## 10. Release plan

| Milestone | Scope | Exit criteria |
|---|---|---|
| C1 Collaboration agent | `-db` 000020; COL-1..8, COL-10, COL-11, COL-12 manual, COL-22, SEC-7, COL-26, COL-28; T3, T16 (status, connections), CLI and SDK for them | A team runs Paperclip; two connected agents pull work; isolation tests prove no new reachability |
| C2 Public web UI | `afs-edge`, public ALB and WAF; COL-15..18, COL-20, COL-21, COL-23, COL-27, COL-30, COL-31; S2, S3, S10 tab, V3 | A member signs in through Okta and Entra in dev; denied cases and removal within 60 s pass; pen test booked |
| C3 REST API and managed mode | COL-12 managed, COL-13, COL-14, COL-19, COL-24, COL-25, COL-29, COL-32; `invoke-api` | A pipeline calls Paperclip with a team key; managed registration keeps the roster in step; scanning blocks and detects |
| C4 People and reports | COL-9, COL-33, COL-36 | Member sync and collaboration reports in dev; security review signed off |

## 11. Dependencies

| Dependency | Needed for | Owner |
|---|---|---|
| `agentic-team-w-paperclip` image with Paperclip and Hermes, published by digest | COL-2, COL-4 | Agentic Teammates project |
| That image reading `PAPERCLIP_API_URL`, `PAPERCLIP_AGENT_ID` and `PAPERCLIP_AGENT_API_KEY` from env (today it reads `instance.yaml` refs) and not generating boot secrets when they are set (it already prefers supplied values) | COL-7, COL-10 | Agentic Teammates project |
| Paperclip: `authenticated` + `public` mode, AWS Secrets Manager provider with prefix and KMS, agent and board API keys, roster and invite APIs, `low_trust_review` preset | COL-6, SEC-7, COL-12, COL-13, COL-29, COL-33 | Paperclip upstream (version pinned in the template) |
| Okta and Entra ID: one redirect URI per environment on the collaboration client (or the existing console client); groups claim | COL-17 | Enterprise identity team |
| Public DNS zone and wildcard certificate for `collab.base_domain` | COL-15 | Platform, network team |
| AWS WAF, internet-facing ALB in public subnets, AWS Load Balancer Controller or Terraform-managed target group | COL-15, COL-30 | Platform |
| Corporate approval for an internet-facing endpoint (or the CIDR allow list) | COL-23 | Security |

## 12. Decisions, risks and open questions

### 12.1 Decisions (Claude, for J's review)

| # | Question | Decision |
|---|---|---|
| PC-D1 | How does the public endpoint fit TEAM-3/TEAM-4? | One AFS-owned public entry (`afs-edge` behind one public ALB with WAF), never a team-owned load balancer or Ingress. Teams still cannot publish anything; the reconciler renders the only exception. One shared ALB keeps cost flat and needs no per-team listener rules, and the edge, not the ALB, does SSO, so each team keeps its own provider |
| PC-D2 | Who decides access to Paperclip? | The edge, with the same `internal/authz` code and role bindings as `afs-api`, on every request. Paperclip's own login stays (it has no OIDC), but it is never the control: removing an AFS binding cuts access within 60 s |
| PC-D3 | How does "one agent = one identity = one pod" hold with Paperclip and Hermes in one pod? | The pod is one AFS agent. Paperclip's orchestrator runs as Hermes in that pod and is that agent. Any other Paperclip agent must be its own AFS agent in its own pod; local-adapter extras are flagged (COL-13) because AFS cannot attribute them separately |
| PC-D4 | Where do Paperclip's own secrets go? | Paperclip's AWS Secrets Manager provider under the reserved prefix `<service>/<namespace>/<agent>/paperclip/`, with the collaboration role allowed to write only there. Forbidding Paperclip secrets would push connector tokens into its database; this keeps them under IAM, KMS, tags and team deletion. It is the one exception to SEC-2, listed read-only in AFS |
| PC-D5 | How do agents connect? | Pull only, inside the namespace, by Service DNS, with a Paperclip agent key per agent delivered as a secret binding. No agent traffic goes through the internet endpoint, and Paperclip never connects into agents |
| PC-D6 | Who may write in Paperclip? | New team role *team collaborator* (viewer plus Paperclip writes and API). Viewers are read-only by HTTP method at the edge. Without the role, every engineer who talks to agents would have to be team-admin |
| PC-D7 | TLS on the in-namespace hop? | Paperclip serves HTTP. The hop is inside Cilium's WireGuard encryption and the namespace policy; recorded as the one exception to the root PRD's TLS-every-hop rule rather than adding a sidecar the containers would have to know about |
| PC-D8 | Defaults | Web UI on, REST API off at creation; `mayExposeCollaboration` on per team; `collab.public_endpoints` on; content scanning `block`; registration `manual` until managed mode ships, then `managed` for new collaboration agents |
| PC-D9 | Hostname | `<team-slug>.<collab.base_domain>`, wildcard DNS and certificate, so team names stay out of certificate transparency; a deleted team's hostname is held for 30 days |
| PC-D10 | Pools, push adapters, inbound webhooks | Out of scope (section 3); each would widen the opening or break per-agent identity |

### 12.2 Risks

| # | Risk | Owner | Response |
|---|---|---|---|
| PC-R1 | The internet-facing endpoint is a new attack surface for a Fortune-100 environment | Security | WAF, SSO and AFS authorization before any Paperclip code runs; optional corporate CIDR allow list; ASVS L2 and a pen test before production; per-team kill switch and service-wide kill switch |
| PC-R2 | Prompt injection through Paperclip content steers agents | Security, teams | Only authenticated team members write; viewers read-only; per-agent egress, secrets, IAM and budget limit the blast radius; Paperclip's `low_trust_review` for external content; denied-spike alerts. Residual risk accepted: AFS cannot judge content |
| PC-R3 | People paste credentials into Paperclip | Security | Scanning blocks at the edge, detects agent writes, never stores the value; Paperclip's secret settings land in the managed hierarchy |
| PC-R4 | Double sign-in (AFS SSO then Paperclip) annoys users | Product | Accepted for C2; member sync (COL-33) reduces it; PC-OQ-1 tracks removing it |
| PC-R5 | Paperclip upstream changes its auth, roster or secret APIs | Platform | Pin the Paperclip version in the template's digest; contract tests against the pinned version; managed mode degrades to `RegistrationHealthy=False` without breaking agents |
| PC-R6 | A single Paperclip pod is a single point of failure for the team's coordination | Platform | Agents keep working on claimed work while Paperclip restarts; daily snapshots; PC-OQ-5 |
| PC-R7 | The reconciler gains read access to one secret per team (the board key) and network access into namespaces | Security | Exact-name IAM condition, port 3100 to the Paperclip pod only, all calls logged; managed mode can stay off per team |

### 12.3 Open questions

Each has an owner, when it is needed and the default AFS builds to.

| # | Question | Owner | Needed by | Default |
|---|---|---|---|---|
| PC-OQ-1 | Can Paperclip trust an authenticating proxy (signed header or token handoff) so people sign in once? | J, Paperclip upstream | C4 | Double sign-in; member sync (COL-33) |
| PC-OQ-2 | How does AFS complete Paperclip's first-admin bootstrap and obtain a board API key without a person in the pod (`auth bootstrap-ceo` prints an invite; public mode disables browser claim)? | `-restapi`, Agentic Teammates | C1 spike | A one-shot bootstrap step in the image's entrypoint, triggered by env, that writes the invite to the pod log for `manual` mode and creates the board key into the agent's managed secret path for `managed` mode |
| PC-OQ-3 | Does Paperclip let an operator turn off local adapters other than the orchestrator, or close sign-up, by configuration? | Paperclip upstream | C3 | Detect and flag (COL-13, COL-27) |
| PC-OQ-4 | Does Paperclip use path segments that carry content or ids we must template out of edge records? | `-restapi` | C2 | Record the route template from a maintained list; unknown paths recorded as their first segment only |
| PC-OQ-5 | Does any team need Paperclip highly available (external RDS database, more than one pod)? | J | After C4 | No; single pod with snapshots (non-goal) |
| PC-OQ-6 | Use the console's existing OIDC client for the edge, or a separate collaboration client per provider? | Enterprise identity team | C2 | A separate client per provider, so its redirect URI and consent can be governed on their own |
| PC-OQ-7 | Should agents' writes into Paperclip also be blocked (not only detected) when they contain credentials? | Security | C3 | Detect and alert only; blocking would need a proxy agents talk through, which SEC-6 rules out |
| PC-OQ-8 | When a team is imported into another environment, should AFS carry the Paperclip master key across (an exception to "no secret values in bundles"), or should operators copy it by runbook? | J, security | C1 | Runbook copy between Secrets Manager accounts; the bundle never holds it |

## 13. Glossary

| Term | Meaning |
|---|---|
| Collaboration agent | The one AFS agent per team built from a Paperclip template; runs Paperclip and its Hermes orchestrator in one pod |
| Connected agent | A worker agent that receives Paperclip's in-namespace URL and its own Paperclip key |
| `afs-edge` | The AFS service that is the only public entry to a team's Paperclip: SSO, authorization, scanning, limits |
| Surface | The web UI or the REST API of a team's Paperclip, each switched on or off by the team |
| Registration mode | `manual` (team-admin registers agents in Paperclip) or `managed` (the reconciler keeps the roster in step) |
| Team collaborator | Team role that may write in Paperclip and use its REST API, without AFS admin rights |

## 14. Review record

`review-prd` pass, 2026-11-22 (dev-flow). Verdict after fixes: **Ready for spec**.

| Dimension | Status | Note |
|---|---|---|
| Problem clarity | ✅ Pass | Four concrete problems, each tied to an existing requirement it collides with |
| Scope definition | ✅ Pass | Goals with measures; ten explicit non-goals |
| Functional completeness | ✅ Pass | COL-1..36 and SEC-7 cover PG1..PG6; section 6.8 lists every existing requirement that changes |
| NFR coverage | ✅ Pass | Performance, scale, availability, security, encryption, observability, privacy, recovery |
| Acceptance criteria | ✅ Pass | Given / When / Then per product story and per repository story, with timings and error codes |
| Dependency identification | ✅ Pass | Upstream images, Paperclip features, IdP, DNS, WAF, corporate approval |
| Open questions | ✅ Pass | PC-OQ-1..8, each with owner, milestone and default |

Fixed in this pass: the edge's OIDC client needed a client secret reference (COL-17, DB-US-47); secret names
followed the AFS lowercase convention and reserved `paperclip` (COL-7, DB-US-46); tokens on the REST API
surface use `afs-api`'s issuer and audience rules (COL-19); agents that predate the collaboration agent are
not connected silently (COL-10); service admin entry into a team's Paperclip is visible to the team (COL-31);
access counts needed a home in the database (COL-36, DB-US-47); import into another environment and the
Paperclip master key (section 8, PC-OQ-8); `api_keys.role` also takes the new role (DB-US-45); the one-per-team
index follows the existing `deleted_at IS NULL` pattern (DB-US-44).

