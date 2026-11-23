# Orchestration agent redesign (team-orchestration-agent-PRD.md), screens 32 to 43.
# Executed by gen.py after the base screens, so it shares CSS, page(), navs and helpers.

CSS_ORCH = """
.orch{border:2px solid #7300e5;background:#fff;border-radius:16px;margin-bottom:20px;overflow:hidden;box-shadow:0 1px 1px rgba(0,7,22,.12)}
.orch>.oh{background:#f6f0ff;padding:12px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #e3d2ff}
.orch>.oh h2{font-size:18px;margin:0;display:flex;align-items:center;gap:10px}
.orch>.oh .sub{color:var(--muted);font-size:13px;margin-top:2px}
.orch>.ob{padding:14px 20px 16px}
.b-orch{color:#fff;background:#7300e5;border-color:#7300e5}
.b-orch-o{color:#7300e5;border-color:#7300e5}
.oic{width:26px;height:26px;border-radius:7px;background:#7300e5;color:#fff;display:inline-grid;place-items:center;font-size:13px;font-weight:700}
.tool{display:inline-flex;align-items:center;gap:6px;font-weight:700}
.tool i{width:18px;height:18px;border-radius:4px;display:inline-grid;place-items:center;font-size:10px;font-style:normal;color:#fff}
.tool i.pc{background:#0b7a75}.tool i.bz{background:#d97706}
.expo{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;vertical-align:middle}
.expo span{padding:4px 12px;font-size:13px;border-right:1px solid var(--line);color:var(--text)}
.expo span:last-child{border-right:0}
.expo span.on{background:#7300e5;color:#fff;font-weight:700}
.expo span.x{color:#c6c6cd;background:#fafafa}
.expo.dis span.on{background:#b9a2db}
.surf{border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.surf h3{margin:0 0 4px;font-size:15px;display:flex;justify-content:space-between;align-items:center}
.surf .url{font-family:"DejaVu Sans Mono",monospace;font-size:12.5px;margin:6px 0}
.lvl{display:inline-block;border-radius:10px;padding:1px 9px;font-size:12px;font-weight:700}
.lvl.pub{background:#fff1e6;color:#b45309}.lvl.prv{background:#e8f3ff;color:#004a9e}.lvl.off{background:#f3f3f7;color:var(--muted)}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:#f3f3f7;border-radius:14px;padding:2px 10px;font-size:12.5px;margin:0 6px 6px 0;font-family:"DejaVu Sans Mono",monospace}
.chip b{font-family:"Open Sans",sans-serif;color:var(--muted);font-weight:400}
.chip.def{border-color:var(--blue);background:#f0f7ff}
.mset{border:1px solid #8c959f;border-radius:8px;padding:8px 10px 2px;background:#fff}
.segnote{border-left:3px solid #7300e5;background:#faf7ff;padding:8px 12px;border-radius:0 8px 8px 0;font-size:13px;margin-bottom:14px}
"""

ROLE_PILL["tvc"] = '<span class="pill tv">Team viewer · payments-factory</span>'
USER["tvc"] = "Dana Ortiz"


def opage(name, role, side, body, modal=""):
    page(name, role, side, f"<style>{CSS_ORCH}</style>" + body, modal)


def tool(kind):
    return ('<span class="tool"><i class="pc">P</i>Paperclip AI</span>' if kind == "pc"
            else '<span class="tool"><i class="bz">B</i>Buzz</span>')


def lvl(kind):
    return {"pub": '<span class="lvl pub">Public</span>', "prv": '<span class="lvl prv">Private</span>',
            "off": '<span class="lvl off">Off</span>', "na": '<span class="lvl off">Off · N/A</span>'}[kind]


def expo(on, allowed=("off", "prv", "pub"), dis=False):
    names = (("off", "Off"), ("prv", "Private"), ("pub", "Public"))
    parts = []
    for key, label in names:
        cls = "on" if key == on else ("x" if key not in allowed else "")
        parts.append(f'<span class="{cls}">{label}</span>')
    return f'<span class="expo{" dis" if dis else ""}">{"".join(parts)}</span>'


def models_field(mode="sel", chips=(("claude-sonnet", True), ("claude-haiku", False)), ro=False, hint="From the models this team may use (4). The agent may call only these; the default is the one its runtime uses unless told otherwise."):
    allsel = mode == "all"
    radios = (f'<span class="radio{" on" if allsel else ""}"></span> All team models &nbsp; '
              f'<span class="radio{"" if allsel else " on"}"></span> Selected models')
    if allsel:
        body = '<div class="small muted">Every model the team may use, now and later (4 today).</div>'
    else:
        body = "".join(f'<span class="chip{" def" if d else ""}">{m}{" <b>default</b>" if d else ""} ✕</span>' for m, d in chips) + '<span class="chip" style="background:#fff;color:var(--link)">+ Add model</span>'
    return f"""<div class="field"><label>Models</label><div class="hint">{hint}</div>
<div style="margin-bottom:6px">{radios}</div><div class="mset">{body}</div></div>
<div class="field"><label>Default model</label><div class="input" style="width:280px">claude-sonnet ▾</div></div>"""


RO_BANNER = ('<div class="alert"><span class="ic">ⓘ</span><div><b>You have read-only access to this team.</b> '
             'You can open the collaboration tool to watch agent work; changes need a team-admin (Marcus Chen).</div></div>')


# ---------------------------------------------------------------------------------------------
# Orchestration card used on the Agents page and the overview (visually separate from agents)
# ---------------------------------------------------------------------------------------------
def orch_card(ro, compact=False):
    dis = " dis" if ro else ""
    open_ui = '<span class="btn p">Open Paperclip AI ↗</span>'
    acts = f'<span class="btn sm{dis}">Restart</span><span class="btn sm{dis}">Pause</span><span class="btn sm">Manage orchestration</span>'
    extra = "" if compact else f"""
<div class="grid g4" style="margin-top:6px">
<div class="kv"><div class="k">Model</div><div class="v mono">claude-sonnet</div></div>
<div class="kv"><div class="k">Pod</div><div class="v mono small">orchestrator-0</div></div>
<div class="kv"><div class="k">Connected agents</div><div class="v">6 of 7 <a class="small">View</a></div></div>
<div class="kv"><div class="k">Cost, Nov MTD</div><div class="v">$2,140</div></div></div>"""
    return f"""
<div class="orch"><div class="oh"><div><h2><span class="oic">◆</span> orchestrator <span class="badge b-orch">Orchestration agent</span> {st('ok','Ready')}</h2>
<div class="sub">Created with the team. Coordinates the team's agents and people through the collaboration tool. The only part of the team reachable from outside the cluster.</div></div>
<div class="btns">{acts}{open_ui}</div></div>
<div class="ob"><div class="grid g4">
<div class="kv"><div class="k">Collaboration tool</div><div class="v">{tool('pc')}</div></div>
<div class="kv"><div class="k">Web UI</div><div class="v">{lvl('prv')} <span class="mono small">payments-factory.collab.corp.example</span></div></div>
<div class="kv"><div class="k">Web API</div><div class="v">{lvl('off')}</div></div>
<div class="kv"><div class="k">Service limit</div><div class="v">Up to {lvl('pub')}</div></div></div>{extra}
</div></div>"""


WORKERS = [a for a in AGENTS]


def worker_rows(selected=None, selectable=True):
    out = []
    links = {"incident-scribe": ("pend", "Not connected"), "release-notes-bot": ("warn", "Pending")}
    for name, state, sk, rep, model, tmpl, secs, cost in WORKERS:
        cls = "sel" if name == selected else ""
        box = f'<span class="cb2 {"on" if cls else ""}"></span>' if selectable else ""
        lk = links.get(name, ("ok", "Connected"))
        out.append(f'<tr class="{cls}"><td>{box}</td><td><a>{name}</a></td><td>{st(sk, state)}</td>'
                   f'<td class="mono small">{name + "-0" if state != "Paused" else "— (paused)"}</td><td class="mono">{model}</td><td>{tmpl}</td>'
                   f'<td>{st(*lk)}</td><td>{secs}</td><td>{cost}</td></tr>')
    return "".join(out)


def agents_page(ro):
    dis = " dis" if ro else ""
    tip = '<span class="tip"><span class="tipbox">Requires team-admin</span></span>' if ro else ""
    return f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Agents</div>
{RO_BANNER if ro else ""}
<div class="hdr"><div><h1>Agents <span class="info">Info</span></h1>
<div class="desc">Namespace afs-t-payments-factory. Model calls go through the metering gateway.</div></div>
<div class="btns"><span class="btn">⟳</span><span class="btn p{dis}">Create agent</span>{tip}</div></div>
{orch_card(ro)}
<div class="card"><div class="ch"><div><h2>Team agents <span class="cnt">(7)</span></h2>
<div class="sub">Workers you create. They reach the orchestration agent inside the namespace only and are never reachable from outside.</div></div>
<div class="btns"><span class="btn">View details</span><span class="btn dd{dis}">Actions</span></div></div>
<div class="tools"><div class="filter">🔍 Find agents</div><span class="sel">Any state ▾</span><span class="sel">Any collaboration link ▾</span><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Name</th><th>Status</th><th>Pod</th><th>Model</th><th>Template</th><th>Collaboration</th><th>Secrets</th><th>Cost, Nov MTD</th></tr>
{worker_rows(None if ro else "reviewer-bot", not ro)}</table></div>
"""


# ---------------------------------------------------------------------------------------------
# Orchestration page: header + tabs. Collaboration tab (segregated), Agent configuration tab (shared)
# ---------------------------------------------------------------------------------------------
def orch_header(ro, tab, t="pc"):
    dis = " dis" if ro else ""
    name = "Paperclip AI" if t == "pc" else "Buzz"
    open_btn = (f'<span class="btn p">Open {name} ↗</span>' if t == "pc"
                else '<span class="btn p dis">Open Buzz ↗</span>')
    tip = ""
    if t == "bz":
        tip = '<span class="tip"><span class="tipbox">N/A for Buzz: no web UI or REST API outside the cluster</span></span>'
    elif ro:
        tip = ""
    tabs = "".join(f'<span class="{"on" if k == tab else ""}">{v}</span>' for k, v in
                   (("collab", "Collaboration"), ("config", "Agent configuration"), ("usage", "Usage"), ("logs", "Logs"), ("rev", "Revisions")))
    return f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Orchestration</div>
{RO_BANNER if ro else ""}
<div class="hdr"><div><h1><span class="oic">◆</span> Orchestration <span class="badge b-orch">orchestrator</span> <span class="info">Info</span></h1>
<div class="desc">Every team has one orchestration agent, created with the team and deleted with it. It runs the team's collaboration tool.</div></div>
<div class="btns"><span class="btn dd{dis}">Actions</span>{open_btn}{tip}</div></div>
<div class="tabs">{tabs}</div>"""


def surf(title, what, url, cur, allowed, ro, note=""):
    return f"""<div class="surf"><h3><span>{title}</span>{expo(cur, allowed, ro)}</h3>
<div class="small muted">{what}</div><div class="url">{url}</div>{note}</div>"""


def collab_tab(ro, t="pc"):
    dis = " dis" if ro else ""
    if t == "pc":
        tool_desc = "Board, chat and agent groupings. Agents pull work from it and report progress."
        ui = surf("Web UI", "Paperclip AI in a browser. Viewers read; collaborators and team-admins write.",
                  "https://payments-factory.collab.corp.example", "prv", ("off", "prv", "pub"), ro,
                  f'<div class="small">{st("ok","Reachable")} · corporate network only · SSO: Okta</div>')
        api = surf("Web API", "Paperclip AI's REST API for pipelines. AFS token in X-Afs-Authorization; Paperclip key in Authorization.",
                   "—", "off", ("off", "prv", "pub"), ro, f'<div class="small">{st("pend","Off")}</div>')
        conds = "EndpointReady · ToolReady · RegistrationHealthy · UnmanagedToolAgents"
    else:
        tool_desc = "Channels, threads and canvases for the team's agents. Agents hold their own keys and join over the relay inside the namespace."
        ui = surf("Web UI", "<b>N/A for Buzz.</b> Buzz has no browser client, so the Web UI stays off and disconnected. It becomes available if a later Buzz release adds one.",
                  "—", "off", ("off",), True, f'<div class="small">{st("pend","Off · N/A for Buzz")}</div>')
        api = surf("Web API", "<b>N/A for Buzz.</b> Buzz has no REST API, so the Web API stays off. Agents reach Buzz inside the namespace only.",
                   "—", "off", ("off",), True, f'<div class="small">{st("pend","Off · N/A for Buzz")}</div>')
        conds = "ToolReady · RegistrationHealthy"
    rows = []
    for name, state, sk, *_ in AGENTS:
        if name == "incident-scribe":
            rows.append(f'<tr><td><span class="cb2"></span></td><td><a>{name}</a></td><td>{st("pend","Off")}</td><td class="mono small">—</td><td>{st("pend","disabled")}</td><td>—</td></tr>')
        elif name == "release-notes-bot":
            rows.append(f'<tr><td><span class="cb2"></span></td><td><a>{name}</a></td><td>{st("ok","On")}</td><td class="mono small">—</td><td>{st("warn","pending")}</td><td>—</td></tr>')
        else:
            rid = f"pc_ag_{len(rows) + 1:02d}" if t == "pc" else f"npub1q{len(rows) + 3}x…k{len(rows)}"
            rows.append(f'<tr><td><span class="cb2"></span></td><td><a>{name}</a></td><td>{st("ok","On")}</td><td class="mono small">{rid}</td><td>{st("ok","linked")}</td><td>4 min ago</td></tr>')
    secname = ("paperclip-github-connector", "paperclip-better-auth-secret") if t == "pc" else ("buzz-git-deploy-key", "buzz-relay-admin-key")
    return f"""
<div class="segnote"><b>Collaboration settings live only on this tab.</b> Model, resources, storage, secrets and configuration values of the orchestration agent are on <a>Agent configuration</a>, the same screen every agent uses.</div>
<div class="card"><div class="ch"><div><h2>Collaboration tool</h2><div class="sub">{tool_desc}</div></div><span class="btn sm{dis}">Change tool</span></div><div class="cb"><div class="grid g4">
<div class="kv"><div class="k">Tool</div><div class="v">{tool(t)}</div><div class="k">Version</div><div class="v mono small">{"paperclip 2026.11.2" if t == "pc" else "buzz 0.9.1 (preview)"}</div></div>
<div class="kv"><div class="k">Status</div><div class="v">{st('ok','Ready')} · gen 9 / 9</div><div class="k">Agent registration</div><div class="v">Managed by AFS</div></div>
<div class="kv"><div class="k">In-namespace address</div><div class="v mono small">{"http://paperclip.afs-t-payments-factory.svc:3100" if t == "pc" else "ws://buzz.afs-t-data-contracts.svc:3000"}</div></div>
<div class="kv"><div class="k">Conditions</div><div class="v small">{conds}<br>{st('ok','All healthy')}</div></div>
</div></div></div>
<div class="card"><div class="ch"><div><h2>Endpoints outside the cluster</h2><div class="sub">Off: reachable inside the namespace only. Private: through the corporate network (internal load balancer). Public: from the internet through WAF. Every request signs in with the team's provider and is checked against AFS roles.</div></div>
<span class="btn sm{dis if t == "pc" else " dis"}">Edit endpoints</span></div><div class="cb">
<div class="grid g2">{ui}{api}</div>
<div class="small muted" style="margin-top:10px">{"Service limit for this team: up to <b>Public</b> (set by service admins). Choices above the limit are greyed out." if t == "pc" else "Both surfaces are fixed Off while Buzz is the tool. People follow agent work in Buzz only after a supported client exists (open question OR-OQ-3); switch the tool to Paperclip AI for outside access now."}</div></div></div>
<div class="card"><div class="ch"><div><h2>Connected agents <span class="cnt">(6 of 7)</span></h2><div class="sub">Connected agents get the tool's in-namespace address and their own {"Paperclip key" if t == "pc" else "Buzz keypair"} in their environment. New agents are connected by default.</div></div>
<div class="btns"><span class="btn dis">Disconnect</span><span class="btn{dis}">Connect</span></div></div>
<div class="tools"><div class="filter">🔍 Find agents</div><span class="sel">All link states ▾</span><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Agent</th><th>Connected</th><th>{"Paperclip agent id" if t == "pc" else "Buzz public key"}</th><th>Link state</th><th>Last sync</th></tr>{"".join(rows)}</table></div>
<div class="grid g2">
<div class="card"><div class="ch"><div><h2>Tool-managed secrets <span class="cnt">(2)</span></h2><div class="sub">Created by the tool under the agent's reserved path. Read-only; values are never shown.</div></div></div>
<table><tr><th>Name</th><th>Managed by</th><th>Last changed</th></tr>
<tr><td class="mono">{secname[0]}</td><td><span class="badge b-warn">Managed by {"Paperclip" if t == "pc" else "Buzz"}</span></td><td>2026-11-19</td></tr>
<tr><td class="mono">{secname[1]}</td><td><span class="badge b-blue">Managed by AFS</span></td><td>2026-11-18</td></tr></table></div>
{access_card(t)}</div>
"""


def access_card(t):
    if t != "pc":
        return ('<div class="card"><div class="ch"><div><h2>Recent access</h2><div class="sub">Last 7 days at the endpoints.</div></div></div>'
                '<div class="cb small muted">No endpoints outside the cluster: N/A for Buzz.</div></div>')
    return """<div class="card"><div class="ch"><div><h2>Recent access</h2><div class="sub">Last 7 days at the endpoints. Counts only, no content.</div></div></div><div class="cb">
<div class="grid g3"><div class="kv"><div class="k">Sign-ins</div><div class="big g">64</div></div><div class="kv"><div class="k">People</div><div class="big g">11</div></div><div class="kv"><div class="k">Denied</div><div class="big g">3</div></div></div>
<table><tr><th>Person</th><th>Surface</th><th>Requests</th><th>Denied</th></tr>
<tr><td>marcus.chen@corp.example</td><td>Web UI</td><td class="num">3,880</td><td class="num">1</td></tr>
<tr><td>dana.ortiz@corp.example</td><td>Web UI</td><td class="num">1,204</td><td class="num">0</td></tr>
<tr><td>priya.raman@corp.example <span class="badge b-warn">Service admin entry</span></td><td>Web UI</td><td class="num">42</td><td class="num">0</td></tr></table></div></div>"""


def config_tab(ro):
    dis = " dis" if ro else ""
    return f"""
<div class="segnote">This is the shared agent configuration screen. For the orchestration agent the name, template and IAM identity are fixed, and it cannot be deleted on its own. Collaboration tool and endpoints are on <a>Collaboration</a>.</div>
<div class="card"><div class="ch"><h2>Agent</h2><span class="btn sm{dis}">Edit</span></div><div class="cb"><div class="grid g4">
<div class="kv"><div class="k">Name</div><div class="v mono">orchestrator <span class="muted small">fixed</span></div></div>
<div class="kv"><div class="k">Runtime</div><div class="v">Orchestration runtime <span class="muted small">managed by the service</span></div></div>
<div class="kv"><div class="k">Image</div><div class="v mono small">ghcr.io/…/orchestrator-paperclip@sha256:7c1d…a0</div></div>
<div class="kv"><div class="k">Service account</div><div class="v mono">agent-orchestrator</div></div></div>
<div class="field"><label>Persona and instructions</label><div class="input" style="height:54px">Plan the team's work on the board, split it into issues for the right agents, review results and keep people informed.</div></div></div></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>Models and resources</h2></div><div class="cb">
<div class="kv"><div class="k">Models</div><div class="v"><span class="chip def">claude-sonnet <b>default</b></span><span class="chip">claude-opus</span><span class="chip">claude-haiku</span> <span class="muted small">Selected, 3 of 4 team models</span></div></div>
<div class="kv"><div class="k">Resources</div><div class="v">2 vCPU · 8 GiB · one pod</div></div></div></div>
<div class="card"><div class="ch"><h2>AWS identity</h2></div><div class="cb"><div class="grid g2">
<div class="kv"><div class="k">IAM identity</div><div class="v">Dedicated <span class="muted small">always</span></div></div>
<div class="kv"><div class="k">Role</div><div class="v mono small">afs/agents/afs-t-payments-factory/orchestrator</div></div></div></div></div></div>
<div class="card"><div class="ch"><div><h2>Persistent storage</h2><div class="sub">Holds the collaboration tool's data. Snapshots cannot be turned off for the orchestration agent.</div></div><div class="btns"><span class="btn sm{dis}">Take snapshot</span><span class="btn sm{dis}">Expand</span></div></div><div class="cb"><div class="grid g4">
<div class="kv"><div class="k">Volume</div><div class="v">20 GiB gp3 · 44% used</div></div>
<div class="kv"><div class="k">Mounted at</div><div class="v mono">/var/lib/agent</div></div>
<div class="kv"><div class="k">Snapshots</div><div class="v">Daily, keep 14 · last today 03:00 {st('ok','Completed')}</div></div>
<div class="kv"><div class="k">On team delete</div><div class="v">Snapshot, then delete volume</div></div></div></div></div>
<div class="grid g2">
<div class="card"><div class="ch"><div><h2>Configuration values <span class="cnt">(2)</span></h2></div><span class="btn sm{dis}">Add value</span></div>
<table><tr><th>Name</th><th>Source</th><th>Value</th></tr>
<tr><td class="mono">LOG_LEVEL</td><td>Namespace</td><td class="mono">info</td></tr>
<tr><td class="mono">AFS_OWNED_REPOS</td><td>Namespace</td><td class="mono small">github.com/acme-payments/*</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>Secret bindings <span class="cnt">(4)</span></h2></div><span class="btn sm{dis}">Add binding</span></div>
<table><tr><th>Secret</th><th>Scope</th><th>Delivery</th></tr>
<tr><td>github-bot-key</td><td><span class="badge b-per">Team shared</span></td><td class="mono small">GITHUB_APP_KEY</td></tr>
<tr><td>jira-bot-api-key</td><td><span class="badge b-per">Team shared</span></td><td class="mono small">JIRA_TOKEN</td></tr>
<tr><td colspan="3" class="small muted">+ 2 tool boot secrets managed by AFS (shown on Collaboration)</td></tr></table></div></div>
"""


# ----------------------------------------------------------------- Service admin
opage("32-admin-create-team-orchestration", "admin", admin_nav("teams", orch=True), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Teams</a> › Create team</div>
<div class="wiz"><div class="steps">
<div><div class="n">Step 1</div><b>Team details</b></div>
<div class="on"><div class="n">Step 2</div><b>Orchestration</b></div>
<div class="todo"><div class="n">Step 3</div><b>Models & network</b></div>
<div class="todo"><div class="n">Step 4</div><b>Budget</b></div>
<div class="todo"><div class="n">Step 5</div><b>Members</b></div>
<div class="todo"><div class="n">Step 6</div><b>Review and create</b></div></div>
<div style="flex:1;max-width:860px">
<div class="hdr"><div><h1>Orchestration</h1><div class="desc">Every team gets an orchestration agent when it is created. It runs the team's collaboration tool and is the only part of the team that can be reached from outside the cluster.</div></div></div>
<div class="card"><div class="ch"><h2>Collaboration tool</h2></div><div class="cb">
<div class="tiles">
<div class="tile on"><b><span class="radio on"></span> {tool('pc')} <span class="badge b-per">Service default</span></b><span>Kanban board, chat and agent groupings. Browser web UI and REST API. Agents pull work and report progress.</span></div>
<div class="tile"><b><span class="radio"></span> {tool('bz')} <span class="badge b-warn">Preview</span></b><span>Channels, threads and canvases for agents. No browser client and no REST API, so Web UI and Web API are N/A and stay off.</span></div>
</div>
<div class="small muted" style="margin-top:10px">Team-admins can change the tool later. Changing it starts the new tool empty; the old tool's data is kept in a snapshot.</div></div></div>
<div class="card"><div class="ch"><div><h2>Endpoint limit <span class="badge b-orch-o">Service admins only</span></h2><div class="sub">The highest exposure this team's team-admins may choose for the Web UI and the Web API.</div></div></div><div class="cb">
<div class="tiles" style="grid-template-columns:1fr 1fr 1fr">
<div class="tile"><b><span class="radio"></span> Off</b><span>Inside the namespace only. People cannot open the tool.</span></div>
<div class="tile on"><b><span class="radio on"></span> Private</b><span>Corporate network through the internal load balancer.</span></div>
<div class="tile"><b><span class="radio"></span> Public</b><span>Internet through WAF. Still SSO and AFS roles on every request.</span></div>
</div></div></div>
<div class="card"><div class="ch"><div><h2>Starting endpoints</h2><div class="sub">Team-admins can change these within the limit.</div></div></div><div class="cb">
<div class="grid g2">
<div class="field"><label>Web UI</label><div class="hint">Default from the service: Private</div>{expo('prv', ('off','prv'))}</div>
<div class="field"><label>Web API</label><div class="hint">Default from the service: Off</div>{expo('off', ('off','prv'))}</div></div>
<div class="field"><label>Hostname</label><div class="hint">From the team name. Private and public endpoints use separate domains set in service settings.</div><div class="input ro mono" style="width:520px">payments-factory.collab.corp.example</div></div>
</div></div>
<div class="card"><div class="ch"><h2>Orchestration agent</h2></div><div class="cb"><div class="grid g3">
<div class="field"><label>Models</label><div class="hint">Service default: all team models, default claude-sonnet</div><div class="input">All team models · default claude-sonnet ▾</div></div>
<div class="field"><label>Resources</label><div class="hint">Service default</div><div class="input">1 vCPU · 4 GiB ▾</div></div>
<div class="field"><label>Volume</label><div class="hint">Service default</div><div class="input">20 GiB · daily snapshots, keep 14</div></div></div>
<div class="small muted">Named <span class="mono">orchestrator</span>, with its own IAM role. Its model calls count against the team budget.</div></div></div>
<div style="display:flex;justify-content:flex-end;gap:8px"><span class="btn" style="border:0">Cancel</span><span class="btn">Previous</span><span class="btn p">Next</span></div>
</div></div>
""")

TEAMS_ORCH = [
    ("payments-factory", "per", "pc", "prv", "off", "pub", ("ok", "Ready")),
    ("search-relevance", "per", "pc", "pub", "prv", "pub", ("ok", "Ready")),
    ("claims-modernization", "per", "pc", "prv", "prv", "prv", ("err", "Degraded")),
    ("data-contracts", "per", "bz", "na", "na", "prv", ("ok", "Ready")),
    ("mobile-platform", "per", "pc", "off", "off", "off", ("ok", "Ready")),
    ("cve-2026-41873-swarm", "eph", "pc", "prv", "off", "prv", ("ok", "Ready")),
    ("ledger-archive", "per", "pc", "prv", "off", "prv", ("warn", "Migrating")),
]


def orch_team_rows(selected=None):
    out = []
    for n, kind, t, ui, api, lim, (sk, s) in TEAMS_ORCH:
        badge = '<span class="badge b-eph">Ephemeral</span>' if kind == "eph" else '<span class="badge b-per">Persistent</span>'
        cls = "sel" if n == selected else ""
        out.append(f'<tr class="{cls}"><td><span class="radio {"on" if cls else ""}"></span></td><td><a>{n}</a></td><td>{badge}</td><td>{tool(t)}</td><td>{st(sk, s)}</td><td>{lvl(ui)}</td><td>{lvl(api)}</td><td>Up to {lvl(lim)}</td></tr>')
    return "".join(out)


opage("33-admin-teams-orchestration", "admin", admin_nav("teams", orch=True), f"""
<div class="crumbs"><a>Agent Factory</a> › Teams</div>
<div class="card"><div class="ch"><div><h2>Teams <span class="cnt">(42)</span> <span class="info">Info</span></h2>
<div class="sub">Each team is an isolated namespace with its own orchestration agent, IAM role, secrets and budget.</div></div>
<div class="btns"><span class="btn">⟳</span><span class="btn">View details</span><span class="btn dd">Actions</span><span class="btn p">Create team</span></div></div>
<div class="tools"><div class="filter">🔍 Find teams by name, cost center or tag</div><span class="sel">Any tool ▾</span><span class="sel">Any exposure ▾</span>
<div class="pager">‹ <b>1</b> 2 3 4 5 › &nbsp; ⚙</div></div>
<table><tr><th></th><th>Name ▴</th><th>Kind</th><th>Collaboration tool</th><th>Orchestration</th><th>Web UI</th><th>Web API</th><th>Endpoint limit</th></tr>
{orch_team_rows("payments-factory")}</table></div>
<div class="card"><div class="ch"><h2>payments-factory</h2><div class="btns"><span class="btn sm">Set endpoint limit</span><span class="btn sm">Open team</span></div></div>
<div class="tabs" style="margin:0 20px 14px"><span>Details</span><span class="on">Orchestration</span><span>Guardrails</span><span>AWS account access</span><span>Budget</span></div>
<div class="cb"><div class="grid g4">
<div class="kv"><div class="k">Orchestration agent</div><div class="v"><a>orchestrator</a> {st('ok','Ready')}</div></div>
<div class="kv"><div class="k">Collaboration tool</div><div class="v">{tool('pc')}</div></div>
<div class="kv"><div class="k">Endpoint limit</div><div class="v">{expo('pub')}</div></div>
<div class="kv"><div class="k">Last outside access</div><div class="v">12 min ago</div></div></div>
<div class="small muted">Lowering the limit turns endpoints above it off within 60 seconds; the team's stored choices are kept and restored if the limit is raised again.</div></div></div>
""")

opage("34-admin-orchestration", "admin", admin_nav("orch", orch=True), f"""
<div class="crumbs"><a>Agent Factory</a> › Orchestration</div>
<div class="hdr"><div><h1>Orchestration <span class="info">Info</span></h1>
<div class="desc">Defaults for every team's orchestration agent, the collaboration tools teams may use, and every endpoint reachable from outside the cluster.</div></div>
<div class="btns"><span class="btn">Download CSV</span><span class="btn dd">Actions</span></div></div>
<div class="alert warn"><span class="ic">⚠</span><div><b>Migration in progress: 38 of 42 teams have an orchestration agent.</b> 3 teams are being given one now; 1 team (ledger-archive) needs a larger compute quota for the orchestration pod. <a>View migration</a></div></div>
<div class="tabs"><span class="on">Endpoints</span><span>Tools and runtimes</span><span>Defaults</span><span>Kill switches</span></div>
<div class="grid g4">
<div class="card"><div class="ch"><h2>Public endpoints</h2></div><div class="cb"><div class="big">9</div><div class="small muted">Internet, through WAF · <span class="mono">*.collab.example.com</span></div></div></div>
<div class="card"><div class="ch"><h2>Private endpoints</h2></div><div class="cb"><div class="big">30</div><div class="small muted">Corporate network · <span class="mono">*.collab.corp.example</span></div></div></div>
<div class="card"><div class="ch"><h2>Tools in use</h2></div><div class="cb"><div class="big g">39 · 3</div><div class="small muted">Paperclip AI · Buzz (preview, no outside endpoints)</div></div></div>
<div class="card"><div class="ch"><h2>Denied, 24 h</h2></div><div class="cb"><div class="big g">57</div><div class="small muted">1 denied-spike alert (claims-modernization)</div></div></div>
</div>
<div class="card"><div class="ch"><div><h2>Endpoints outside the cluster <span class="cnt">(39)</span></h2><div class="sub">Only orchestration agents have them. Every request is signed in through the team's provider and checked against AFS roles.</div></div></div>
<div class="tools"><div class="filter">🔍 Find by team or hostname</div><span class="sel">Any exposure ▾</span><span class="sel">Any surface ▾</span><div class="pager">‹ <b>1</b> 2 3 › ⚙</div></div>
<table><tr><th>Team</th><th>Tool</th><th>Surface</th><th>Exposure</th><th>Hostname</th><th>State</th><th>Last access</th></tr>
<tr><td><a>search-relevance</a></td><td>{tool('pc')}</td><td>Web UI</td><td>{lvl('pub')}</td><td class="mono small">search-relevance.collab.example.com</td><td>{st('ok','Ready')}</td><td>2 min ago</td></tr>
<tr><td><a>search-relevance</a></td><td>{tool('pc')}</td><td>Web API</td><td>{lvl('prv')}</td><td class="mono small">search-relevance.collab.corp.example/api</td><td>{st('ok','Ready')}</td><td>9 min ago</td></tr>
<tr><td><a>payments-factory</a></td><td>{tool('pc')}</td><td>Web UI</td><td>{lvl('prv')}</td><td class="mono small">payments-factory.collab.corp.example</td><td>{st('ok','Ready')}</td><td>12 min ago</td></tr>
<tr><td><a>claims-modernization</a></td><td>{tool('pc')}</td><td>Web UI</td><td>{lvl('prv')}</td><td class="mono small">claims-modernization.collab.corp.example</td><td>{st('err','Degraded')}</td><td>1 h ago</td></tr>
<tr><td><a>cve-2026-41873-swarm</a> <span class="badge b-eph">Ephemeral</span></td><td>{tool('pc')}</td><td>Web UI</td><td>{lvl('prv')}</td><td class="mono small">cve-2026-41873-swarm.collab.corp.example</td><td>{st('ok','Ready')}</td><td>40 min ago</td></tr></table></div>
<div class="grid g2">
<div class="card"><div class="ch"><div><h2>Collaboration tools</h2><div class="sub">Tools teams may pick. Each maps to an orchestration runtime template that only service admins see.</div></div><span class="btn sm">Edit</span></div>
<table><tr><th>Tool</th><th>Enabled</th><th>Default</th><th>Runtime template</th><th>Teams</th></tr>
<tr><td>{tool('pc')}</td><td>{tg(True)}</td><td>✓</td><td class="mono small">orchestrator-paperclip v3.1</td><td>39</td></tr>
<tr><td>{tool('bz')} <span class="badge b-warn">Preview</span></td><td>{tg(True)}</td><td></td><td class="mono small">orchestrator-buzz v0.4</td><td>3</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>Defaults for new teams</h2></div><span class="btn sm">Edit</span></div><div class="cb"><div class="grid g2">
<div class="kv"><div class="k">Endpoint limit</div><div class="v">{lvl('prv')}</div><div class="k">Web UI at creation</div><div class="v">{lvl('prv')}</div></div>
<div class="kv"><div class="k">Web API at creation</div><div class="v">{lvl('off')}</div><div class="k">Service-wide kill switch</div><div class="v">Public {tg(True)} &nbsp; Private {tg(True)}</div></div></div></div></div></div>
""")

# ----------------------------------------------------------------- Team-admin
def overview_orch(ro):
    dis = " dis" if ro else ""
    tip = '<span class="tip"><span class="tipbox">Requires team-admin</span></span>' if ro else ""
    return f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Teams</a> › payments-factory</div>
{RO_BANNER if ro else ""}
<div class="hdr"><div><h1>payments-factory <span class="badge b-per">Persistent</span> <span class="info">Info</span></h1>
<div class="desc">Payments Software Factory · Agents maintaining the payments ledger services</div></div>
<div class="btns"><span class="btn{dis}">Edit</span><span class="btn dd{dis}">Actions</span><span class="btn p{dis}">Create agent</span>{tip}</div></div>
<div class="card"><div class="ch"><h2>Summary</h2></div><div class="cb"><div class="grid g4">
<div class="kv"><div class="k">State</div><div class="v">{st('ok','Active')}</div><div class="k">Reconcile status</div><div class="v">{st('ok','Ready')} · gen 37 / 37</div></div>
<div class="kv"><div class="k">Namespace</div><div class="v mono">afs-t-payments-factory</div><div class="k">Cluster</div><div class="v">prod-use1-a</div></div>
<div class="kv"><div class="k">Team IAM role</div><div class="v mono small">arn:aws:iam::…:role/afs-team-payments</div><div class="k">Cost center</div><div class="v">CC-4410</div></div>
<div class="kv"><div class="k">Owner</div><div class="v">payments-eng-leads@corp.example</div><div class="k">Created</div><div class="v">2026-09-02 by priya.raman</div></div>
</div></div></div>
{orch_card(ro, compact=True)}
<div class="grid g3">
<div class="card"><div class="ch"><h2>Budget, November</h2><a>Budget & usage</a></div><div class="cb">
<div class="big">$31,880</div><div class="small muted" style="margin-bottom:8px">of $40,000 monthly · includes orchestrator $2,140</div>{bar(80,'w')}</div></div>
<div class="card"><div class="ch"><h2>Team agents</h2><a>View agents</a></div><div class="cb">
<div class="grid g2"><div class="kv"><div class="k">Running</div><div class="big g">5</div></div><div class="kv"><div class="k">Connected to Paperclip AI</div><div class="big g">6 / 7</div></div></div>
<div class="small">{st('warn','1 agent restarting')} · release-notes-bot</div></div></div>
<div class="card"><div class="ch"><h2>Recent activity</h2><a>Activity & audit</a></div><div class="cb small">
<div style="margin-bottom:8px"><b>marcus.chen</b> set Web UI to Private <span class="muted">· 2h</span></div>
<div style="margin-bottom:8px"><b>system:reconciler</b> linked test-gap-finder to Paperclip AI <span class="muted">· 5h</span></div>
<div><b>priya.raman</b> raised the endpoint limit to Public <span class="muted">· 1d</span></div></div></div>
</div>"""


opage("35-ta-team-overview-orchestration", "ta", team_nav("overview", "ta", orch=True), overview_orch(False))
opage("36-ta-agents-orchestration", "ta", team_nav("agents", "ta", orch=True), agents_page(False))
opage("37-ta-orchestration-collaboration", "ta", team_nav("orch", "ta", orch=True), orch_header(False, "collab") + collab_tab(False))
opage("38-ta-orchestration-agent-config", "ta", team_nav("orch", "ta", orch=True), orch_header(False, "config") + config_tab(False))

EDIT_MODAL = f"""<div class="modalwrap"><div class="modal" style="width:760px"><div class="mh">Edit endpoints <span class="muted">✕</span></div><div class="mb">
<div class="field"><label>Web UI</label><div class="hint">Paperclip AI in a browser for the team's people.</div>{expo('pub')}</div>
<div class="alert warn" style="margin-top:-4px"><span class="ic">⚠</span><div><b>Public means reachable from the internet.</b> AWS WAF, sign-in with Okta and AFS role checks still apply to every request. The change is recorded in the team's audit log and takes effect within 60 seconds.</div></div>
<div class="field"><label>Web API</label><div class="hint">Paperclip AI's REST API for pipelines and the afs CLI. Writes need the collaborator or team-admin role.</div>{expo('prv')}</div>
<div class="small muted" style="margin-bottom:8px">Service limit for this team: up to Public.</div>
<div class="code">afs orchestration put-orchestration --team-id team_01JD3Z… \\<br>&nbsp; --web-ui-exposure public --web-api-exposure private \\<br>&nbsp; --if-match 9</div>
</div><div class="mf"><span class="btn" style="border:0">Cancel</span><span class="btn p">Save endpoints</span></div></div></div>"""
opage("39-ta-orchestration-edit-endpoints", "ta", team_nav("orch", "ta", orch=True), orch_header(False, "collab") + collab_tab(False), EDIT_MODAL)

opage("40-ta-create-agent-collaboration", "ta", team_nav("agents", "ta", orch=True), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › <a>Agents</a> › Create agent</div>
<div class="hdr"><div><h1>Create agent</h1><div class="desc">Adds a team agent. The team's orchestration agent already exists and is managed on Orchestration.</div></div></div>
<div class="split"><div style="flex:1;max-width:860px">
<div class="card"><div class="ch"><h2>Agent</h2></div><div class="cb">
<div class="grid g2"><div class="field"><label>Name</label><div class="hint"><span class="mono">orchestrator</span> is reserved</div><div class="input">security-patcher</div></div>
<div class="field"><label>Template</label><div class="hint">From the Agentic Teammates runtime catalog</div><div class="input">hermes-dev (v2.4) ▾</div></div></div>
<div class="field"><label>Persona and instructions</label><div class="input" style="height:54px">Keeps payments services free of known-vulnerable dependencies; opens PRs, never merges.</div></div>
</div></div>
<div class="card"><div class="ch"><h2>Models and resources</h2></div><div class="cb">
{models_field()}
<div class="field"><label>Resources</label><div class="hint">One pod per agent. Add agents to add capacity.</div><div class="input" style="width:280px">2 vCPU · 8 GiB ▾</div></div></div></div>
<div class="card"><div class="ch"><h2>Persistent storage · AWS identity · Configuration values · Secrets</h2></div><div class="cb small muted">Unchanged from today's Create agent (T3): storage, IAM identity, configuration values and secret bindings.</div></div>
<div class="orch"><div class="oh"><div><h2><span class="oic">◆</span> Collaboration</h2><div class="sub">How this agent works with the team's orchestration agent. Settings for the tool itself are on Orchestration.</div></div></div>
<div class="ob"><div class="field"><label>{tg(True)} Connect to Paperclip AI</label><div class="hint">On by default. The agent gets the tool's in-namespace address and its own Paperclip key by environment, and may open a connection to the orchestration agent only. It is never reachable from outside.</div></div>
<div class="grid g3"><div class="kv"><div class="k">Address</div><div class="v mono small">http://paperclip.afs-t-payments-factory.svc:3100</div></div>
<div class="kv"><div class="k">Registration</div><div class="v">Managed by AFS</div></div>
<div class="kv"><div class="k">Environment</div><div class="v mono small">AFS_COLLAB_URL, PAPERCLIP_*</div></div></div></div></div>
<div style="display:flex;justify-content:flex-end;gap:8px"><span class="btn" style="border:0">Cancel</span><span class="btn p">Create agent</span></div>
</div>
<div style="width:360px"><div class="card"><div class="ch"><h2>Equivalent CLI</h2></div><div class="cb">
<div class="code">afs agents create-agent \\<br>&nbsp; --team-id team_01JD3Z… \\<br>&nbsp; --name security-patcher \\<br>&nbsp; --template hermes-dev \\<br>&nbsp; --models claude-sonnet claude-haiku \\<br>&nbsp; --default-model-id claude-sonnet \\<br>&nbsp; --collaboration-connect</div>
<div class="small muted" style="margin-top:8px">There is no role option: every agent you create is a team agent.</div></div></div></div>
</div>
""")

ROLE_PILL["ta2"] = '<span class="pill ta">Team-admin · data-contracts</span>'
USER["ta2"] = "Lee Park"
opage("41-ta-orchestration-buzz", "ta2", team_nav("orch", "ta", team="data-contracts", orch=True),
      orch_header(False, "collab", "bz").replace("payments-factory", "data-contracts") + collab_tab(False, "bz").replace("payments-factory", "data-contracts"))

# ----------------------------------------------------------------- Team viewer
opage("42-tv-agents-orchestration", "tv", team_nav("agents", "tv", orch=True), agents_page(True))
opage("43-tv-orchestration", "tv", team_nav("orch", "tv", orch=True), orch_header(True, "collab") + collab_tab(True))


# ----------------------------------------------------------------- Model access (J, 2026-11-23)
CATALOG = [
    ("anthropic.claude-opus-…", "Anthropic", True, "15.00", "75.00", "18", ("ok", "Approved")),
    ("anthropic.claude-sonnet-…", "Anthropic", True, "3.00", "15.00", "42", ("ok", "Approved")),
    ("anthropic.claude-haiku-…", "Anthropic", True, "1.00", "5.00", "42", ("ok", "Approved")),
    ("amazon.nova-pro-…", "Amazon", True, "0.80", "3.20", "40", ("ok", "Approved")),
    ("amazon.titan-embed-…", "Amazon", True, "0.02", "—", "40", ("ok", "Approved")),
    ("meta.llama-4-maverick-…", "Meta", True, "—", "—", "0", ("warn", "Waiting for approval")),
]


def catalog_rows():
    out = []
    for m, prov, en, i, o, teams, (sk, ps) in CATALOG:
        out.append(f'<tr><td><span class="cb2"></span></td><td class="mono">{m}</td><td>{prov}</td><td>{st("ok","Enabled") if en else st("pend","Disabled")}</td>'
                   f'<td>{st(sk, ps)}</td><td>{i}</td><td>{o}</td><td>{teams}</td></tr>')
    return "".join(out)


opage("44-admin-model-access", "admin", admin_nav("models", orch=True), f"""
<div class="crumbs"><a>Agent Factory</a> › Model catalog & pricing</div>
<div class="hdr"><div><h1>Model catalog & pricing <span class="info">Info</span></h1>
<div class="desc">Bedrock models agents may call through the metering gateway. A model is callable only with an approved price.</div></div>
<div class="btns"><span class="btn">Sync from Bedrock</span><span class="btn dd">Actions</span></div></div>
<div class="card"><div class="ch"><div><h2>Models enabled for the service</h2><div class="sub">Teams choose from these. Each team's list is set on the team (default: all service models).</div></div><span class="btn sm">Edit</span></div><div class="cb">
<div class="tiles">
<div class="tile on"><b><span class="radio on"></span> All models <span class="badge b-per">Default</span></b><span>Every Bedrock model in the catalog, including models added by the daily sync. New models become callable when their price is approved.</span></div>
<div class="tile"><b><span class="radio"></span> Selected models</b><span>Only the models switched on below. New models from the sync start disabled.</span></div>
</div></div></div>
<div class="card"><div class="ch"><div><h2>Catalog <span class="cnt">(6)</span></h2><div class="sub">Synced daily from Bedrock in this region. With <b>All models</b>, the Enabled column follows the catalog and cannot be switched per model.</div></div><div class="btns"><span class="btn dis">Disable</span><span class="btn dis">Enable</span></div></div>
<div class="tools"><div class="filter">🔍 Find models</div><span class="sel">Any provider ▾</span><span class="sel">Any price state ▾</span><div class="pager">‹ <b>1</b> › &nbsp; ⚙</div></div>
<table><tr><th></th><th>Model</th><th>Provider</th><th>Service</th><th>Price</th><th>Input $/MTok</th><th>Output $/MTok</th><th>Teams with access</th></tr>
{catalog_rows()}</table></div>
<div class="alert warn"><span class="ic">⚠</span><div><b>1 model is enabled but not callable yet.</b> meta.llama-4-maverick has no approved price, so the gateway refuses its calls (budgets need a price to reserve spend). <a>Review prices</a></div></div>
""")

opage("45-admin-team-models", "admin", admin_nav("teams", orch=True), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Teams</a> › Create team</div>
<div class="wiz"><div class="steps">
<div><div class="n">Step 1</div><b>Team details</b></div>
<div><div class="n">Step 2</div><b>Orchestration</b></div>
<div class="on"><div class="n">Step 3</div><b>Models & network</b></div>
<div class="todo"><div class="n">Step 4</div><b>Budget</b></div>
<div class="todo"><div class="n">Step 5</div><b>Members</b></div>
<div class="todo"><div class="n">Step 6</div><b>Review and create</b></div></div>
<div style="flex:1;max-width:860px">
<div class="hdr"><div><h1>Models & network</h1><div class="desc">Which models this team's agents may call. Team-admins then choose all, one or several of these per agent.</div></div></div>
<div class="card"><div class="ch"><div><h2>Models for this team <span class="badge b-orch-o">Service admins only</span></h2><div class="sub">From the models enabled for the service (6).</div></div></div><div class="cb">
<div class="tiles">
<div class="tile on"><b><span class="radio on"></span> All service models <span class="badge b-per">Default</span></b><span>Every model enabled for the service, now and later. Removing a model from the service removes it here.</span></div>
<div class="tile"><b><span class="radio"></span> Selected models</b><span>Only the models you pick. Models the service adds later are not added.</span></div>
</div>
<table style="margin-top:12px"><tr><th>Model</th><th>Provider</th><th>Price</th><th>Inference profile</th></tr>
<tr><td class="mono">anthropic.claude-opus-…</td><td>Anthropic</td><td>{st('ok','Approved')}</td><td class="muted">Created with the team</td></tr>
<tr><td class="mono">anthropic.claude-sonnet-…</td><td>Anthropic</td><td>{st('ok','Approved')}</td><td class="muted">Created with the team</td></tr>
<tr><td class="mono">anthropic.claude-haiku-…</td><td>Anthropic</td><td>{st('ok','Approved')}</td><td class="muted">Created with the team</td></tr>
<tr><td class="mono">amazon.nova-pro-…</td><td>Amazon</td><td>{st('ok','Approved')}</td><td class="muted">Created with the team</td></tr>
<tr><td class="mono">amazon.titan-embed-…</td><td>Amazon</td><td>{st('ok','Approved')}</td><td class="muted">Created with the team</td></tr>
<tr><td class="mono">meta.llama-4-maverick-…</td><td>Meta</td><td>{st('warn','Waiting for approval')}</td><td class="muted">Created when the price is approved</td></tr></table>
</div></div>
<div class="card"><div class="ch"><h2>Network</h2></div><div class="cb small muted">Unchanged: isolation tier and external systems (S3 step 2 today).</div></div>
<div class="card"><div class="ch"><h2>Equivalent CLI</h2></div><div class="cb"><div class="code">afs teams create-team … --model-access all</div></div></div>
<div style="display:flex;justify-content:flex-end;gap:8px"><span class="btn" style="border:0">Cancel</span><span class="btn">Previous</span><span class="btn p">Next</span></div>
</div></div>
""")
