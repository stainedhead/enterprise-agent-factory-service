# Team model gateway (model-endpoint-gateway-PRD.md, PROPOSED), screens 56 to 68.
# Executed by gen.py after orch_screens.py, so it shares CSS, page(), opage(), navs and helpers.
# Proposal mockups only: nothing here is built.

CSS_GW = """
td.num{white-space:nowrap}
.tip .tipbox{bottom:auto;top:38px;z-index:2}
.rt{font-family:"DejaVu Sans Mono",monospace;font-size:12.5px;font-weight:700;white-space:nowrap}
.b-met{color:#006ce0;border-color:#006ce0}
.b-cap{color:#00802f;border-color:#00802f}
.b-quo{color:#855900;border-color:#855900}
.b-unm{color:#855900;border-color:#855900;background:#fffef0}
.b-terms{color:#7300e5;border-color:#7300e5}
.b-bi{color:var(--muted);border-color:#9aa5b1;background:#f3f3f7}
.b-sub{color:#0b6b6b;border-color:#0b6b6b}
.loc{display:inline-block;white-space:nowrap;border-radius:10px;padding:1px 9px;font-size:12px;font-weight:700}
.loc.ext{background:#fff1e6;color:#b45309}.loc.corp{background:#e8f3ff;color:#004a9e}.loc.ns{background:#eaf7ee;color:#00802f}.loc.aws{background:#f3f3f7;color:var(--muted)}
.pm{font-size:12.5px;color:var(--muted)}
.proposal{float:right;background:#7300e5;color:#fff;font-size:12px;font-weight:700;padding:2px 12px;border-radius:12px}
.hbar{display:flex;align-items:center;gap:8px}
.hbar .bar{flex:1}
.lat{display:grid;grid-template-columns:repeat(24,1fr);gap:3px;align-items:end;height:120px;border-bottom:1px solid var(--line)}
.lat i{display:block;background:#688ae8;border-radius:2px 2px 0 0}
.lat i.hi{background:#c33d69}
.slo{position:relative}
.slo .line{position:absolute;left:0;right:0;border-top:2px dashed var(--red)}
.slo .line span{position:absolute;right:0;top:-18px;font-size:11px;color:var(--red);font-weight:700}
.envbox{background:#0f141a;color:#d1d5db;border-radius:8px;padding:10px 14px;font-family:"DejaVu Sans Mono",monospace;font-size:12px;line-height:1.7}
.envbox b{color:#9ccaff;font-weight:400}
"""

PROPOSAL = '<div class="proposal">PROPOSAL · not built</div>'


def gpage(name, role, side, body, modal=""):
    page(name, role, side, f"<style>{CSS_ORCH}{CSS_GW}</style>" + PROPOSAL + body, modal)


def loc(kind):
    return {"ext": '<span class="loc ext">External</span>', "corp": '<span class="loc corp">Corporate</span>',
            "ns": '<span class="loc ns">In namespace</span>', "aws": '<span class="loc aws">AWS (VPC endpoint)</span>'}[kind]


def mb(kind):
    return {"met": '<span class="badge b-met">Metered</span>', "cap": '<span class="badge b-cap">Capped</span>',
            "quo": '<span class="badge b-quo">Token quota</span>', "unm": '<span class="badge b-unm">Unmetered</span>',
            "terms": '<span class="badge b-terms">Extra terms</span>', "bi": '<span class="badge b-bi">Built-in</span>',
            "sub": '<span class="badge b-sub">Fee capped</span>'}[kind]


def admin_nav_gw(on):
    side = admin_nav(on, orch=True)
    return side.replace('<a class="">Model catalog & pricing</a>',
                        '<a class="">Model catalog & pricing</a><a class="' + ("on" if on == "endpoints" else "") + '">Model endpoints</a>').replace(
        '<a class="on">Model catalog & pricing</a>', '<a class="on">Model catalog & pricing</a><a class="">Model endpoints</a>')


def team_nav_gw(on, role, team="payments-factory"):
    side = team_nav(on if on != "endpoints" else "_", role, team=team, orch=True)
    return side.replace('<a class="">Models</a>', '<a class="">Models</a><a class="' + ("on" if on == "endpoints" else "") + '">Model endpoints</a>').replace(
        '<a class="on">Models</a>', '<a class="on">Models</a><a class="">Model endpoints</a>')


# route, display, protocol, location, pricing, badges, teams, health, cred
SVC_ROUTES = [
    ("bedrock", "Amazon Bedrock", "Bedrock, Anthropic Messages", "aws", "Per token", ("bi", "met", "cap"), "42", ("ok", "Healthy"), "Gateway role"),
    ("openai-prod", "OpenAI", "Chat, Responses, Embeddings", "ext", "Per token", ("met", "cap"), "18", ("ok", "Healthy"), "Per team (18 of 18 set)"),
    ("openrouter", "OpenRouter", "Chat", "ext", "Per token", ("met", "cap", "terms"), "3", ("ok", "Healthy"), "Per team (2 of 3 set)"),
    ("ml-platform", "Enterprise ML platform", "Chat, Embeddings", "corp", "Per token · transfer price", ("met", "cap"), "26", ("warn", "Degraded"), "Shared key"),
    ("nous-portal", "Nous Portal (Hermes models)", "Chat", "ext", "Per token", ("met", "cap"), "4", ("ok", "Healthy"), "Per team (4 of 4 set)"),
    ("opencode-go", "OpenCode Go (subscription)", "Chat", "ext", "Subscription · fee per key", ("met", "sub", "terms"), "0", ("pend", "No traffic"), "Per team"),
    ("eval-sandbox", "Evaluation sandbox", "Chat", "corp", "Free", ("met",), "0", ("pend", "Disabled"), "None"),
]


def svc_rows(sel=None):
    out = []
    for r, d, p, l, pm, bs, teams, (hk, ht), cred in SVC_ROUTES:
        en = st("pend", "Off") if r == "eval-sandbox" else st("err", "Off by provider policy") if r == "opencode-go" else st("ok", "On")
        out.append(f'<tr class="{"sel" if r == sel else ""}"><td><span class="radio{" on" if r == sel else ""}"></span></td><td><a class="rt">{r}</a><div class="small muted">{d}</div></td>'
                   f'<td class="small">{p}</td><td>{loc(l)}</td><td class="small">{pm}</td><td>{" ".join(mb(b) for b in bs)}</td>'
                   f'<td>{en}</td><td class="num">{teams}</td><td>{st(hk, ht)}</td><td class="small">{cred}</td></tr>')
    return "".join(out)


# ---------------------------------------------------------------------------------------------- Service admin
gpage("56-admin-model-endpoints", "admin", admin_nav_gw("endpoints"), f"""
<div class="crumbs"><a>Agent Factory</a> › Model endpoints</div>
<div class="hdr"><div><h1>Model endpoints <span class="info">Info</span></h1>
<div class="desc">OpenAI-compatible model services agents reach through their team gateway, by route name. Every call through a route is metered; per-token routes count against team budgets and hard caps.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Create endpoint</span></div></div>
<div class="alert warn"><span class="ic">⚠</span><div><b>ml-platform is degraded for 4 teams.</b> p95 time to first token is 7.8 s over the last 15 minutes (objective 5 s). Calls still flow; teams were notified. <a>Open inference report</a></div></div>
<div class="alert"><span class="ic">ⓘ</span><div class="small"><b>Provider policy:</b> external inference allowed · 4 of 5 external providers on · OpenCode Go off (waiting for the provider to confirm gateway use). <a>Open provider policy</a></div></div>
<div class="card"><div class="ch"><div><h2>Service endpoints <span class="cnt">(7)</span></h2><div class="sub">Switched-on endpoints are offered to every team; each team opts in. Endpoints with extra terms are selected per team by a service admin. Off means off for every team.</div></div>
<div class="btns"><span class="btn dis">Turn off</span><span class="btn">Edit</span></div></div>
<div class="tools"><div class="filter">🔍 Find endpoints</div><span class="sel">Any location ▾</span><span class="sel">Any pricing mode ▾</span><div class="pager">‹ <b>1</b> › &nbsp; ⚙</div></div>
<table><tr><th></th><th>Route</th><th>Protocol</th><th>Location</th><th>Pricing</th><th>Budget control</th><th>Service</th><th class="num">Teams</th><th>Health (15 min)</th><th>Credential</th></tr>
{svc_rows("openai-prod")}</table></div>
<div class="grid g2">
<div class="card"><div class="ch"><div><h2>Team-declared endpoints <span class="cnt">(4)</span></h2><div class="sub">Declared by teams you allow to add endpoints. Read here; managed by each team.</div></div><a>Teams allowed (6)</a></div>
<table><tr><th>Team</th><th>Route</th><th>Location</th><th>Pricing</th><th>Health</th></tr>
<tr><td><a>payments-factory</a></td><td class="rt">coder-vllm</td><td>{loc('ns')}</td><td class="small">Capacity</td><td>{st('ok','Healthy')}</td></tr>
<tr><td><a>search-relevance</a></td><td class="rt">rerank-tgi</td><td>{loc('ns')}</td><td class="small">Capacity</td><td>{st('ok','Healthy')}</td></tr>
<tr><td><a>data-platform</a></td><td class="rt">azure-oai-east</td><td>{loc('ext')}</td><td class="small">Per token</td><td>{st('ok','Healthy')}</td></tr>
<tr><td><a>mobile-platform</a></td><td class="rt">ollama-test</td><td>{loc('ns')}</td><td class="small">Free</td><td>{st('err','Unavailable')}</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>Direct LLM access</h2><div class="sub">External systems of category LLM that agents could call without a route</div></div></div><div class="cb">
<table><tr><th>External system</th><th>Linked route</th><th>Direct access</th></tr>
<tr><td>OpenAI {mb('unm')}</td><td class="rt">openai-prod</td><td>{st('pend','Blocked while route exists')}</td></tr>
<tr><td>OpenRouter {mb('unm')}</td><td class="rt">openrouter</td><td>{st('warn','Override for 1 team')}</td></tr>
<tr><td>Nous Portal {mb('unm')}</td><td class="rt">nous-portal</td><td>{st('pend','Blocked while route exists')}</td></tr></table>
<div class="small muted" style="margin-top:8px">A route host is reachable only from team gateways, so calls through a route cannot bypass metering. Direct access stays <b>Unmetered</b> and is off by default.</div></div></div>
</div>
<div class="card"><div class="ch"><h2>Pending price proposals <span class="cnt">(2)</span></h2><a>Review all</a></div>
<table><tr><th>Route</th><th>Model</th><th>Current in / out $/MTok</th><th>Proposed in / out $/MTok</th><th>Source</th><th></th></tr>
<tr><td class="rt">openai-prod</td><td class="mono">gpt-4.1-mini</td><td>0.40 / 1.60</td><td><b>0.35 / 1.40</b></td><td class="small">Provider price page, 2026-11-23</td><td><span class="btn sm">Review</span></td></tr>
<tr><td class="rt">openrouter</td><td class="mono">qwen3-coder</td><td class="muted">— (not callable)</td><td><b>0.22 / 0.95</b></td><td class="small">LiteLLM price list</td><td><span class="btn sm">Review</span></td></tr></table></div>
""")

gpage("57-admin-create-model-endpoint", "admin", admin_nav_gw("endpoints"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Model endpoints</a> › Create endpoint</div>
<div class="wiz"><div class="steps">
<div><div class="n">Step 1</div><b>Endpoint and route</b></div>
<div><div class="n">Step 2</div><b>Connection and credential</b></div>
<div class="on"><div class="n">Step 3</div><b>Models and pricing</b></div>
<div class="todo"><div class="n">Step 4</div><b>Access and objectives</b></div>
<div class="todo"><div class="n">Step 5</div><b>Review and create</b></div></div>
<div style="flex:1;max-width:980px"><div>
<div class="hdr"><div><h1>Models and pricing</h1><div class="desc">Route <span class="rt">openrouter</span> · OpenAI Chat protocol · https://openrouter.ai/api/v1</div></div></div>
<div class="card"><div class="ch"><div><h2>Pricing mode</h2><div class="sub">Decides how calls are costed and whether hard caps apply.</div></div></div><div class="cb">
<div class="grid g3">
<div class="tile on"><b><span class="radio on"></span> Per token</b><span>Each model has an input and output price. The gateway reserves the worst case before the call and settles to actual usage. <b>Counts against budgets and hard caps.</b></span></div>
<div class="tile"><b><span class="radio"></span> Capacity</b><span>Cost is hardware (CUR or a monthly amount), allocated by token share. Tokens metered and reported; no hard limit.</span></div>
<div class="tile"><b><span class="radio"></span> Free</b><span>Charged elsewhere. Tokens metered, cost zero.</span></div>
</div></div></div>
<div class="card"><div class="ch"><div><h2>Models on this route <span class="cnt">(3)</span></h2><div class="sub">Agents may call only listed models. A model without a price in force is refused (model_not_priced).</div></div><div class="btns"><span class="btn sm">Import from LiteLLM price list</span><span class="btn sm">Add model</span></div></div>
<table><tr><th>Model name (sent in <span class="mono">model</span>)</th><th class="num">Max output tok</th><th class="num">Input $/MTok</th><th class="num">Cached input $/MTok</th><th class="num">Output $/MTok</th><th>Price source</th></tr>
<tr><td class="mono">anthropic/claude-sonnet-4.5</td><td class="num">64,000</td><td class="num">3.00</td><td class="num">0.30</td><td class="num">15.00</td><td class="small">Manual</td></tr>
<tr><td class="mono">openai/gpt-5.1</td><td class="num">128,000</td><td class="num">1.25</td><td class="num">0.125</td><td class="num">10.00</td><td class="small">Provider page</td></tr>
<tr><td class="mono">qwen/qwen3-coder</td><td class="num">32,000</td><td class="num muted">—</td><td class="num muted">—</td><td class="num muted">—</td><td>{st('warn','Proposal waiting')}</td></tr></table>
<div class="cb"><div class="field" style="margin-top:12px"><label>{tg(True)} Use the provider's reported cost when larger</label><div class="hint">OpenRouter returns <span class="mono">usage.cost</span>. The gateway settles to the larger of that and the token-price cost and records both, so fees the price table does not model still count.</div></div>
<div class="field"><label>Optional per-call fee (USD)</label><div class="input" style="width:200px">0.00</div></div></div></div>
<div class="alert"><span class="ic">ⓘ</span><div class="small"><b>Hard-cap guarantee.</b> Per-token routes use the Bedrock reservation rule: the gateway writes the reserved output limit into every request, so spend can exceed a cap only by one in-flight call per pod. Calls with no usage in the response are settled at the reserved amount.</div></div>
</div>
<div><div class="card"><div class="ch"><h2>Equivalent CLI</h2></div><div class="cb">
<div class="code">afs model-endpoints create-model-endpoint \\<br>&nbsp; --slug openrouter \\<br>&nbsp; --protocol openai_chat \\<br>&nbsp; --location external \\<br>&nbsp; --base-url https://openrouter.ai/api/v1 \\<br>&nbsp; --auth-kind bearer \\<br>&nbsp; --credential-mode per_team \\<br>&nbsp; --pricing-mode per_token \\<br>&nbsp; --requires-terms</div>
<div class="code" style="margin-top:8px">afs model-endpoints put-endpoint-models \\<br>&nbsp; --endpoint-id mep_01JE… \\<br>&nbsp; --models file://openrouter-models.json</div>
<div class="small muted" style="margin-top:8px">Credentials are set separately with <span class="mono">put-model-endpoint-credential</span>, from a file, stdin or a prompt.</div></div></div>
<div style="display:flex;justify-content:flex-end;gap:8px"><span class="btn" style="border:0">Cancel</span><span class="btn">Previous</span><span class="btn p">Next</span></div></div>
</div></div>
""")

gpage("58-admin-endpoint-detail", "admin", admin_nav_gw("endpoints"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Model endpoints</a> › openai-prod</div>
<div class="hdr"><div><h1><span class="rt" style="font-size:22px">openai-prod</span> {st('ok','Healthy')} <span class="info">Info</span></h1>
<div class="desc">OpenAI · https://api.openai.com/v1 · Chat, Responses, Embeddings · {loc('ext')} {mb('met')} {mb('cap')}</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn">Edit</span></div></div>
<div class="tabs"><span>Details</span><span>Models & prices</span><span class="on">Teams & credentials</span><span>Health</span><span>Usage</span><span>Revisions</span></div>
<div class="grid g4 kpi">
<div class="card"><div class="cb"><div class="small muted">Teams with this route</div><div class="big">18</div><div class="small muted">opted in: 17 by their team-admins, 1 by a service admin</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Credential mode</div><div class="big g" style="font-size:20px;margin:6px 0">Per team</div><div class="small muted">One OpenAI project key per team, so OpenAI's invoice splits by team</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Spend, month to date</div><div class="big">$9,412</div><div class="small muted">4.1 B tokens · 0.3% estimated usage</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Provider reconciliation</div><div class="big g" style="font-size:20px;margin:6px 0">{st('ok','Within 1.2%')}</div><div class="small muted">OpenAI organization costs, yesterday</div></div></div>
</div>
<div class="card"><div class="ch"><div><h2>Teams <span class="cnt">(18)</span></h2><div class="sub">Credential values are write-only and never shown. Each lives at <span class="mono">afs/&lt;namespace&gt;/_gateway/openai-prod</span>, readable only by that team's gateway.</div></div><div class="btns"><span class="btn dis">Rotate credential</span><span class="btn">Set credential</span></div></div>
<div class="tools"><div class="filter">🔍 Find teams</div><span class="sel">Any credential state ▾</span><div class="pager">‹ <b>1</b> 2 › &nbsp; ⚙</div></div>
<table><tr><th></th><th>Team</th><th>Opted in by</th><th>Credential</th><th>Last rotated</th><th>Team gateway</th><th class="num">Spend MTD</th><th class="num">Calls (24 h)</th><th class="num">Errors (24 h)</th></tr>
<tr><td><span class="cb2"></span></td><td><a>payments-factory</a></td><td class="small">Team-admin</td><td>{st('ok','Set')}</td><td class="small">2026-11-02</td><td>{st('ok','Ready · v1.2.0')}</td><td class="num">$2,180</td><td class="num">14,210</td><td class="num">0.2%</td></tr>
<tr><td><span class="cb2"></span></td><td><a>search-relevance</a></td><td class="small">Team-admin</td><td>{st('ok','Set')}</td><td class="small">2026-10-19</td><td>{st('ok','Ready · v1.2.0')}</td><td class="num">$3,040</td><td class="num">22,904</td><td class="num">0.4%</td></tr>
<tr><td><span class="cb2"></span></td><td><a>data-platform</a></td><td class="small">Service admin</td><td>{st('ok','Set')}</td><td class="small">2026-11-20</td><td>{st('ok','Ready · v1.2.0')}</td><td class="num">$1,377</td><td class="num">6,018</td><td class="num">0.1%</td></tr>
<tr><td><span class="cb2"></span></td><td><a>cve-2026-41873-swarm</a></td><td class="small">Team-admin</td><td>{st('err','Missing')}</td><td class="small muted">—</td><td>{st('ok','Ready · v1.2.0')}</td><td class="num">$0</td><td class="num">0</td><td class="num muted">—</td></tr>
<tr><td><span class="cb2"></span></td><td><a>mobile-platform</a></td><td class="small">Team-admin</td><td>{st('ok','Set')}</td><td class="small">2026-09-30</td><td>{st('inf','Rolling · v1.2.1 (ring 2)')}</td><td class="num">$812</td><td class="num">3,330</td><td class="num">0.3%</td></tr></table></div>
<div class="alert warn"><span class="ic">⚠</span><div class="small"><b>cve-2026-41873-swarm has the route but no credential.</b> Its agents get <span class="mono">503 Unavailable</span> with reason <span class="mono">credential_missing</span> on this route until a team-admin or service admin sets one.</div></div>
""")

LAT = [3.1, 2.9, 2.8, 2.6, 2.7, 2.9, 3.4, 3.9, 4.2, 4.6, 4.9, 5.4, 6.8, 7.8, 7.1, 5.2, 4.4, 4.0, 3.7, 3.5, 3.3, 3.2, 3.0, 2.9]


def lat_chart(vals=LAT, slo=5.0, scale=13):
    bars = "".join(f'<i class="{"hi" if v > slo else ""}" style="height:{int(v*scale)}px"></i>' for v in vals)
    return (f'<div class="slo"><div class="line" style="bottom:{int(slo*scale)}px"><span>Objective p95 {slo:.0f} s</span></div><div class="lat">{bars}</div></div>'
            '<div class="lg"><span><i style="background:#688ae8"></i>p95 time to first token, per hour</span><span><i style="background:#c33d69"></i>Over objective</span><span>Last 24 h</span></div>')


gpage("59-admin-inference-report", "admin", admin_nav_gw("reports"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Reports & analytics</a> › Inference</div>
<div class="hdr"><div><h1>Inference <span class="info">Info</span></h1><div class="desc">Every model call through team gateways, Bedrock and routes, all teams. From gateway telemetry (OpenTelemetry GenAI conventions) and the usage ledger; no prompt or completion content is recorded.</div></div></div>
<div class="tabs"><span>Overview</span><span>Usage</span><span>Costs</span><span class="on">Inference</span><span>Activity</span><span>Traffic</span></div>
<div class="rbar"><div class="seg"><span class="on">24 h</span><span>7 d</span><span>Month to date</span><span>30 d</span><span>Custom</span></div><span class="sel">Team: all ▾</span><span class="sel">Route: all ▾</span><span class="sel">Group by: route ▾</span><span style="flex:1"></span><span class="btn">Download CSV</span><span class="btn">Schedule report</span></div>
<div class="grid g4 kpi">
<div class="card"><div class="cb"><div class="small muted">Model calls · 24 h</div><div class="big">412 K</div><div class="small muted">86% Bedrock · 14% routes</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Tokens per second (peak hour)</div><div class="big">61.4 K</div><div class="small muted">out 9.8 K/s · cached 21%</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Errors and refusals</div><div class="big">1.3%</div><div class="small muted">upstream 0.6% · throttled 0.4% · AFS refused 0.3%</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Gateway overhead p99</div><div class="big">11 ms</div><div class="small muted">objective 25 ms · 42 team gateways</div></div></div>
</div>
<div class="card"><div class="ch"><div><h2>Routes <span class="cnt">(10)</span></h2><div class="sub">Percentiles from the usage ledger. Effective $/MTok for capacity routes = allocated cost ÷ tokens.</div></div></div>
<table><tr><th>Route</th><th>Pricing</th><th class="num">Calls</th><th class="num">p50 latency</th><th class="num">p95 TTFT</th><th class="num">Out tok/s per call</th><th class="num">Error rate</th><th class="num">Est. usage</th><th class="num">Cost</th><th class="num">Effective $/MTok</th><th>Health</th></tr>
<tr><td class="rt">bedrock</td><td class="small">Per token</td><td class="num">354 K</td><td class="num">2.4 s</td><td class="num">1.1 s</td><td class="num">71</td><td class="num">0.9%</td><td class="num">0.0%</td><td class="num">$3,118</td><td class="num">5.92</td><td>{st('ok','Healthy')}</td></tr>
<tr><td class="rt">openai-prod</td><td class="small">Per token</td><td class="num">31.2 K</td><td class="num">3.0 s</td><td class="num">1.6 s</td><td class="num">64</td><td class="num">0.3%</td><td class="num">0.3%</td><td class="num">$402</td><td class="num">2.70</td><td>{st('ok','Healthy')}</td></tr>
<tr><td class="rt">ml-platform</td><td class="small">Transfer price</td><td class="num">18.9 K</td><td class="num">5.8 s</td><td class="num warn"><b>7.8 s</b></td><td class="num">22</td><td class="num">2.4%</td><td class="num">0.0%</td><td class="num">$96</td><td class="num">0.80</td><td>{st('warn','Degraded')}</td></tr>
<tr><td class="rt">openrouter</td><td class="small">Per token</td><td class="num">2.1 K</td><td class="num">4.1 s</td><td class="num">2.2 s</td><td class="num">48</td><td class="num">1.1%</td><td class="num">0.0%</td><td class="num">$31</td><td class="num">3.40</td><td>{st('ok','Healthy')}</td></tr>
<tr><td class="rt">nous-portal</td><td class="small">Per token</td><td class="num">1.4 K</td><td class="num">3.6 s</td><td class="num">1.9 s</td><td class="num">55</td><td class="num">0.6%</td><td class="num">0.0%</td><td class="num">$12 <span class="small muted">not reconciled</span></td><td class="num">1.10</td><td>{st('ok','Healthy')}</td></tr>
<tr><td class="rt">coder-vllm <span class="small muted">payments-factory</span></td><td class="small">Capacity</td><td class="num">5.4 K</td><td class="num">1.9 s</td><td class="num">0.4 s</td><td class="num">88</td><td class="num">0.1%</td><td class="num">0.0%</td><td class="num">$58 <span class="small muted">EKS</span></td><td class="num">0.61</td><td>{st('ok','Healthy')}</td></tr>
<tr><td class="rt">ollama-test <span class="small muted">mobile-platform</span></td><td class="small">Free</td><td class="num">212</td><td class="num muted">—</td><td class="num muted">—</td><td class="num muted">—</td><td class="num err">100%</td><td class="num">—</td><td class="num">$0</td><td class="num muted">—</td><td>{st('err','Unavailable')}</td></tr></table></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>ml-platform · time to first token</h2><span class="sel">Route: ml-platform ▾</span></div><div class="cb">{lat_chart()}</div></div>
<div class="card"><div class="ch"><div><h2>Errors by code · 24 h</h2><div class="sub">Upstream failures are separated from AFS refusals</div></div></div>
<table><tr><th>Code</th><th>Source</th><th class="num">Calls</th><th>Top route</th></tr>
<tr><td class="mono">429 Throttled</td><td class="small">Upstream</td><td class="num">1,640</td><td class="rt">ml-platform</td></tr>
<tr><td class="mono">502 UpstreamError</td><td class="small">Upstream</td><td class="num">2,210</td><td class="rt">ml-platform</td></tr>
<tr><td class="mono">402 BudgetExceeded</td><td class="small">AFS (cap)</td><td class="num">604</td><td class="rt">bedrock</td></tr>
<tr><td class="mono">403 route_not_enabled_for_agent</td><td class="small">AFS (access)</td><td class="num">318</td><td class="rt">openai-prod</td></tr>
<tr><td class="mono">400 unsupported_parameter</td><td class="small">AFS (request)</td><td class="num">41</td><td class="rt">bedrock</td></tr></table></div>
</div>
<div class="small muted">Per-agent figures are on each team's report. Traces for any call can be found by request id in the platform trace store.</div>
""")

gpage("60-admin-team-routes", "admin", admin_nav_gw("teams"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Teams</a> › <a>payments-factory</a> › Model endpoints</div>
<div class="hdr"><div><h1>payments-factory · Model endpoints <span class="info">Info</span></h1><div class="desc">The service endpoints this team opted in to, extra-terms selections, and whether it may declare its own endpoints.</div></div>
<div class="btns"><span class="btn">Edit</span></div></div>
<div class="grid g2">
<div class="card"><div class="ch"><div><h2>Service endpoints for this team <span class="cnt">(4)</span></h2><div class="sub">Teams opt in themselves. Only endpoints with extra terms need a service admin.</div></div><span class="btn sm">Select extra-terms endpoint</span></div>
<table><tr><th>Route</th><th>Opted in</th><th>By</th><th>Credential</th></tr>
<tr><td class="rt">bedrock</td><td>{st('ok','Always')}</td><td class="small muted">Built-in</td><td class="small muted">Team Bedrock role</td></tr>
<tr><td class="rt">openai-prod</td><td>{st('ok','Yes')}</td><td class="small">Marcus Chen (team-admin)</td><td>{st('ok','Set')}</td></tr>
<tr><td class="rt">ml-platform</td><td>{st('ok','Yes')}</td><td class="small">Marcus Chen (team-admin)</td><td class="small">Shared key</td></tr>
<tr><td class="rt">openrouter {mb('terms')}</td><td>{st('ok','Yes')}</td><td class="small">Priya Raman (service admin)</td><td>{st('ok','Set')}</td></tr>
<tr><td class="rt">eval-sandbox</td><td>{st('pend','No')}</td><td class="small muted">Off for the service</td><td class="small muted">—</td></tr></table></div>
<div>
<div class="card"><div class="ch"><h2>Team endpoints</h2></div><div class="cb">
<div class="field"><label>{tg(True)} Team may declare its own model endpoints</label><div class="hint">Team-admins can add endpoints (for example a vLLM server in the namespace) with an owner and a purpose. Off removes nothing that exists; it stops new ones.</div></div>
<div class="kv"><div class="k">Declared</div><div class="v"><span class="rt">coder-vllm</span> · {loc('ns')} · Capacity</div></div></div></div>
<div class="card"><div class="ch"><h2>Equivalent CLI</h2></div><div class="cb"><div class="code">afs teams put-team-model-endpoints --team-id team_01JD3Z… \\<br>&nbsp; --endpoint-ids mep_openai… mep_mlplat… mep_openrtr…</div></div></div>
</div></div>
""")

# ---------------------------------------------------------------------------------------------- Team-admin
def team_routes_page(ro):
    edit = ('<span class="btn dis">Remove from team</span><span class="btn dis">Add service endpoint</span>' if ro else '<span class="btn">Remove from team</span><span class="btn">Add service endpoint</span>')
    create = ('<span class="tip"><span class="btn p dis">Create endpoint</span><span class="tipbox">Needs team-admin</span></span>' if ro
              else '<span class="btn p">Create endpoint</span>')
    banner = ('<div class="alert"><span class="ic">ⓘ</span><div><b>You have read-only access to this team.</b> You can see routes, health and usage. Credentials show only whether they are set; changes need a team-admin (Marcus Chen).</div></div>' if ro else "")
    svc_sub = ('Endpoints switched on by service admins that this team opted in to. Team-admins add and remove them.' if ro else 'Endpoints switched on by service admins that this team opted in to. Add one to make it available to agents; endpoints with extra terms need a service admin.')
    cred_col = (lambda s: st("ok", "Set") if s else st("pend", "Not needed"))
    return f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Model endpoints</div>
<div class="hdr"><div><h1>Model endpoints <span class="info">Info</span></h1>
<div class="desc">Routes this team's agents can call through the team gateway <span class="mono">https://afs-gateway.afs-t-payments-factory.svc:8443</span>.</div></div>
<div class="btns"><span class="btn dd{' dis' if ro else ''}">Actions</span>{create}</div></div>
{banner}
<div class="grid g4 kpi">
<div class="card"><div class="cb"><div class="small muted">Team gateway</div><div class="big g" style="font-size:20px;margin:6px 0">{st('ok','Ready')}</div><div class="small muted">2 of 2 pods · v1.2.0 · overhead p99 9 ms</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Routes</div><div class="big">5</div><div class="small muted">4 from the service · 1 declared by the team</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Route spend, month to date</div><div class="big">$2,412</div><div class="small muted">of $31,880 total team spend · counts toward the $40,000 cap</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Calls, 24 h</div><div class="big">22.1 K</div><div class="small muted">error rate 0.4%</div></div></div>
</div>
<div class="card"><div class="ch"><div><h2>Service endpoints <span class="cnt">(4)</span></h2><div class="sub">{svc_sub}</div></div><div class="btns">{edit}</div></div>
<table><tr><th></th><th>Route</th><th>Provider</th><th>Location</th><th>Budget control</th><th>Agents using</th><th>Credential</th><th>Health</th><th class="num">Spend MTD</th></tr>
<tr><td><span class="radio"></span></td><td class="rt">bedrock</td><td class="small">Amazon Bedrock</td><td>{loc('aws')}</td><td>{mb('met')} {mb('cap')}</td><td class="small">12 of 12</td><td class="small muted">Team Bedrock role</td><td>{st('ok','Healthy')}</td><td class="num">$29,468</td></tr>
<tr class="sel"><td><span class="radio on"></span></td><td class="rt">openai-prod</td><td class="small">OpenAI</td><td>{loc('ext')}</td><td>{mb('met')} {mb('cap')}</td><td class="small">5 of 12</td><td>{cred_col(True)}</td><td>{st('ok','Healthy')}</td><td class="num">$2,180</td></tr>
<tr><td><span class="radio"></span></td><td class="rt">ml-platform</td><td class="small">Enterprise ML platform</td><td>{loc('corp')}</td><td>{mb('met')} {mb('cap')}</td><td class="small">3 of 12</td><td class="small">Service-managed</td><td>{st('warn','Degraded')}</td><td class="num">$174</td></tr>
<tr><td><span class="radio"></span></td><td class="rt">openrouter</td><td class="small">OpenRouter</td><td>{loc('ext')}</td><td>{mb('met')} {mb('cap')} {mb('terms')}</td><td class="small">1 of 12</td><td>{cred_col(True)}</td><td>{st('ok','Healthy')}</td><td class="num">$58</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>Team endpoints <span class="cnt">(1)</span></h2><div class="sub">Declared by this team (allowed by service admins). Owner and purpose are shown to service admins.</div></div></div>
<table><tr><th></th><th>Route</th><th>Address</th><th>Location</th><th>Pricing</th><th>Budget control</th><th>Agents using</th><th>Health</th><th>Owner</th></tr>
<tr><td><span class="radio"></span></td><td class="rt">coder-vllm</td><td class="mono small">http://vllm-coder:8000/v1</td><td>{loc('ns')}</td><td class="small">Capacity · EKS cost</td><td>{mb('met')}</td><td class="small">4 of 12</td><td>{st('ok','Healthy')}</td><td class="small">Marcus Chen</td></tr></table></div>
<div class="alert warn"><span class="ic">⚠</span><div class="small"><b>ml-platform is degraded.</b> p95 time to first token 7.8 s (objective 5 s) since 13:10. Calls still flow. Agents with another route may switch per call; AFS does not move traffic for them.</div></div>
"""


gpage("61-ta-model-endpoints", "ta", team_nav_gw("endpoints", "ta"), team_routes_page(False))

gpage("62-ta-create-team-endpoint", "ta", team_nav_gw("endpoints", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › <a>Model endpoints</a> › Create endpoint</div>
<div class="split"><div style="flex:1;max-width:860px">
<div class="hdr"><div><h1>Create team endpoint</h1><div class="desc">Adds an OpenAI-compatible model service only this team can use. Every call is metered by the team gateway.</div></div></div>
<div class="card"><div class="ch"><h2>Endpoint and route</h2></div><div class="cb">
<div class="grid g2"><div class="field"><label>Route name</label><div class="hint">Lowercase letters, digits and hyphens. Agents see it in URLs and in <span class="mono">AFS_LLM_CODER_VLLM_BASE_URL</span>. Cannot be changed.</div><div class="input">coder-vllm</div></div>
<div class="field"><label>Display name</label><div class="hint">Shown on screens and reports</div><div class="input">Qwen coder on vLLM (team GPU pool)</div></div></div>
<div class="grid g2"><div class="field"><label>Owner</label><div class="input">Marcus Chen ▾</div></div>
<div class="field"><label>Purpose</label><div class="input">Cheap code completion for the patch agents</div></div></div>
</div></div>
<div class="card"><div class="ch"><h2>Connection</h2></div><div class="cb">
<div class="field"><label>Location</label>
<div class="grid g3"><div class="tile on"><b><span class="radio on"></span> In this namespace</b><span>A Service in afs-t-payments-factory. Traffic never leaves the namespace.</span></div>
<div class="tile"><b><span class="radio"></span> Corporate network</b><span>A host on the corporate network, over HTTPS.</span></div>
<div class="tile"><b><span class="radio"></span> External</b><span>An internet provider, over HTTPS.</span></div></div></div>
<div class="grid g2"><div class="field"><label>Service and port</label><div class="input">vllm-coder : 8000 ▾</div></div>
<div class="field"><label>Base path</label><div class="input">/v1</div></div></div>
<div class="grid g2"><div class="field"><label>Protocol paths</label><div><span class="cb2 on"></span> Chat completions &nbsp; <span class="cb2"></span> Responses &nbsp; <span class="cb2 on"></span> Embeddings</div></div>
<div class="field"><label>Authentication</label><div class="input">None (network policy only) ▾</div></div></div>
<div class="field"><label>{tg(True)} Test connection before saving</label><div class="hint">The team gateway calls <span class="mono">GET /v1/models</span> once. {st('ok','Reachable · 1 model: Qwen/Qwen3-Coder-30B')}</div></div>
</div></div>
<div class="card"><div class="ch"><h2>Models and cost</h2></div><div class="cb">
<div class="grid g3">
<div class="tile"><b><span class="radio"></span> Per token</b><span>You set prices; calls count against the team budget and its hard cap.</span></div>
<div class="tile on"><b><span class="radio on"></span> Capacity</b><span>Cost is the GPU pods in this namespace (EKS split cost, daily). Tokens are metered.</span></div>
<div class="tile"><b><span class="radio"></span> Free</b><span>No cost recorded. Tokens are metered.</span></div></div>
<table style="margin-top:12px"><tr><th>Model name</th><th class="num">Max output tok</th><th class="num">Context tok</th></tr>
<tr><td class="mono">Qwen/Qwen3-Coder-30B</td><td class="num">16,384</td><td class="num">131,072</td></tr></table>
<div class="small muted" style="margin-top:12px">Capacity routes are metered and reported per agent, with no hard limit. GPU pods in this namespace appear in the team's EKS cost.</div></div></div>
<div style="display:flex;justify-content:flex-end;gap:8px"><span class="btn" style="border:0">Cancel</span><span class="btn p">Create endpoint</span></div>
</div>
<div style="width:360px"><div class="card"><div class="ch"><h2>Equivalent CLI</h2></div><div class="cb">
<div class="code">afs model-endpoints create-model-endpoint \\<br>&nbsp; --team-id team_01JD3Z… \\<br>&nbsp; --slug coder-vllm \\<br>&nbsp; --location in_namespace \\<br>&nbsp; --base-url http://vllm-coder:8000/v1 \\<br>&nbsp; --protocol openai_chat openai_embeddings \\<br>&nbsp; --auth-kind none \\<br>&nbsp; --pricing-mode capacity \\<br>&nbsp; --owner marcus.chen \\<br>&nbsp; --purpose "Cheap code completion"</div>
</div></div>
<div class="card"><div class="ch"><h2>What agents get</h2></div><div class="cb small">Agents with this route receive <span class="mono">AFS_LLM_CODER_VLLM_BASE_URL</span> and an entry in <span class="mono">/etc/afs/llm-routes.json</span> on their next restart. They never call <span class="mono">vllm-coder</span> directly: network policy lets only the team gateway reach it.</div></div></div>
</div>
""")

ENV = """<b>AFS_GATEWAY_URL</b>=https://afs-gateway.afs-t-payments-factory.svc:8443<br>
<b>AFS_LLM_ROUTES</b>=openai-prod,bedrock,coder-vllm<br>
<b>AFS_LLM_DEFAULT_ROUTE</b>=openai-prod &nbsp; <b>AFS_LLM_DEFAULT_MODEL</b>=gpt-4.1<br>
<b>AFS_LLM_OPENAI_PROD_BASE_URL</b>=${AFS_GATEWAY_URL}/r/openai-prod/v1<br>
<b>AFS_LLM_CODER_VLLM_BASE_URL</b>=${AFS_GATEWAY_URL}/r/coder-vllm/v1<br>
<b>AFS_LLM_BEDROCK_BASE_URL</b>=${AFS_GATEWAY_URL}/r/bedrock/v1 <span style="color:#8c959f"># OpenAI protocol → Converse</span><br>
<b>OPENAI_BASE_URL</b>=${AFS_LLM_OPENAI_PROD_BASE_URL} &nbsp; <b>OPENAI_API_KEY</b>=afs-gateway <span style="color:#8c959f"># placeholder</span><br>
<b>AWS_ENDPOINT_URL_BEDROCK_RUNTIME</b>, <b>ANTHROPIC_BASE_URL</b> <span style="color:#8c959f"># unchanged, now the team gateway</span><br>
<span style="color:#8c959f"># file: /etc/afs/llm-routes.json (routes, models, limits, metered/capped)</span>"""


def agent_models_page(ro):
    dis = " dis" if ro else ""
    banner = RO_BANNER.replace("You can open the collaboration tool to watch agent work; changes", "Changes") if ro else ""
    return f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › <a>Agents</a> › security-patcher</div>
<div class="hdr"><div><h1>security-patcher {st('ok','Ready')}</h1><div class="desc">Team agent · hermes-dev (v2.4) · 1 pod</div></div>
<div class="btns"><span class="btn dd{dis}">Actions</span><span class="btn p{dis}">Edit</span></div></div>
{banner}
<div class="tabs"><span>Details</span><span class="on">Models & routes</span><span>Secrets</span><span>Configuration</span><span>AWS access</span><span>External systems</span><span>Report</span></div>
<div class="split"><div style="flex:1">
<div class="card"><div class="ch"><div><h2>Bedrock models</h2><div class="sub">Unchanged from 1.1.0</div></div></div><div class="cb">
<span class="chip def">claude-sonnet <b>default</b></span><span class="chip">claude-haiku</span></div></div>
<div class="card"><div class="ch"><div><h2>Routes</h2><div class="sub">From the routes this team may use (5). The agent may call only these, through the team gateway.</div></div></div><div class="cb">
<div style="margin-bottom:8px"><span class="radio"></span> All team routes &nbsp; <span class="radio on"></span> Selected routes</div>
<table><tr><th>Route</th><th>Selected</th><th>Models on route</th><th>Budget control</th><th>Calls (7 d)</th><th class="num">Cost (7 d)</th></tr>
<tr><td class="rt">bedrock</td><td><span class="cb2 on{dis}"></span></td><td class="small">2 (above), also by OpenAI protocol</td><td>{mb('met')} {mb('cap')}</td><td class="num">3,412</td><td class="num">$212.40</td></tr>
<tr><td class="rt">openai-prod</td><td><span class="cb2 on{dis}"></span></td><td class="small">gpt-4.1, gpt-4.1-mini, text-embedding-3-large</td><td>{mb('met')} {mb('cap')}</td><td class="num">1,906</td><td class="num">$48.10</td></tr>
<tr><td class="rt">coder-vllm</td><td><span class="cb2 on{dis}"></span></td><td class="small">Qwen/Qwen3-Coder-30B</td><td>{mb('met')}</td><td class="num">4,880</td><td class="num">$9.20 <span class="small muted">alloc.</span></td></tr>
<tr><td class="rt">ml-platform</td><td><span class="cb2{dis}"></span></td><td class="small muted">not selected</td><td>{mb('met')} {mb('cap')}</td><td class="num muted">—</td><td class="num muted">—</td></tr>
<tr><td class="rt">openrouter</td><td><span class="cb2{dis}"></span></td><td class="small muted">not selected</td><td>{mb('met')} {mb('cap')}</td><td class="num muted">—</td><td class="num muted">—</td></tr></table>
<div class="grid g2" style="margin-top:12px"><div class="field"><label>Default route</label><div class="input{' ro' if ro else ''}" style="width:260px">openai-prod ▾</div></div>
<div class="field"><label>Default model on that route</label><div class="input{' ro' if ro else ''}" style="width:260px">gpt-4.1 ▾</div></div></div>
</div></div></div>
<div style="width:520px"><div class="card"><div class="ch"><div><h2>What the agent receives</h2><div class="sub">Environment and files on the next restart. No upstream credential ever reaches the pod.</div></div></div><div class="cb"><div class="envbox">{ENV}</div>
<div class="small muted" style="margin-top:8px">Changing this agent's routes restarts its pod. Changes at team or service level apply at the gateway within 60 s and in the environment on the next restart.</div></div></div>
{"" if ro else '<div class="card"><div class="ch"><h2>Equivalent CLI</h2></div><div class="cb"><div class="code">afs agents update-agent-models --team-id team_01JD3Z… \\<br>&nbsp; --agent-id agt_01JE… --if-match 14 \\<br>&nbsp; --route-access selected \\<br>&nbsp; --routes bedrock openai-prod coder-vllm \\<br>&nbsp; --default-route openai-prod --default-route-model gpt-4.1</div></div></div>'}
</div></div>
"""


gpage("63-ta-agent-models-routes", "ta", team_nav_gw("agents", "ta"), agent_models_page(False))


def team_inference_body():
    return f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › <a>Reports</a> › Inference</div>
<div class="hdr"><div><h1>Inference <span class="info">Info</span></h1><div class="desc">This team's model calls through its gateway: Bedrock and routes. Per-agent figures come from the usage ledger.</div></div></div>
<div class="tabs"><span>Overview</span><span>Usage</span><span>Costs</span><span class="on">Inference</span><span>Activity</span><span>Traffic</span></div>
<div class="rbar"><div class="seg"><span>24 h</span><span class="on">7 d</span><span>Month to date</span><span>30 d</span><span>Custom</span></div><span class="sel">Route: all ▾</span><span class="sel">Agent: all ▾</span><span class="sel">Group by: agent ▾</span><span style="flex:1"></span><span class="btn">Download CSV</span></div>
<div class="grid g4 kpi">
<div class="card"><div class="cb"><div class="small muted">Model calls · 7 d</div><div class="big">148 K</div><div class="small muted">bedrock 71% · coder-vllm 18% · openai-prod 9%</div></div></div>
<div class="card"><div class="cb"><div class="small muted">p95 time to first token</div><div class="big">1.3 s</div><div class="small muted">best: coder-vllm 0.4 s</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Errors and refusals</div><div class="big">0.6%</div><div class="small muted">0 over budget · 12 unsupported parameters</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Bedrock via OpenAI protocol</div><div class="big">22%</div><div class="small muted">of Bedrock calls · same budget, tags and profiles</div></div></div>
</div>
<div class="card"><div class="ch"><div><h2>Agents <span class="cnt">(12)</span></h2><div class="sub">Calls and timings by agent across all routes</div></div></div>
<table><tr><th>Agent</th><th>Main route</th><th class="num">Calls</th><th class="num">Tokens in / out</th><th class="num">p50 latency</th><th class="num">p95 TTFT</th><th class="num">Errors</th><th class="num">Cost</th></tr>
<tr><td><a>orchestrator</a> <span class="badge b-orch">Orchestration</span></td><td class="rt">bedrock</td><td class="num">38.2 K</td><td class="num">812 M / 64 M</td><td class="num">2.1 s</td><td class="num">1.2 s</td><td class="num">0.3%</td><td class="num">$1,904</td></tr>
<tr><td><a>reviewer-bot</a></td><td class="rt">bedrock</td><td class="num">29.0 K</td><td class="num">1.1 B / 88 M</td><td class="num">3.0 s</td><td class="num">1.6 s</td><td class="num">0.5%</td><td class="num">$3,512</td></tr>
<tr><td><a>security-patcher</a></td><td class="rt">coder-vllm</td><td class="num">10.2 K</td><td class="num">96 M / 21 M</td><td class="num">1.8 s</td><td class="num">0.4 s</td><td class="num">1.0%</td><td class="num">$270</td></tr>
<tr><td><a>doc-writer</a></td><td class="rt">openai-prod</td><td class="num">6.8 K</td><td class="num">41 M / 9 M</td><td class="num">3.2 s</td><td class="num">1.7 s</td><td class="num">0.2%</td><td class="num">$188</td></tr>
<tr><td><a>test-gardener</a></td><td class="rt">coder-vllm</td><td class="num">14.9 K</td><td class="num">120 M / 30 M</td><td class="num">1.7 s</td><td class="num">0.4 s</td><td class="num">0.9%</td><td class="num">$41 <span class="small muted">alloc.</span></td></tr></table></div>
<div class="grid g2">
<div class="card"><div class="ch"><div><h2>Cost by route · month to date</h2><div class="sub">Capacity routes show allocated EKS cost and the effective price</div></div></div>
<table><tr><th>Route</th><th>Pricing</th><th class="num">Tokens</th><th class="num">Cost</th><th class="num">Effective $/MTok</th></tr>
<tr><td class="rt">bedrock</td><td class="small">Per token</td><td class="num">5.0 B</td><td class="num">$29,468</td><td class="num">5.89</td></tr>
<tr><td class="rt">openai-prod</td><td class="small">Per token</td><td class="num">808 M</td><td class="num">$2,180</td><td class="num">2.70</td></tr>
<tr><td class="rt">ml-platform</td><td class="small">Transfer price</td><td class="num">218 M</td><td class="num">$174</td><td class="num">0.80</td></tr>
<tr><td class="rt">coder-vllm</td><td class="small">Capacity (EKS)</td><td class="num">31.0 M</td><td class="num">$19 <span class="small muted">+ GPU pods $1,212</span></td><td class="num">39.7</td></tr></table>
<div class="cb small muted" style="padding-top:8px">coder-vllm's GPU pods run all month; at 31 M tokens its effective price is above openai-prod's. More traffic lowers it.</div></div>
<div class="card"><div class="ch"><h2>openai-prod · time to first token</h2></div><div class="cb">{lat_chart([1.2,1.1,1.0,1.1,1.3,1.4,1.6,1.8,1.7,1.5,1.4,1.6,1.7,1.5,1.4,1.3,1.2,1.2,1.1,1.0,1.0,1.1,1.2,1.1], 5.0, 13)}</div></div>
</div>
"""


gpage("64-ta-team-inference-report", "ta", team_nav_gw("reports", "ta"), team_inference_body())

gpage("65-ta-budget-routes", "ta", team_nav_gw("budget", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Budget & usage</div>
<div class="hdr"><div><h1>Budget & usage <span class="info">Info</span></h1><div class="desc">Monthly budget $40,000 · hard cap (block at 100%) · thresholds 50 / 80 / 100%</div></div>
<div class="btns"><span class="btn">Edit budget</span></div></div>
<div class="grid g3 kpi">
<div class="card"><div class="cb"><div class="small muted">Spent, month to date</div><div class="big">$31,880</div>{bar(80,'w')}<div class="small muted" style="margin-top:6px">80% · $8,120 left · forecast $41,300 <span class="warn">(over cap 2 days before month end)</span></div></div></div>
<div class="card"><div class="cb"><div class="small muted">Reserved in flight</div><div class="big">$14.20</div><div class="small muted">9 calls across bedrock and openai-prod</div></div></div>
<div class="card"><div class="cb"><div class="small muted">Not in the cap</div><div class="big g">31.0 M tok</div><div class="small muted">coder-vllm (capacity) · reported only, no hard limit</div></div></div>
</div>
<div class="card"><div class="ch"><div><h2>What counts against the cap</h2><div class="sub">Every per-token route is reserved before the call and settled to actual usage, like Bedrock</div></div></div>
<table><tr><th>Source</th><th>Budget control</th><th class="num">Spend MTD</th><th>Share of spend</th><th class="num">Estimated usage</th></tr>
<tr><td class="rt">bedrock</td><td>{mb('met')} {mb('cap')}</td><td class="num">$29,468</td><td><div class="hbar">{bar(92)}<span class="small">92%</span></div></td><td class="num">0.0%</td></tr>
<tr><td class="rt">openai-prod</td><td>{mb('met')} {mb('cap')}</td><td class="num">$2,180</td><td><div class="hbar">{bar(7)}<span class="small">7%</span></div></td><td class="num">0.3%</td></tr>
<tr><td class="rt">ml-platform</td><td>{mb('met')} {mb('cap')}</td><td class="num">$174</td><td><div class="hbar">{bar(1)}<span class="small">&lt;1%</span></div></td><td class="num">0.0%</td></tr>
<tr><td class="rt">openrouter</td><td>{mb('met')} {mb('cap')}</td><td class="num">$58</td><td><div class="hbar">{bar(0)}<span class="small">&lt;1%</span></div></td><td class="num">0.0%</td></tr>
<tr><td class="rt">coder-vllm</td><td>{mb('met')} <span class="small muted">Reported only</span></td><td class="num muted">— (capacity)</td><td class="small muted">Not in the cap · cost in EKS compute</td><td class="num">0.0%</td></tr>
<tr><td class="muted">EKS compute, incl. team gateway and GPU pods</td><td class="small muted">Reported, not capped</td><td class="num">$2,904</td><td class="small muted">CUR, daily</td><td class="num muted">—</td></tr></table></div>
<div class="alert"><span class="ic">ⓘ</span><div class="small">At 100% the team gateway answers <span class="mono">402 BudgetExceeded</span> on every per-token route and Bedrock alike; capacity and free routes keep working (they have no hard limit in 1.2.0). Direct calls to providers outside a route are not possible for this team (no LLM external system is on).</div></div>
""")

# ---------------------------------------------------------------------------------------------- Team viewer
gpage("66-tv-model-endpoints", "tv", team_nav_gw("endpoints", "tv"), team_routes_page(True))
gpage("67-tv-agent-models-routes", "tv", team_nav_gw("agents", "tv"), agent_models_page(True))


# ---------------------------------------------------------------------------------------------- Provider policy (J, 2026-11-24)
PROV = [
    # provider, hosts, routes, teams, direct systems, on, note
    ("OpenAI", "api.openai.com", "openai-prod", "18", "1", True, ""),
    ("OpenRouter", "openrouter.ai", "openrouter", "3", "1 (override for 1 team)", True, ""),
    ("Nous Portal", "inference-api.nousresearch.com", "nous-portal", "4", "1", True, ""),
    ("Azure OpenAI", "*.openai.azure.com", "azure-oai-east (team)", "1", "0", True, ""),
    ("OpenCode Go", "opencode.ai", "opencode-go", "0", "0", False, "Waiting for OpenCode to confirm gateway use (MEG-OQ-22)"),
    ("Other external hosts", "any external host not listed", "none today", "0", "0", True, ""),
]


def prov_rows():
    out = []
    for n, h, r, t, d, on, note in PROV:
        state = st("ok", "On") if on else st("err", "Off")
        out.append(f'<tr><td><b>{n}</b>{"<div class=\"small muted\">" + note + "</div>" if note else ""}</td><td class="mono small">{h}</td><td class="rt">{r}</td>'
                   f'<td class="num">{t}</td><td class="small">{d}</td><td>{state}</td><td>{tg(on)}</td></tr>')
    return "".join(out)


prov_modal = f"""<div class="modalwrap"><div class="modal" style="width:700px"><div class="mh">Turn off all external inference?<span class="muted">✕</span></div><div class="mb">
<div class="small" style="margin-bottom:10px">Every endpoint with location <b>External</b> stops for every team. Nothing is deleted: opt-ins, selections, credentials and prices come back when you turn it on again.</div>
<table><tr><th>What changes</th><th class="num">Count</th></tr>
<tr><td>Routes refused within 60 s (<span class="mono">external_provider_blocked</span>)</td><td class="num">5</td></tr>
<tr><td>Teams that lose at least one route</td><td class="num">21</td></tr>
<tr><td>Team-declared external endpoints</td><td class="num">1</td></tr>
<tr><td>Direct LLM external systems closed, overrides included</td><td class="num">4</td></tr>
<tr><td>Agents whose default route falls back to <span class="rt">bedrock</span></td><td class="num">37</td></tr></table>
<div class="small muted" style="margin-top:10px">Gateway egress to these hosts is removed. Agents drop the routes from their files and variables on their next restart. Not affected: <span class="rt">bedrock</span>, corporate and in-namespace endpoints.</div>
<div class="field" style="margin-top:12px"><label>Reason (recorded in the audit log and shown to teams)</label><div class="input">Enterprise policy: no external inference providers</div></div>
<div class="field"><label>Type <b>turn off</b> to confirm</label><div class="input" style="width:220px">turn off</div></div>
</div><div class="mf"><span class="btn" style="border:0">Cancel</span><span class="btn p" style="background:#d91515;border-color:#d91515">Turn off external inference</span></div></div></div>"""

PROV_BODY = f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Model endpoints</a> › Provider policy</div>
<div class="hdr"><div><h1>Provider policy <span class="info">Info</span></h1>
<div class="desc">Turn external inference providers off for the whole service, one at a time or all at once. Off refuses calls on their routes, removes the routes from agents, removes gateway egress to their hosts and closes direct LLM access.</div></div></div>
<div class="tabs"><span>Endpoints</span><span>Price proposals</span><span class="on">Provider policy</span></div>
<div class="card"><div class="ch"><div><h2>External inference</h2><div class="sub">Covers every endpoint with location External, service and team, and every external system of category LLM.</div></div><span class="btn">Turn off all external inference</span></div><div class="cb">
<div class="field"><label>{tg(True)} External inference providers are allowed</label><div class="hint">When off, team-admins cannot create External endpoints, and each provider below is off whatever its own switch says.</div></div></div></div>
<div class="card"><div class="ch"><div><h2>External providers <span class="cnt">(6)</span></h2><div class="sub">A provider matches its routes by provider and by host, so a team cannot add a blocked provider back under a new route.</div></div><div class="btns"><span class="btn">Add provider</span></div></div>
<table><tr><th>Provider</th><th>Hosts</th><th>Routes</th><th class="num">Teams</th><th>Direct LLM systems</th><th>Status</th><th>Allowed</th></tr>
{prov_rows()}</table></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>Not affected</h2></div><div class="cb">
<table><tr><th>Route or kind</th><th>Why</th><th>How to stop it</th></tr>
<tr><td class="rt">bedrock</td><td class="small">AWS, through VPC endpoints</td><td class="small">Model catalog</td></tr>
<tr><td>{loc('corp')}</td><td class="small">Inside the enterprise network</td><td class="small">The endpoint's own switch</td></tr>
<tr><td>{loc('ns')}</td><td class="small">Runs in the team's namespace</td><td class="small">The team's endpoint</td></tr></table></div></div>
<div class="card"><div class="ch"><h2>Recent changes</h2><a>Audit log</a></div>
<table><tr><th>When</th><th>Change</th><th>By</th></tr>
<tr><td class="small">2026-11-24 14:02</td><td class="small">OpenCode Go <b>off</b>: waiting for the provider to confirm gateway use</td><td class="small">Priya Raman</td></tr>
<tr><td class="small">2026-11-20 09:15</td><td class="small">Nous Portal <b>on</b></td><td class="small">Priya Raman</td></tr></table></div>
</div>
<div class="card"><div class="ch"><h2>Equivalent CLI</h2></div><div class="cb"><div class="code">afs model-endpoints put-inference-provider-policy --external-providers off \\<br>&nbsp; --reason "Enterprise policy: no external inference providers"</div>
<div class="code" style="margin-top:8px">afs model-endpoints update-inference-provider --provider opencode --no-enabled \\<br>&nbsp; --reason "Waiting for the provider to confirm gateway use"</div></div></div>
"""

gpage("68-admin-provider-policy", "admin", admin_nav_gw("endpoints"), PROV_BODY)
gpage("68a-admin-provider-policy-confirm", "admin", admin_nav_gw("endpoints"), PROV_BODY, modal=prov_modal)

