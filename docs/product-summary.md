# Product summary

The Agent Factory Service (AFS) gives enterprise teams isolated, budget-capped software factories on
AWS EKS. A team-admin creates a team; AFS provisions a namespace with default-deny networking, an IAM
role, a Bedrock inference profile, secret delivery and log delivery, then runs the team's containerized
agents (agentic-teams runtime). Humans join as team-admins or team viewers; service admins run the
service. Spend on Bedrock is metered per request and stopped at the team's hard cap, and reconciled
daily against the AWS billing report.

Interfaces: REST API (Go), `afs` CLI (AWS CLI conventions), `@afs/sdk` (TypeScript), web console.

Requirements and UI: [initial PRD](../enterprise-agent-factory-service-initial-PRD.md).

Full design: [solution-design.md](solution-design.md).
