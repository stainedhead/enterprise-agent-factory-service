# Technical details

Cross-repo technical reference. The architecture lives in [solution-design.md](solution-design.md);
this file records the facts that span the child repositories as they are built.

## Toolchains

| Repository | Toolchain (verified 2026-11-20) |
|---|---|
| enterprise-agent-factory-service-db | PostgreSQL 17 (RDS), Go 1.27.4, pgx v5.13, golangci-lint v2.15.0 |
| enterprise-agent-factory-service-restapi | Go 1.27.4, golangci-lint v2.15.0, govulncheck v1.8.0 |
| enterprise-agent-factory-service-cli | Go 1.27.4, golangci-lint v2.15.0, govulncheck v1.8.0 |
| enterprise-agent-factory-service-website | TypeScript 7.0.2 (native compiler), Node.js 22+, pnpm 12.21, Vite 8.3, Vitest 5.1, Biome 2.6, React 19.3 |

## Contract

`enterprise-agent-factory-service-restapi/api/openapi.yaml` (OpenAPI 3.1) is the API contract. `@afs/sdk` and the CLI
generate their wire types from it.

## Environments

## Data store

RDS PostgreSQL 17. Schema, migrations, roles and row-level security live in
`enterprise-agent-factory-service-db`; see its `docs/data-model.md`.
