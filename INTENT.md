# Intent

## Purpose
Give every delivery team in the enterprise a safe, governed way to work with a team of AI agents, without
each team building and securing its own agent infrastructure. The Enterprise Agent Factory Service (AFS)
is a centrally run platform-engineering product: the platform team operates it and sets guardrails; teams
manage their own isolated software factory inside those guardrails.

This repository is the root of the product. It holds the requirements, the cross-repo design, the UI
mockups and cross-repo specs. It contains no code and does not vendor, submodule or otherwise track the
child repositories.

## The set it ties together
| Repository | What it is for |
|---|---|
| `enterprise-agent-factory-service-db` | The desired-state database: schema, migrations, roles, row-level security. |
| `enterprise-agent-factory-service-restapi` | The control plane: REST API with role-based access, the reconciler that applies desired state to EKS and AWS, the gateway that meters and caps Bedrock spend, and billing reconciliation. |
| `enterprise-agent-factory-service-cli` | The `afs` CLI for people and automation, in the style of the AWS CLI. |
| `enterprise-agent-factory-service-website` | The `@afs/sdk` TypeScript SDK and the web console built on it. |

## Goals
- **Isolation by default.** Each team's agents, secrets, IAM permissions, logs and budget are separate
  from every other team's. Namespace restrictions are the primary network boundary.
- **Spend that cannot run away.** Model spend is metered per call and stopped at a hard cap, not discovered
  hours later in the bill.
- **Attributable agents.** Every agent has its own identity; every change and every action traces to a
  named agent or person and a team.
- **Central management, team self-service.** Three roles (service admin, team-admin, team viewer), one API
  that enforces them, and three clients (console, CLI, SDK) that respect them.
- **Configuration you can carry and recover.** Desired state lives in PostgreSQL, is versioned and audited,
  can be exported to another account or cluster, and is re-applied continuously.
- **Long-running first, short-lived next.** Phase 1 serves development and maintenance teams. The design
  already carries the ephemeral lifecycle, lifetime budgets and event hooks for budgeted workloads, POCs
  and CVE remediation work orders.

## Non-goals
- The agent runtime itself (the Agentic Teammates project).
- External or multi-enterprise tenancy.
- Chargeback billing; AFS provides showback data by cost center.
- Source code, builds or releases in this root.
