# Skill: the `afs` CLI

> **Status banner.** Release `v1.0.1` of `enterprise-agent-factory-service-cli` is prepared on `main`; the
> repository owner pushes the tag, and it is not yet published: no signed archives, no Homebrew formula and no tap exist yet. Until the
> release is published, build from source (`make build` writes `bin/afs`). This file describes the CLI at
> `main`; check `afs --version` and `afs <service> <operation> help` for the truth on a given build.

`afs` is the command line to the Enterprise Agent Factory Service. It calls the AFS REST API; the API decides
what the caller may do. Full documentation: the CLI repository's `user-docs/` and the generated reference
`user-docs/reference/` (links below are to files in that repository).

## Install

```bash
git clone https://github.com/stainedhead/enterprise-agent-factory-service-cli.git
cd enterprise-agent-factory-service-cli && make build && ./bin/afs --version
```

Put `bin/afs` on `PATH`. Release archives and Homebrew come with the published release (`user-docs/install.md`).

## Configure and authenticate

```bash
afs configure                       # endpoint URL (https only), default output, default team id; writes ~/.afs/config
afs configure sso && afs sso login  # people: device-flow sign-in; token cached with mode 0600
afs sso get-caller-identity         # who am I, which role
```

Automation uses an API key: `AFS_API_KEY` in the environment, or `api_key` in `~/.afs/credentials` (mode 0600).
Order: `AFS_API_KEY`, credentials file, cached SSO session, workload token file. Other environment variables:
`AFS_PROFILE`, `AFS_ENDPOINT_URL`, `AFS_DEFAULT_OUTPUT`. Never put a token, API key or secret value on a command line.
Secret values come from `file://PATH`, `fileb://PATH` or `-` (standard input) only.

## Command shape

`afs <service> <operation> [--options]`. Services: `teams`, `agents`, `pools`, `secrets`, `budgets`, `members`,
`api-keys`, `audit`, `reports`, `models`, `work-orders`, `swarm-templates`, `collaboration`, `admin`, plus `configure`,
`sso` and `completion`. Operations are kebab-case verb-noun and map to one API call each (`list-teams` is `ListTeams`).
Options mirror API fields (`--team-id`, `--amount-usd`); lists are space-separated.

```bash
afs teams list-teams --output table
afs teams create-team --generate-cli-skeleton > team.json     # edit, then:
afs teams create-team --cli-input-json file://team.json
afs agents list-agents --team-id team_... --output table
afs agents update-agent --team-id team_... --agent-id agt_... --if-match 4 ...   # updates send If-Match
afs help; afs <service> help; afs <service> <operation> help
```

Global options: `--profile --endpoint-url --output json|yaml|table|text|csv --query` (JMESPath) `--no-paginate
--max-items --page-size --starting-token --cli-input-json --generate-cli-skeleton --debug --no-cli-pager --color
--version`. `json` output is the stable machine contract. Lists auto-paginate; with `--max-items` the command prints
`NextToken` for `--starting-token`. `--wait` on long operations polls until the resource is ready.

Errors go to stderr as `An error occurred (<Code>) when calling the <Operation> operation: <message>`.
Exit codes: 0 success, 252 usage error, 254 service error (including `AccessDenied`), 255 other (network, config).

## Team collaboration (Paperclip)

Contract: API 1.3 and later. Reference: `user-docs/collaboration.md`, `user-docs/reference/collaboration.md`.
The collaboration agent is an ordinary agent with `--role collaboration`, made from a template whose capabilities
include `paperclip`; a team has at most one. Find such templates with
`afs agents list-agent-templates --capability paperclip`.

```bash
afs agents create-agent --team-id team_... --name paperclip --role collaboration --template paperclip \
  --image registry.example.com/agents/paperclip@sha256:... --model-id <model> --wait

afs collaboration describe-collaboration --team-id team_...
afs collaboration put-collaboration --team-id team_... --web-ui-enabled --no-rest-api-enabled \
  [--registration-mode manual|managed] [--if-match N] [--wait]
afs collaboration list-collaboration-links --team-id team_... [--link-state failed] [--connect | --no-connect]
afs collaboration connect-agent    --team-id team_... --agent-id agt_... [--paperclip-agent-id ag_...]   # id: manual mode only
afs collaboration disconnect-agent --team-id team_... --agent-id agt_...
afs collaboration rotate-collaboration-keys --team-id team_...
afs collaboration invoke-api --team-id team_... [--method POST] --path /api/issues \
  [--body file://issue.json] --paperclip-key-file ./pc.key [--collab-url https://<team>.<base domain>] [--include]
```

- `put-collaboration` replaces both switches (give each as `--x` or `--no-x`). `--wait` polls until the endpoint is
  `Ready` at your change's generation.
- `invoke-api` sends one request to the team's Paperclip REST API through the edge. The AFS credential (API key or SSO
  session) proves who you are; the Paperclip key proves what you may do in Paperclip. The key comes from a mode-0600
  file or stdin (`--paperclip-key-file -`), never an option value. The response is printed unchanged; exit 0 for 2xx
  and 3xx, 254 for an error answer, 252 for a bad option, 255 for a local problem. Workload tokens are refused: use an
  API key. Only `https` on port 443 is accepted; `--query`, `--output` and `--wait` do not apply.
- Reports: `afs reports get-team-report --team-id team_... --kind collaboration --range 7d --group-by day,person`
  and `afs reports get-service-report --kind collaboration --group-by team`. Extra `--group-by` values: `surface`,
  `reason`, `person`. The report never holds what people wrote and cannot be scheduled.
- Secrets: `afs secrets list-secrets --managed-by user|afs|paperclip`. Secrets managed by AFS or Paperclip cannot be
  updated, deleted or given a value (`409 Conflict`); `rotate-secret` works on AFS-managed ones except the master key.
- Role for people and keys who use Paperclip but change no AFS configuration: `--role team_collaborator`.
- Service administrators: `afs admin put-setting --key collab.base_domain --value '"collab.example.com"'` (and the
  other `collab.*` keys), `afs admin update-identity-provider --collab-client-id ... --collab-client-secret-arn <ARN>`,
  `afs teams update-team --may-expose-collaboration`, `afs admin list-collaboration-endpoints`.
- Swarm templates may carry `"collaboration": {"templateId": "tpl_..."}` in the spec file.
