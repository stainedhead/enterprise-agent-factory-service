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
  replica; pause scales it to zero. A team adds capacity by adding agents. The exception is the phase 2
  swarm pool (AGT-8): its workers do similar work across many repositories, need no separate identities,
  and share one swarm-level identity, secret set and budget, so a pool has a worker count.
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
