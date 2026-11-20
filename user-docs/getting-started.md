# Getting started

## Clone the set

```bash
git clone https://github.com/stainedhead/enterprise-agent-factory-service.git
cd enterprise-agent-factory-service
for r in db restapi cli website; do
  git clone https://github.com/stainedhead/enterprise-agent-factory-service-$r.git
done
```

The root `.gitignore` keeps the children untracked, so each stays its own repository.

## Toolchains

| Repository | Install |
|---|---|
| -db, -restapi, -cli | Go 1.27 (`go.mod` pins the toolchain, so any Go ≥ 1.21 downloads it) and `make`. `-db` integration tests also need PostgreSQL 17 or Docker |
| -website | Node.js 22 or later, pnpm 12 (`corepack enable`) |

## Claude Code plugins

```
/plugin marketplace add https://github.com/stainedhead/shared-plugins
/plugin install dev-flow
/plugin install repo
```

## Where to go

| You want to | Go to |
|---|---|
| Understand the architecture | `docs/solution-design.md` in this repository |
| Read the requirements and UI | `enterprise-agent-factory-service-initial-PRD.md` in this repository |
| Change tables, roles or row-level security | `enterprise-agent-factory-service-db/` |
| Change the API, reconciler, gateway or billing | `enterprise-agent-factory-service-restapi/` |
| Change the `afs` CLI | `enterprise-agent-factory-service-cli/` |
| Change the SDK or web console | `enterprise-agent-factory-service-website/` |
| Specify a feature that touches both | `specs/` in this repository |
