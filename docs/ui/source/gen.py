"""Generates console-style mockup screens for the Agent Factory PRD.

Each screen is a standalone HTML file; shoot.mjs renders them to PNG (node shoot.mjs [prefix ...]).
"""
import html
import pathlib

OUT = pathlib.Path(__file__).parent / "screens"
OUT.mkdir(exist_ok=True)

CSS = """
:root{--nav:#0f141a;--nav2:#161d26;--text:#0f141a;--muted:#5f6b7a;--line:#d1d5db;--soft:#e9ebed;
--bg:#ffffff;--page:#f9fafb;--link:#006ce0;--blue:#006ce0;--blue-d:#004a9e;--green:#00802f;--red:#db0000;
--amber:#855900;--info-bg:#f0fbff;--info-line:#006ce0;--warn-bg:#fffef0;--warn-line:#855900;--err-bg:#fff5f5;
--purple:#7300e5}
*{box-sizing:border-box}
body{margin:0;font-family:"Open Sans","Helvetica Neue",Arial,sans-serif;font-size:14px;color:var(--text);background:var(--page)}
a{color:var(--link);text-decoration:none}
.top{height:40px;background:var(--nav);color:#fff;display:flex;align-items:center;padding:0 16px;gap:16px}
.brand{display:flex;align-items:center;gap:8px;font-weight:700;font-size:15px}
.logo{width:22px;height:22px;border-radius:5px;background:linear-gradient(135deg,#3d8bff,#7a4dff);display:grid;place-items:center;font-size:11px}
.search{flex:0 0 420px;height:28px;border-radius:14px;background:var(--nav2);border:1px solid #414d5c;color:#8c959f;padding:4px 14px;font-size:13px}
.top .sp{flex:1}
.top .item{color:#d1d5db;font-size:13px;display:flex;align-items:center;gap:6px}
.pill{border:1px solid #414d5c;border-radius:12px;padding:2px 10px;font-size:12px;color:#fff}
.pill.admin{border-color:#ff9900;color:#ffb84d}
.pill.ta{border-color:#5fa8ff;color:#9ccaff}
.pill.tv{border-color:#9aa5b1;color:#d1d5db}
.pill.so{border-color:#ff5d64;color:#ffb3b6}
.shell{display:flex;min-height:calc(100vh - 40px)}
.side{width:232px;background:#fff;border-right:1px solid var(--soft);padding:16px 0;flex:0 0 232px}
.side h4{margin:0 20px 10px;font-size:16px}
.side .grp{margin:14px 20px 6px;font-size:12px;font-weight:700;color:var(--muted);text-transform:none}
.side a{display:block;padding:5px 20px;color:var(--text);font-size:14px}
.side a.on{color:var(--blue);font-weight:700;border-left:3px solid var(--blue);padding-left:17px;background:#f0f7ff}
.side a.dim{color:#9aa5b1}
.side hr{border:0;border-top:1px solid var(--soft);margin:12px 20px}
.team-switch{margin:4px 16px 8px;border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:13px;display:flex;justify-content:space-between}
.main{flex:1;padding:14px 28px 40px;min-width:0}
.crumbs{font-size:13px;color:var(--muted);margin-bottom:10px}
.crumbs a{color:var(--link)}
.hdr{display:flex;align-items:flex-end;justify-content:space-between;margin:6px 0 16px}
.hdr h1{font-size:24px;margin:0;font-weight:700;display:flex;align-items:center;gap:10px}
.hdr .desc{color:var(--muted);font-size:14px;margin-top:4px}
.info{font-size:13px;font-weight:700;color:var(--link)}
.btns{display:flex;gap:8px}
.btn{border:2px solid var(--blue);color:var(--blue);background:#fff;border-radius:20px;padding:4px 18px;font-weight:700;font-size:14px;white-space:nowrap}
.btn.p{background:var(--blue);color:#fff}
.btn.dis{border-color:#c6c6cd;color:#9aa5b1;background:#fff}
.btn.p.dis{background:#e9ebed;border-color:#e9ebed;color:#9aa5b1}
.btn.dd:after{content:" ▾"}
.btn.sm{padding:2px 12px;font-size:13px}
.card{background:#fff;border-radius:16px;box-shadow:0 1px 1px rgba(0,7,22,.12),0 0 1px rgba(0,7,22,.15);margin-bottom:20px;overflow:hidden}
.card>.ch{padding:14px 20px 10px;display:flex;justify-content:space-between;align-items:center}
.card>.ch h2{font-size:18px;margin:0;font-weight:700}
.card>.ch h2 .cnt{color:var(--muted);font-weight:400}
.card>.ch .sub{color:var(--muted);font-size:13px;margin-top:2px}
.card>.cb{padding:4px 20px 18px}
.grid{display:grid;gap:20px}
.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(4,1fr)}
.kv .k{color:var(--muted);font-size:13px;margin-bottom:2px}
.kv .v{font-size:14px;margin-bottom:14px}
.big{font-size:30px;font-weight:300;color:var(--blue)}
.big.g{color:var(--text)}
.tools{display:flex;gap:10px;align-items:center;padding:0 20px 10px}
.filter{flex:1;max-width:520px;border:1px solid var(--line);border-radius:8px;padding:5px 12px;color:#8c959f;font-size:13px}
.sel{border:1px solid var(--line);border-radius:8px;padding:5px 12px;font-size:13px;color:var(--text)}
.pager{margin-left:auto;display:flex;gap:10px;color:var(--muted);font-size:13px;align-items:center}
.pager b{color:var(--blue);border:0}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:13px;font-weight:700;padding:8px 12px;border-bottom:1px solid var(--line);white-space:nowrap;background:#fff}
td a{white-space:nowrap}
td{padding:9px 12px;border-bottom:1px solid var(--soft);font-size:14px;vertical-align:middle}
tr.sel td{background:#f0f7ff}
tr.sel td:first-child{box-shadow:inset 2px 0 0 var(--blue)}
.cb2{width:14px;height:14px;border:2px solid #8c959f;border-radius:3px;display:inline-block;vertical-align:middle}
.cb2.on{background:var(--blue);border-color:var(--blue)}
.radio{width:14px;height:14px;border:2px solid #8c959f;border-radius:50%;display:inline-block;vertical-align:middle}
.radio.on{border:4px solid var(--blue)}
.st{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.st:before{content:"";width:10px;height:10px;border-radius:50%;background:currentColor}
.ok{color:var(--green)}.err{color:var(--red)}.warn{color:var(--amber)}.pend{color:var(--muted)}.inf{color:var(--blue)}
.st.pend:before{background:none;border:2px solid currentColor;width:8px;height:8px}
.badge{display:inline-block;border-radius:4px;padding:0 6px;font-size:12px;font-weight:700;border:1px solid}
.b-eph{color:var(--purple);border-color:var(--purple)}
.b-per{color:var(--muted);border-color:#9aa5b1}
.b-blue{color:var(--blue);border-color:var(--blue)}
.mono{font-family:"DejaVu Sans Mono",Menlo,monospace;font-size:12.5px}
.bar{height:8px;background:var(--soft);border-radius:4px;overflow:hidden;min-width:110px}
.bar>i{display:block;height:100%;background:var(--blue)}
.bar.w>i{background:#b38200}.bar.r>i{background:var(--red)}
.alert{border:2px solid var(--info-line);background:var(--info-bg);border-radius:12px;padding:10px 16px;margin-bottom:16px;display:flex;gap:10px}
.alert.warn{border-color:var(--warn-line);background:var(--warn-bg);color:var(--text)}
.alert.err{border-color:var(--red);background:var(--err-bg);color:var(--text)}
.alert .ic{font-weight:700}
.rbar{display:flex;gap:10px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg span{padding:5px 12px;font-size:13px;border-right:1px solid var(--line)}.seg span:last-child{border-right:0}
.seg span.on{background:var(--blue);color:#fff;font-weight:700}
.sb{display:flex;align-items:flex-end;gap:5px;height:170px;border-bottom:1px solid var(--line);padding-top:8px}
.sb .c{flex:1;display:flex;flex-direction:column-reverse}
.sb .c i{display:block}
.lg{display:flex;gap:16px;font-size:12.5px;color:var(--muted);margin-top:8px;flex-wrap:wrap}
.lg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}
.hm{display:grid;grid-template-columns:150px repeat(24,1fr);gap:2px;font-size:11.5px;align-items:center}
.hm b{font-weight:400;color:var(--muted);text-align:center}
.hm .n{font-size:12.5px;white-space:nowrap;overflow:hidden}
.hm i{display:block;height:18px;border-radius:2px}
.strip{display:flex;height:22px;border-radius:4px;overflow:hidden}
.strip i{display:block;height:100%}
.kpi .big{font-size:26px}
.num{text-align:right;font-variant-numeric:tabular-nums}
.tg{display:inline-block;width:34px;height:18px;border-radius:9px;background:#9aa5b1;position:relative;vertical-align:middle}
.tg:after{content:"";position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:#fff}
.tg.on{background:var(--blue)}.tg.on:after{left:18px}.tg.dis{opacity:.45}
.b-warn{color:var(--amber);border-color:var(--amber)}
.alert.warn .ic{color:var(--amber)}.alert .ic{color:var(--blue)}.alert.err .ic{color:var(--red)}
.tabs{display:flex;gap:0;border-bottom:1px solid var(--line);margin-bottom:18px}
.tabs span{padding:8px 16px;font-weight:700;color:var(--muted)}
.tabs span.on{color:var(--blue);border-bottom:3px solid var(--blue)}
.field{margin-bottom:16px}
.field label{display:block;font-weight:700;font-size:14px;margin-bottom:2px}
.field .hint{color:var(--muted);font-size:13px;margin-bottom:6px}
.input{border:1px solid #8c959f;border-radius:8px;padding:6px 12px;font-size:14px;background:#fff;min-height:32px}
.input.ph{color:#8c959f}
.input.ro{background:#f3f3f7;color:var(--muted);border-color:#c6c6cd}
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.tile{border:2px solid var(--line);border-radius:12px;padding:12px 14px}
.tile.on{border-color:var(--blue);background:#f0f7ff}
.tile b{display:block;margin-bottom:4px}
.tile span{color:var(--muted);font-size:13px}
.wiz{display:flex;gap:32px}
.steps{width:200px;flex:0 0 200px;font-size:13px}
.steps div{padding:0 0 18px}
.steps .n{color:var(--muted);font-size:12px}
.steps .on b{color:var(--text)}
.steps b{color:var(--link)}
.steps .todo b{color:#9aa5b1}
.split{display:flex;gap:20px}
.chart{height:170px;display:flex;align-items:flex-end;gap:6px;padding:8px 0 0;border-bottom:1px solid var(--line);position:relative}
.chart .c{flex:1;display:flex;flex-direction:column-reverse;gap:1px}
.chart .c i{display:block;background:#688ae8;border-radius:2px 2px 0 0}
.chart .c i.b{background:#c33d69}
.chart .cap{position:absolute;left:0;right:0;border-top:2px dashed var(--red)}
.chart .cap span{position:absolute;right:0;top:-18px;font-size:11px;color:var(--red);font-weight:700}
.legend{display:flex;gap:16px;font-size:12px;color:var(--muted);margin-top:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.tip{position:relative;display:inline-block}
.tipbox{position:absolute;bottom:40px;right:0;background:#0f141a;color:#fff;font-size:12px;padding:6px 10px;border-radius:6px;white-space:nowrap}
.modalwrap{position:absolute;inset:40px 0 0 0;background:rgba(15,20,26,.55);display:grid;place-items:center}
.modal{background:#fff;border-radius:16px;width:620px;box-shadow:0 4px 20px rgba(0,7,22,.3)}
.modal .mh{padding:16px 20px;font-weight:700;font-size:18px;border-bottom:1px solid var(--soft);display:flex;justify-content:space-between}
.modal .mb{padding:16px 20px}
.modal .mf{padding:12px 20px;border-top:1px solid var(--soft);display:flex;justify-content:flex-end;gap:8px}
.foot{position:fixed;bottom:0;left:0;right:0;height:28px;background:var(--nav);color:#9aa5b1;font-size:12px;display:flex;align-items:center;padding:0 16px;gap:20px}
.muted{color:var(--muted)}
.small{font-size:12.5px}
.tag{display:inline-block;background:#f3f3f7;border-radius:4px;padding:1px 6px;font-size:12px;margin-right:4px}
.code{background:#0f141a;color:#d1d5db;border-radius:8px;padding:10px 14px;font-family:"DejaVu Sans Mono",monospace;font-size:12px;line-height:1.6}
"""

ROLE_PILL = {
    "admin": '<span class="pill admin">Service admin</span>',
    "ta": '<span class="pill ta">Team-admin · payments-factory</span>',
    "tv": '<span class="pill tv">Team viewer · payments-factory</span>',
    "so": '<span class="pill so">Security operator</span>',
    "sw": '<span class="pill ta">Team-admin · cve-2026-41873-swarm</span>',
}
USER = {"admin": "Priya Raman", "ta": "Marcus Chen", "tv": "Dana Ortiz", "so": "Sam Okafor", "sw": "Marcus Chen"}


def admin_nav(on, orch=False):
    items = [
        ("grp", "Service"), ("dash", "Dashboard"), ("teams", "Teams"), ("wo", "Work orders"),
        ("grp", "Governance"), ("budgets", "Budgets & ceilings"), ("reports", "Reports & analytics"), ("costs", "Cost reconciliation"), ("tags", "Cost allocation tags"),
        ("audit", "Audit log"),
        ("grp", "Platform"), ("models", "Model catalog & pricing"), ("templates", "Agent templates"), ("swarmt", "Swarm templates"),
        ("external", "External systems"), ("settings", "Service settings"), ("export", "Export & import"),
    ]
    if orch:
        items.insert(items.index(("external", "External systems")), ("orch", "Orchestration"))
    return nav("Agent Factory", items, on)


def team_nav(on, role, team="payments-factory", swarm=False, collab=False, orch=False):
    items = [
        ("grp", "Team"), ("overview", "Overview"), ("agents", "Agents"), ("members", "Members & access"),
        ("grp", "Configuration"), ("secrets", "Secrets"), ("config", "Configuration values"), ("identities", "Agent identities"),
        ("network", "External systems"), ("models", "Models"), ("logs", "Log delivery"),
        ("notify", "Notifications"),
        ("grp", "Cost"), ("budget", "Budget & usage"), ("reports", "Reports"), ("tags", "Cost tags"),
        ("grp", "History"), ("activity", "Activity & audit"), ("revisions", "Config revisions"),
    ]
    if role in ("ta", "sw"):
        items.insert(4, ("keys", "API keys"))
    if swarm:
        items.insert(3, ("pools", "Pools & stages"))
    if collab:
        items.insert(items.index(("agents", "Agents")) + 1, ("collab", "Collaboration"))
    if orch:
        items.insert(items.index(("agents", "Agents")), ("orch", "Orchestration"))
    switch = f'<div class="team-switch"><span><b>{team}</b></span><span class="muted">▾</span></div>'
    return nav("Agent Factory", items, on, switch)


def nav(title, items, on, extra=""):
    out = [f'<nav class="side"><h4>{title}</h4>{extra}']
    for key, label in items:
        if key == "grp":
            out.append(f'<div class="grp">{label}</div>')
        else:
            out.append(f'<a class="{"on" if key == on else ""}">{label}</a>')
    out.append('<hr><a class="dim">Documentation ↗</a><a class="dim">CLI reference ↗</a></nav>')
    return "".join(out)


def page(name, role, side, body, modal="", title="Agent Factory"):
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap">
<style>{CSS}</style></head><body>
<header class="top"><div class="brand"><div class="logo">AF</div>Agent Factory</div>
<div class="search">Search teams, agents, secrets, work orders  [Alt+S]</div><div class="sp"></div>
<span class="item">us-east-1 · prod</span><span class="item">🔔</span>{ROLE_PILL[role]}
<span class="item">{USER[role]} ▾</span></header>
<div class="shell">{side}<main class="main">{body}</main></div>{modal}</body></html>"""
    (OUT / f"{name}.html").write_text(doc)


def st(kind, text):
    return f'<span class="st {kind}">{text}</span>'


def tg(on, dis=False):
    return f'<span class="tg{" on" if on else ""}{" dis" if dis else ""}"></span>'


def bar(pct, cls=""):
    return f'<div class="bar {cls}"><i style="width:{min(pct,100)}%"></i></div>'


# ------------------------------------------------------------------------------------------------
# Service admin
# ------------------------------------------------------------------------------------------------

page("01-admin-dashboard", "admin", admin_nav("dash"), f"""
<div class="crumbs"><a>Agent Factory</a> › Dashboard</div>
<div class="hdr"><div><h1>Service dashboard <span class="info">Info</span></h1>
<div class="desc">Fleet health, spend and reconciliation across all teams in prod.</div></div>
<div class="btns"><span class="btn">Export showback CSV</span><span class="btn p">Create team</span></div></div>
<div class="alert warn"><span class="ic">⚠</span><div><b>Cost reconciliation variance on 1 team.</b> search-relevance: gateway estimate is 6.1% below billed Bedrock cost for 2026-11-18 (alert above 5%). <a>Review reconciliation</a> · 1 model price change from the AWS Price List is waiting for approval. <a>Review prices</a></div></div>
<div class="grid g4">
 <div class="card"><div class="ch"><h2>Teams</h2></div><div class="cb"><div class="big">42</div><div class="small muted">38 persistent · 4 ephemeral</div></div></div>
 <div class="card"><div class="ch"><h2>Agents running</h2></div><div class="cb"><div class="big">318</div><div class="small muted">of 341 desired · 6 paused</div></div></div>
 <div class="card"><div class="ch"><h2>Spend, Nov MTD</h2></div><div class="cb"><div class="big">$184,210</div><div class="small muted">of $402,000 budgeted (46%)</div></div></div>
 <div class="card"><div class="ch"><h2>Reconciler</h2></div><div class="cb"><div class="big g">{st('ok','Healthy')}</div><div class="small muted">Last full resync 3 min ago · 2 drift corrections today</div></div></div>
</div>
<div class="grid g2">
<div class="card"><div class="ch"><div><h2>Teams needing attention <span class="cnt">(5)</span></h2></div><a>View all teams</a></div>
<table><tr><th>Team</th><th>Issue</th><th>Since</th></tr>
<tr><td><a>search-relevance</a></td><td>{st('warn','Budget 92% used')}</td><td>2h</td></tr>
<tr><td><a>cve-2026-41873-swarm</a> <span class="badge b-eph">Ephemeral</span></td><td>{st('warn','Expires in 18h, 3 PRs open')}</td><td>—</td></tr>
<tr><td><a>claims-modernization</a></td><td>{st('err','Degraded: 2 agents CrashLoop')}</td><td>34m</td></tr>
<tr><td><a>mobile-platform</a></td><td>{st('err','Blocked: hard cap reached')}</td><td>1d</td></tr>
<tr><td><a>data-contracts</a></td><td>{st('inf','Drift reverted: NetworkPolicy edited')}</td><td>12m</td></tr>
</table></div>
<div class="card"><div class="ch"><div><h2>Top spend, Nov MTD</h2></div><a>Cost reconciliation</a></div>
<table><tr><th>Team</th><th>Cost center</th><th>Spend / budget</th><th></th></tr>
<tr><td><a>payments-factory</a></td><td>CC-4410</td><td>$31,880 / $40,000</td><td>{bar(80,'w')}</td></tr>
<tr><td><a>search-relevance</a></td><td>CC-2290</td><td>$22,970 / $25,000</td><td>{bar(92,'w')}</td></tr>
<tr><td><a>claims-modernization</a></td><td>CC-7001</td><td>$18,400 / $50,000</td><td>{bar(37)}</td></tr>
<tr><td><a>mobile-platform</a></td><td>CC-3120</td><td>$15,000 / $15,000</td><td>{bar(100,'r')}</td></tr>
<tr><td><a>identity-services</a></td><td>CC-4410</td><td>$9,120 / $20,000</td><td>{bar(46)}</td></tr>
</table></div></div>
""")

TEAM_ROWS = [
    ("payments-factory", "per", "ok", "Active", 12, 80, "$31,880 / $40,000", "CC-4410", "—"),
    ("search-relevance", "per", "ok", "Active", 9, 92, "$22,970 / $25,000", "CC-2290", "—"),
    ("claims-modernization", "per", "err", "Degraded", 14, 37, "$18,400 / $50,000", "CC-7001", "—"),
    ("cve-2026-41873-swarm", "eph", "ok", "Active", 6, 64, "$640 / $1,000", "CC-9000", "Nov 21, 14:00"),
    ("mobile-platform", "per", "warn", "Blocked (cap)", 7, 100, "$15,000 / $15,000", "CC-3120", "—"),
    ("poc-contract-summarizer", "eph", "ok", "Active", 3, 22, "$440 / $2,000", "CC-5150", "Dec 15, 00:00"),
    ("identity-services", "per", "pend", "Reconciling", 8, 46, "$9,120 / $20,000", "CC-4410", "—"),
    ("legacy-batch-retire", "per", "pend", "Suspended", 0, 0, "$0 / $5,000", "CC-7001", "—"),
]


def team_table(selected=None):
    rows = []
    for name, kind, sk, state, agents, pct, spend, cc, exp in TEAM_ROWS:
        badge = '<span class="badge b-eph">Ephemeral</span>' if kind == "eph" else '<span class="badge b-per">Persistent</span>'
        cls = "sel" if name == selected else ""
        rows.append(f'<tr class="{cls}"><td><span class="radio {"on" if cls else ""}"></span></td><td><a>{name}</a></td><td>{badge}</td>'
                    f'<td>{st(sk, state)}</td><td>{agents}</td><td>{spend}</td><td>{bar(pct, "r" if pct >= 100 else "w" if pct >= 80 else "")}</td><td>{cc}</td><td>{exp}</td></tr>')
    return "".join(rows)


page("02-admin-teams", "admin", admin_nav("teams"), f"""
<div class="crumbs"><a>Agent Factory</a> › Teams</div>
<div class="card"><div class="ch"><div><h2>Teams <span class="cnt">(42)</span> <span class="info">Info</span></h2>
<div class="sub">Each team is an isolated namespace with its own IAM role, inference profiles, secrets and budget.</div></div>
<div class="btns"><span class="btn">⟳</span><span class="btn">View details</span><span class="btn dd">Actions</span><span class="btn p">Create team</span></div></div>
<div class="tools"><div class="filter">🔍 Find teams by name, cost center or tag</div><span class="sel">Any kind ▾</span><span class="sel">Any state ▾</span>
<div class="pager">‹ <b>1</b> 2 3 4 5 › &nbsp; ⚙</div></div>
<table><tr><th></th><th>Name ▴</th><th>Kind</th><th>State</th><th>Agents</th><th>Spend / budget (Nov)</th><th></th><th>Cost center</th><th>Expires</th></tr>
{team_table("payments-factory")}</table></div>
""")

page("03-admin-create-team", "admin", admin_nav("teams"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Teams</a> › Create team</div>
<div class="wiz"><div class="steps">
<div class="on"><div class="n">Step 1</div><b>Team details</b></div>
<div class="todo"><div class="n">Step 2</div><b>Models & network</b></div>
<div class="todo"><div class="n">Step 3</div><b>Budget</b></div>
<div class="todo"><div class="n">Step 4</div><b>Members</b></div>
<div class="todo"><div class="n">Step 5</div><b>Review and create</b></div></div>
<div style="flex:1;max-width:820px">
<div class="hdr"><div><h1>Team details</h1></div></div>
<div class="card"><div class="ch"><h2>Lifecycle</h2></div><div class="cb">
<div class="tiles">
<div class="tile on"><b><span class="radio on"></span> Persistent team</b><span>Long-running development and maintenance team. Monthly budget. Runs until suspended or deleted.</span></div>
<div class="tile"><b><span class="radio"></span> Ephemeral (budgeted workload or POC)</b><span>Time-boxed swarm for one job. Lifetime hard cap and expiry; torn down automatically.</span></div>
</div></div></div>
<div class="card"><div class="ch"><h2>Identity</h2></div><div class="cb">
<div class="field"><label>Name</label><div class="hint">Lowercase, used for the namespace <span class="mono">afs-t-&lt;name&gt;</span>. Cannot be changed later.</div><div class="input" style="width:420px">payments-factory</div></div>
<div class="field"><label>Display name</label><div class="input" style="width:420px">Payments Software Factory</div></div>
<div class="field"><label>Description <span class="muted" style="font-weight:400">- optional</span></label><div class="input ph" style="height:56px">Agents maintaining the payments ledger services and their dependencies</div></div>
<div class="grid g2"><div class="field"><label>Cost center</label><div class="input">CC-4410</div></div>
<div class="field"><label>Owner email</label><div class="input">payments-eng-leads@corp.example</div></div></div>
<div class="field"><label>Sign-in provider</label><div class="hint">The service's providers. The team's people sign in through this one; team-admins can change it later.</div><div class="input" style="width:420px">Okta · corp.okta.example (service default) ▾</div></div>
</div></div>
<div class="card"><div class="ch"><div><h2>Cost allocation tags</h2><div class="sub">Required by the service. Every AWS resource and Bedrock call of this team carries these, plus <span class="mono">afs-team-id</span> and <span class="mono">afs-agent-id</span>.</div></div></div><div class="cb">
<div class="grid g3"><div class="field"><label>business-unit</label><div class="input">Payments ▾</div></div>
<div class="field"><label>product-line</label><div class="input">merchant-ledger</div></div>
<div class="field"><label>data-classification</label><div class="input">confidential ▾</div></div></div>
<div class="small muted">Fixed for every team: <span class="mono">environment = prod</span>, <span class="mono">managed-by = agent-factory</span>. The team can add its own tags after creation.</div>
</div></div>
<div class="card"><div class="ch"><h2>Guardrails <span class="muted small" style="font-weight:400">set by service admins</span></h2></div><div class="cb">
<div class="grid g3"><div class="field"><label>Budget ceiling (USD / month)</label><div class="hint">Team-admins can budget up to this.</div><div class="input">40,000</div></div>
<div class="field"><label>Compute quota</label><div class="hint">CPU / memory / pods</div><div class="input">32 vCPU · 128 GiB · 100</div></div>
<div class="field"><label>Isolation tier</label><div class="hint">Node pool for the namespace</div><div class="input">Shared (standard) ▾</div></div></div>
</div></div>
<div style="display:flex;justify-content:flex-end;gap:8px"><span class="btn" style="border:0">Cancel</span><span class="btn p">Next</span></div>
</div></div>
""")

page("04-admin-models", "admin", admin_nav("models"), f"""
<div class="crumbs"><a>Agent Factory</a> › Model catalog & pricing</div>
<div class="card"><div class="ch"><div><h2>Models <span class="cnt">(6)</span> <span class="info">Info</span></h2>
<div class="sub">Bedrock models teams may enable. Prices drive real-time spend reservation in the gateway; CUR reconciles daily.</div></div>
<div class="btns"><span class="btn">Sync prices from AWS Price List</span><span class="btn dd">Actions</span><span class="btn p">Add model</span></div></div>
<div class="tools"><div class="filter">🔍 Find models</div><div class="pager">‹ <b>1</b> › &nbsp; ⚙</div></div>
<table><tr><th></th><th>Model</th><th>Provider</th><th>Status</th><th>Input $/MTok</th><th>Output $/MTok</th><th>Teams using</th><th>Price effective</th></tr>
<tr><td><span class="cb2"></span></td><td class="mono">anthropic.claude-opus-…</td><td>Anthropic</td><td>{st('ok','Enabled')}</td><td>15.00</td><td>75.00</td><td>18</td><td>2026-10-01</td></tr>
<tr class="sel"><td><span class="cb2 on"></span></td><td class="mono">anthropic.claude-sonnet-…</td><td>Anthropic</td><td>{st('ok','Enabled')}</td><td>3.00</td><td>15.00</td><td>39</td><td>2026-10-01</td></tr>
<tr><td><span class="cb2"></span></td><td class="mono">anthropic.claude-haiku-…</td><td>Anthropic</td><td>{st('ok','Enabled')}</td><td>1.00</td><td>5.00</td><td>27</td><td>2026-10-01</td></tr>
<tr><td><span class="cb2"></span></td><td class="mono">amazon.nova-pro-…</td><td>Amazon</td><td>{st('ok','Enabled')}</td><td>0.80</td><td>3.20</td><td>6</td><td>2026-09-15</td></tr>
<tr><td><span class="cb2"></span></td><td class="mono">amazon.titan-embed-…</td><td>Amazon</td><td>{st('ok','Enabled')}</td><td>0.02</td><td>—</td><td>11</td><td>2026-09-15</td></tr>
<tr><td><span class="cb2"></span></td><td class="mono">meta.llama-…</td><td>Meta</td><td>{st('pend','Disabled')}</td><td>0.72</td><td>0.72</td><td>0</td><td>2026-08-01</td></tr>
</table></div>
<div class="card"><div class="ch"><div><h2>Price changes waiting for approval <span class="cnt">(1)</span></h2><div class="sub">Read daily from the AWS Price List. An approved price applies from its effective date, or from approval if that is later. Budgets reserve spend at the approved price.</div></div></div>
<table><tr><th>Model</th><th>Effective from</th><th>Input $/MTok</th><th>Output $/MTok</th><th>Cache read / write</th><th>Fetched</th><th>Decision</th></tr>
<tr><td class="mono">anthropic.claude-haiku-…</td><td>2026-12-01 00:00 UTC</td><td>1.00 → <b>0.80</b></td><td>5.00 → <b>4.00</b></td><td>0.08 / 1.00</td><td>Nov 21, 02:00</td><td><span class="btn sm">Reject</span> <span class="btn sm p">Approve</span></td></tr></table></div>
<div class="card"><div class="ch"><h2>anthropic.claude-sonnet-… · price history</h2><span class="btn sm">Add price</span></div>
<table><tr><th>Effective from</th><th>Input</th><th>Output</th><th>Cache read</th><th>Cache write</th><th>Source</th><th>Changed by</th></tr>
<tr><td>2026-10-01 00:00 UTC</td><td>3.00</td><td>15.00</td><td>0.30</td><td>3.75</td><td>aws_price_list</td><td>priya.raman (approved)</td></tr>
<tr><td>2026-06-01 00:00 UTC</td><td>3.00</td><td>15.00</td><td>0.30</td><td>3.75</td><td>manual</td><td>priya.raman</td></tr></table></div>
""")

page("05-admin-audit", "admin", admin_nav("audit"), f"""
<div class="crumbs"><a>Agent Factory</a> › Audit log</div>
<div class="card"><div class="ch"><div><h2>Audit events <span class="cnt">(1,000+)</span> <span class="info">Info</span></h2>
<div class="sub">Append-only. Every API call that changes state, every denied call and every drift correction.</div></div>
<div class="btns"><span class="btn">Download CSV</span></div></div>
<div class="tools"><div class="filter">🔍 Filter: team = payments-factory, outcome = any</div><span class="sel">Last 24 hours ▾</span><div class="pager">‹ <b>1</b> 2 3 … › ⚙</div></div>
<table><tr><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Outcome</th><th>Resource</th><th>Team</th><th>Request ID</th></tr>
<tr><td>18:42:07</td><td>marcus.chen</td><td>PutBudget</td><td>{st('ok','Allowed')}</td><td>budget</td><td>payments-factory</td><td class="mono">req_01JD…8KX</td></tr>
<tr><td>18:40:51</td><td>dana.ortiz</td><td>CreateSecret</td><td>{st('err','Denied')}</td><td>secret github-bot-key</td><td>payments-factory</td><td class="mono">req_01JD…7Q2</td></tr>
<tr><td>18:31:12</td><td>system:reconciler</td><td>DriftCorrected</td><td>{st('ok','Allowed')}</td><td>NetworkPolicy default-deny</td><td>data-contracts</td><td class="mono">rec_01JD…3MN</td></tr>
<tr><td>18:12:44</td><td>key:ci-deployer</td><td>UpdateAgent</td><td>{st('ok','Allowed')}</td><td>agent reviewer-bot</td><td>payments-factory</td><td class="mono">req_01JD…1BZ</td></tr>
<tr><td>17:58:03</td><td>priya.raman</td><td>SetBudgetCeiling</td><td>{st('ok','Allowed')}</td><td>team</td><td>search-relevance</td><td class="mono">req_01JD…0AC</td></tr>
<tr><td>17:44:19</td><td>system:gateway</td><td>BudgetBlocked</td><td>{st('warn','Blocked')}</td><td>budget</td><td>mobile-platform</td><td class="mono">gw_01JD…ZZ1</td></tr>
</table></div>
""")

# ------------------------------------------------------------------------------------------------
# Team-admin
# ------------------------------------------------------------------------------------------------


def team_overview(role):
    ro = role == "tv"
    edit = '<span class="btn dis">Edit</span>' if ro else '<span class="btn">Edit</span>'
    susp = '<span class="btn dis dd">Actions</span>' if ro else '<span class="btn dd">Actions</span>'
    create = '<span class="btn p dis">Create agent</span>' if ro else '<span class="btn p">Create agent</span>'
    tip = '<span class="tip"><span class="tipbox">Requires team-admin</span></span>' if ro else ""
    banner = ('<div class="alert"><span class="ic">ⓘ</span><div><b>You have read-only access to this team.</b> '
              'Team viewers can see configuration, status, usage and audit history. Secret values are never shown. '
              'Ask a team-admin (Marcus Chen) for changes.</div></div>') if ro else ""
    return f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Teams</a> › payments-factory</div>
{banner}
<div class="hdr"><div><h1>payments-factory <span class="badge b-per">Persistent</span> <span class="info">Info</span></h1>
<div class="desc">Payments Software Factory · Agents maintaining the payments ledger services</div></div>
<div class="btns">{edit}{susp}{create}{tip}</div></div>
<div class="card"><div class="ch"><h2>Summary</h2></div><div class="cb"><div class="grid g4">
<div class="kv"><div class="k">State</div><div class="v">{st('ok','Active')}</div><div class="k">Reconcile status</div><div class="v">{st('ok','Ready')} · gen 37 / 37</div></div>
<div class="kv"><div class="k">Namespace</div><div class="v mono">afs-t-payments-factory</div><div class="k">Cluster</div><div class="v">prod-use1-a</div></div>
<div class="kv"><div class="k">Team IAM role</div><div class="v mono small">arn:aws:iam::…:role/afs-team-payments</div><div class="k">Cost center</div><div class="v">CC-4410</div></div>
<div class="kv"><div class="k">Owner</div><div class="v">payments-eng-leads@corp.example</div><div class="k">Created</div><div class="v">2026-09-02 by priya.raman</div></div>
</div></div></div>
<div class="grid g3">
<div class="card"><div class="ch"><h2>Budget, November</h2><a>Budget & usage</a></div><div class="cb">
<div class="big">$31,880</div><div class="small muted" style="margin-bottom:8px">of $40,000 monthly · hard cap, block at 100%</div>{bar(80,'w')}
<div class="small muted" style="margin-top:8px">Alerts at 50% ✓ · 80% ✓ (today 09:12) · 100%</div></div></div>
<div class="card"><div class="ch"><h2>Agents</h2><a>View agents</a></div><div class="cb">
<div class="grid g2"><div class="kv"><div class="k">Running</div><div class="big g">11</div></div><div class="kv"><div class="k">Desired</div><div class="big g">12</div></div></div>
<div class="small">{st('warn','1 agent restarting')} · release-notes-bot</div></div></div>
<div class="card"><div class="ch"><h2>Recent activity</h2><a>Activity & audit</a></div><div class="cb small">
<div style="margin-bottom:8px"><b>marcus.chen</b> changed the budget to $40,000 <span class="muted">· 3h</span></div>
<div style="margin-bottom:8px"><b>system:reconciler</b> rotated secret github-bot-key into 3 agents <span class="muted">· 6h</span></div>
<div><b>key:ci-deployer</b> updated agent reviewer-bot image <span class="muted">· 6h</span></div></div></div>
</div>
<div class="card"><div class="ch"><h2>Conditions</h2></div>
<table><tr><th>Type</th><th>Status</th><th>Last transition</th><th>Message</th></tr>
<tr><td>NamespaceReady</td><td>{st('ok','True')}</td><td>2026-09-02</td><td>Namespace, quota and PSA restricted applied</td></tr>
<tr><td>NetworkIsolated</td><td>{st('ok','True')}</td><td>2026-11-20 18:31</td><td>Default-deny + 4 egress rules; drift reverted 0 times today</td></tr>
<tr><td>IdentityReady</td><td>{st('ok','True')}</td><td>2026-09-02</td><td>IAM role and 7 Pod Identity associations</td></tr>
<tr><td>SecretsSynced</td><td>{st('ok','True')}</td><td>2026-11-20 12:40</td><td>7 of 7 ExternalSecrets synced</td></tr>
<tr><td>InferenceProfilesReady</td><td>{st('ok','True')}</td><td>2026-10-01</td><td>3 application inference profiles tagged afs-team-id</td></tr>
</table></div>
"""


page("06-ta-team-overview", "ta", team_nav("overview", "ta"), team_overview("ta"))

AGENTS = [
    ("ledger-maintainer", "Running", "ok", "2 / 2", "claude-sonnet", "hermes-dev", "4 secrets", "$9,410"),
    ("dependency-updater", "Running", "ok", "3 / 3", "claude-haiku", "hermes-dev", "2 secrets", "$2,120"),
    ("reviewer-bot", "Running", "ok", "2 / 2", "claude-opus", "omp-review", "2 secrets", "$12,980"),
    ("release-notes-bot", "Restarting", "warn", "0 / 1", "claude-haiku", "opencode", "1 secret", "$310"),
    ("test-gap-finder", "Running", "ok", "2 / 2", "claude-sonnet", "hermes-dev", "2 secrets", "$5,760"),
    ("incident-scribe", "Paused", "pend", "0 / 0", "claude-sonnet", "hermes-ops", "3 secrets", "$1,300"),
    ("api-doc-writer", "Running", "ok", "2 / 2", "claude-sonnet", "opencode", "1 secret", "$0"),
]


def agent_rows(selected=None, selectable=True):
    out = []
    for name, state, sk, rep, model, tmpl, secs, cost in AGENTS:
        cls = "sel" if name == selected else ""
        box = f'<span class="cb2 {"on" if cls else ""}"></span>' if selectable else ""
        out.append(f'<tr class="{cls}"><td>{box}</td><td><a>{name}</a></td><td>{st(sk, state)}</td><td class="mono small">{name + "-0" if state != "Paused" else "— (paused)"}</td><td class="mono">{model}</td><td>{tmpl}</td><td>{secs}</td><td>{cost}</td></tr>')
    return "".join(out)


page("07-ta-agents", "ta", team_nav("agents", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Agents</div>
<div class="card"><div class="ch"><div><h2>Agents <span class="cnt">(7)</span> <span class="info">Info</span></h2>
<div class="sub">Containerized agents in namespace afs-t-payments-factory. Model calls go through the metering gateway.</div></div>
<div class="btns"><span class="btn">⟳</span><span class="btn">View details</span><span class="btn dd">Actions</span><span class="btn p">Create agent</span></div></div>
<div class="tools"><div class="filter">🔍 Find agents</div><span class="sel">Any state ▾</span><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Name</th><th>Status</th><th>Pod</th><th>Model</th><th>Template</th><th>Secrets</th><th>Cost, Nov MTD</th></tr>
{agent_rows("reviewer-bot")}</table></div>
<div class="card" style="position:relative"><div class="ch"><h2>reviewer-bot</h2><div class="btns"><span class="btn sm">Restart</span><span class="btn sm">Pause</span><span class="btn sm">Take snapshot</span><span class="btn sm">Edit</span></div></div>
<div class="tabs" style="margin:0 20px 14px"><span class="on">Details</span><span>Configuration</span><span>Secrets & identity</span><span>Usage</span><span>Logs</span><span>Revisions</span></div>
<div class="cb"><div class="grid g4">
<div class="kv"><div class="k">Image</div><div class="v mono small">ghcr.io/…/omp-review@sha256:9f2c…e1</div></div>
<div class="kv"><div class="k">Service account</div><div class="v mono">agent-reviewer-bot</div></div>
<div class="kv"><div class="k">Resources</div><div class="v">2 vCPU · 8 GiB · one pod</div></div>
<div class="kv"><div class="k">Last change</div><div class="v">6h ago by key:ci-deployer</div></div></div>
<div class="grid g4" style="margin-top:14px">
<div class="kv"><div class="k">Persistent volume</div><div class="v">50 GiB gp3 · 31% used <a class="small">Expand</a></div></div>
<div class="kv"><div class="k">Mounted at</div><div class="v mono">/var/lib/agent</div></div>
<div class="kv"><div class="k">Snapshots</div><div class="v">Daily, keep 7 · last today 03:00 {st('ok','Completed')}</div></div>
<div class="kv"><div class="k">On delete</div><div class="v">Snapshot, then delete volume</div></div></div></div></div>
""")

page("08-ta-create-agent", "ta", team_nav("agents", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › <a>Agents</a> › Create agent</div>
<div class="hdr"><div><h1>Create agent</h1><div class="desc">Defines desired state. The reconciler creates the service account, Pod Identity association, secrets and workload.</div></div></div>
<div class="split"><div style="flex:1;max-width:860px">
<div class="card"><div class="ch"><h2>Agent</h2></div><div class="cb">
<div class="grid g2"><div class="field"><label>Name</label><div class="input">security-patcher</div></div>
<div class="field"><label>Template</label><div class="hint">From the Agentic Teammates runtime catalog</div><div class="input">hermes-dev (v2.4) ▾</div></div></div>
<div class="field"><label>Image</label><div class="hint">Pinned by digest. Tags are not accepted.</div><div class="input mono">ghcr.io/stainedhead/hermes-dev@sha256:4b1e…77</div></div>
<div class="field"><label>Persona and instructions</label><div class="input" style="height:60px">Keeps payments services free of known-vulnerable dependencies; opens PRs, never merges.</div></div>
</div></div>
<div class="card"><div class="ch"><h2>Model and resources</h2></div><div class="cb"><div class="grid g2">
<div class="field"><label>Model</label><div class="hint">Enabled for this team</div><div class="input">claude-sonnet ▾</div></div>
<div class="field"><label>Resources</label><div class="hint">One pod per agent. Add agents to add capacity.</div><div class="input">2 vCPU · 8 GiB ▾</div></div></div></div></div>
<div class="card"><div class="ch"><div><h2>Persistent storage</h2><div class="sub">One volume for this agent's memory, configuration and work in progress, mounted at <span class="mono">/var/lib/agent</span>. It survives restarts, pauses, upgrades and reschedules.</div></div></div><div class="cb"><div class="grid g2">
<div class="field"><label>Size (GiB)</label><div class="hint">1 to 1000. Can be expanded later, never shrunk.</div><div class="input">20</div></div>
<div class="field"><label>Storage class</label><div class="hint">Offered by your service admins. Fixed after creation.</div><div class="input">gp3 · general purpose SSD, encrypted ▾</div></div>
<div class="field"><label>When the agent is deleted</label><div class="input">Take a final snapshot, then delete the volume ▾</div></div>
<div class="field"><label>Snapshot backups</label><div class="input">Daily, keep 7 ▾</div></div></div></div></div>
<div class="card"><div class="ch"><div><h2>AWS identity</h2><div class="sub">A dedicated role gives this agent its own IAM identity, and is required for roles in other accounts. Add cross-account roles after the agent is created.</div></div></div><div class="cb"><div class="grid g2">
<div class="field"><label>IAM identity</label><div class="input">Dedicated role for this agent ▾</div></div>
<div class="field"><label>Role name</label><div class="hint">Set by Agent Factory</div><div class="input ro mono small">afs/agents/afs-t-payments-factory/security-patcher</div></div></div></div></div>
<div class="card"><div class="ch"><div><h2>Configuration values</h2><div class="sub">Non-secret settings, delivered as environment variables and as files under <span class="mono">/etc/afs/config</span>. Use the namespace value to share one setting across the team's agents. Secrets belong under Secrets.</div></div><span class="btn sm">Add value</span></div>
<table><tr><th>Name</th><th>Source</th><th>Value</th><th></th></tr>
<tr><td class="mono">LOG_LEVEL</td><td><div class="input" style="margin:0">Use namespace value ▾</div></td><td><span class="mono">info</span> <span class="muted small">from namespace</span></td><td><a>Remove</a></td></tr>
<tr><td class="mono">GITHUB_ORG</td><td><div class="input" style="margin:0">Use namespace value ▾</div></td><td><span class="mono">acme-payments</span> <span class="muted small">from namespace</span></td><td><a>Remove</a></td></tr>
<tr><td class="mono">MAX_OPEN_PRS</td><td><div class="input" style="margin:0">Agent value ▾</div></td><td><div class="input mono" style="margin:0">3</div></td><td><a>Remove</a></td></tr></table></div>
<div class="card"><div class="ch"><div><h2>Secrets</h2><div class="sub">Team-shared secrets can be bound now. Secrets only this agent can read are added after it is created, under Secrets.</div></div><span class="btn sm">Add secret binding</span></div>
<table><tr><th>Secret</th><th>Scope</th><th>Delivery</th><th>Target</th><th></th></tr>
<tr><td>github-bot-key</td><td><span class="badge b-per" style="white-space:nowrap">Team shared</span></td><td>Environment variable</td><td class="mono">GITHUB_APP_KEY</td><td><a>Remove</a></td></tr>
<tr><td>artifactory-reader</td><td><span class="badge b-per" style="white-space:nowrap">Team shared</span></td><td>File</td><td class="mono">/var/run/secrets/artifactory/token</td><td><a>Remove</a></td></tr></table></div>
<div style="display:flex;justify-content:flex-end;gap:8px"><span class="btn" style="border:0">Cancel</span><span class="btn">Preview CLI command</span><span class="btn p">Create agent</span></div>
</div>
<div style="width:360px"><div class="card"><div class="ch"><h2>Equivalent CLI</h2></div><div class="cb">
<div class="code">afs agents create-agent \\<br>&nbsp; --team-id team_01JD3Z… \\<br>&nbsp; --name security-patcher \\<br>&nbsp; --template hermes-dev \\<br>&nbsp; --model-id claude-sonnet \\<br>&nbsp; --storage SizeGiB=20,StorageClass=gp3,\\<br>&nbsp;&nbsp;&nbsp; OnDelete=snapshot_then_delete,\\<br>&nbsp;&nbsp;&nbsp; Snapshots=daily,Keep=7 \\<br>&nbsp; --iam-identity dedicated \\<br>&nbsp; --config-values file://config.json \\<br>&nbsp; --secret-bindings file://bindings.json</div>
<div class="small muted" style="margin-top:8px">Every console action maps to one CLI operation and one REST call.</div></div></div></div>
</div>
""")

SECRETS = [
    ("github-bot-key", "_shared", "GitHub App private key for PRs", "3 agents", "Every 90 days", "Nov 20, 12:40"),
    ("artifactory-reader", "_shared", "Read-only package mirror", "5 agents", "Every 90 days", "Oct 28"),
    ("splunk-hec-token", "_shared", "Log delivery to Splunk", "Log delivery", "—", "Sep 02"),
    ("snyk-token", "dependency-updater", "Snyk API token", "dependency-updater", "—", "Oct 02"),
    ("jira-bot-api-key", "incident-scribe", "Jira automation user", "incident-scribe", "Every 30 days", "Nov 11"),
]
NS = "afs-t-payments-factory"


def scope_badge(scope):
    if scope == "_shared":
        return '<span class="badge b-per" style="white-space:nowrap">Team shared</span>'
    return f'<span class="badge b-blue" style="white-space:nowrap">Agent: {scope}</span>'


def secret_rows(selectable=True):
    out = []
    for n, scope, d, used, rot, chg in SECRETS:
        box = '<span class="cb2"></span>' if selectable else ""
        out.append(f'<tr><td>{box}</td><td><a>{n}</a></td><td>{scope_badge(scope)}</td><td>{d}</td>'
                   f'<td class="mono small">afs/{NS}/{scope}/{n}</td><td>{used}</td><td>{rot}</td><td>{chg}</td><td class="muted small">Write-only</td></tr>')
    return "".join(out)


secret_modal = """<div class="modalwrap"><div class="modal"><div class="mh">Create secret<span class="muted">✕</span></div><div class="mb">
<div class="field"><label>Scope</label><div class="hint">Team shared: any agent in this team can be bound to it. Agent: only that agent can read it.</div><div class="input">Agent: incident-scribe ▾</div></div>
<div class="field"><label>Name</label><div class="input">pagerduty-token</div></div>
<div class="field"><label>Description</label><div class="input">PagerDuty Events API token for incident-scribe</div></div>
<div class="field"><label>Secret value</label><div class="hint">Sent once, straight to AWS Secrets Manager. Agent Factory stores only the reference and cannot show it again.</div>
<div class="input mono">••••••••••••••••••••••••••••••••</div></div>
<div class="grid g2"><div class="field"><label>Rotation reminder</label><div class="input">Every 90 days ▾</div></div>
<div class="field"><label>Secrets Manager path</label><div class="hint">Set by Agent Factory. Cannot be changed.</div><div class="input ro mono small">afs/afs-t-payments-factory/incident-scribe/pagerduty-token</div></div></div>
<div class="alert" style="margin:4px 0 0"><span class="ic">ⓘ</span><div class="small">The path follows <span class="mono">service / namespace / agent / name</span>, so access rules are prefix rules. Only incident-scribe and this team's secret store can read it. Encrypted with the environment KMS key and tagged <span class="mono">afs-team-id</span>.</div></div>
</div><div class="mf"><span class="btn" style="border:0">Cancel</span><span class="btn p">Create secret</span></div></div></div>"""

page("09-ta-secrets", "ta", team_nav("secrets", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Secrets</div>
<div class="card"><div class="ch"><div><h2>Secrets <span class="cnt">(5)</span> <span class="info">Info</span></h2>
<div class="sub">Stored in AWS Secrets Manager under paths Agent Factory manages. Values are write-only and never stored in or shown by Agent Factory.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Create secret</span></div></div>
<div class="tools"><div class="filter">🔍 Find secrets</div><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Name</th><th>Scope</th><th>Description</th><th>Secrets Manager path</th><th>Used by</th><th>Rotation</th><th>Last changed</th><th>Value</th></tr>
{secret_rows()}</table></div>
""", modal=secret_modal)


def chart(cap=True):
    vals = [(1.1, .0), (1.3, 0), (1.2, 0), (1.6, 0), (1.5, 0), (0.6, 0), (0.5, 0), (1.7, 0), (1.9, 0), (1.8, 0), (2.0, 0),
            (1.9, 0), (0.7, 0), (0.6, 0), (2.1, 0), (2.2, 0), (2.4, 0), (2.3, 0), (2.5, 0), (2.4, 0)]
    cols = []
    for g, _ in vals:
        h = int(g * 55)
        cols.append(f'<div class="c"><i style="height:{h}px"></i><i class="b" style="height:{int(h*0.05)+2}px"></i></div>')
    capline = '<div class="cap" style="bottom:148px"><span>Daily run-rate to cap: $1,333</span></div>' if cap else ""
    return f'<div class="chart">{capline}{"".join(cols)}</div><div class="legend"><span><i style="background:#688ae8"></i>Bedrock tokens (gateway, real time)</span><span><i style="background:#c33d69"></i>EKS compute (CUR, daily)</span><span>Nov 1 → Nov 20</span></div>'


page("10-ta-budget", "ta", team_nav("budget", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Budget & usage</div>
<div class="hdr"><div><h1>Budget & usage <span class="info">Info</span></h1><div class="desc">Spend is reserved per model call by the gateway and stopped at the hard cap. CUR reconciles billed cost daily.</div></div>
<div class="btns"><span class="btn">Download CSV</span><span class="btn p">Edit budget</span></div></div>
<div class="grid g4">
<div class="card"><div class="ch"><h2>Month to date</h2></div><div class="cb"><div class="big">$31,880</div>{bar(80,'w')}<div class="small muted" style="margin-top:6px">80% of $40,000 · ceiling $40,000</div></div></div>
<div class="card"><div class="ch"><h2>Forecast, month end</h2></div><div class="cb"><div class="big">$44,600</div><div class="small warn">Projected to hit cap on Nov 27</div></div></div>
<div class="card"><div class="ch"><h2>On exhaust</h2></div><div class="cb"><div class="big g" style="font-size:20px;font-weight:600">Block calls</div><div class="small muted">Gateway rejects; IAM deny applied as backstop</div></div></div>
<div class="card"><div class="ch"><h2>Reconciled (Nov 19)</h2></div><div class="cb"><div class="big g" style="font-size:20px;font-weight:600">{st('ok','Within 0.8%')}</div><div class="small muted">Gateway $1,702 · billed $1,716</div></div></div>
</div>
<div class="card"><div class="ch"><h2>Daily spend</h2><span class="sel">Group by: source ▾</span></div><div class="cb">{chart()}</div></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>By agent</h2></div><table><tr><th>Agent</th><th>Input tok</th><th>Output tok</th><th>Cost</th></tr>
<tr><td>reviewer-bot</td><td>410 M</td><td>91 M</td><td>$12,980</td></tr><tr><td>ledger-maintainer</td><td>1.2 B</td><td>388 M</td><td>$9,410</td></tr><tr><td>test-gap-finder</td><td>720 M</td><td>240 M</td><td>$5,760</td></tr><tr><td>dependency-updater</td><td>1.1 B</td><td>200 M</td><td>$2,120</td></tr></table></div>
<div class="card"><div class="ch"><h2>Budget settings</h2></div><div class="cb"><div class="grid g2">
<div class="kv"><div class="k">Period</div><div class="v">Monthly, resets on the 1st (UTC)</div><div class="k">Amount</div><div class="v">$40,000</div></div>
<div class="kv"><div class="k">Alert thresholds</div><div class="v">50% · 80% · 100%</div><div class="k">Alerts go to</div><div class="v">#payments-factory (Slack), owner email</div></div></div></div></div>
</div>
""")

page("11-ta-members", "ta", team_nav("members", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Members & access</div>
<div class="tabs"><span class="on">People and groups</span><span>API keys</span></div>
<div class="card"><div class="ch"><div><h2>Role bindings <span class="cnt">(6)</span> <span class="info">Info</span></h2>
<div class="sub">Grant team-admin or team viewer to people or to IdP groups. Group membership is managed in the enterprise IdP.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Add members</span></div></div>
<div class="tools"><div class="filter">🔍 Find members</div><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Subject</th><th>Type</th><th>Role</th><th>Granted by</th><th>Granted</th><th>Last sign-in</th></tr>
<tr><td><span class="cb2"></span></td><td>Marcus Chen <span class="muted small">marcus.chen@corp.example</span></td><td>User</td><td><span class="badge b-blue">team-admin</span></td><td>priya.raman</td><td>2026-09-02</td><td>Today</td></tr>
<tr><td><span class="cb2"></span></td><td><span class="mono">grp-payments-eng-leads</span></td><td>IdP group · 4 people</td><td><span class="badge b-blue">team-admin</span></td><td>priya.raman</td><td>2026-09-02</td><td>—</td></tr>
<tr><td><span class="cb2"></span></td><td><span class="mono">grp-payments-engineering</span></td><td>IdP group · 38 people</td><td><span class="badge b-per">team viewer</span></td><td>marcus.chen</td><td>2026-09-03</td><td>—</td></tr>
<tr><td><span class="cb2"></span></td><td>Dana Ortiz <span class="muted small">dana.ortiz@corp.example</span></td><td>User</td><td><span class="badge b-per">team viewer</span></td><td>marcus.chen</td><td>2026-10-14</td><td>Today</td></tr>
<tr><td><span class="cb2"></span></td><td>Sam Patel <span class="muted small">finops</span></td><td>User</td><td><span class="badge b-per">team viewer</span></td><td>marcus.chen</td><td>2026-11-01</td><td>Nov 18</td></tr>
<tr><td><span class="cb2"></span></td><td><span class="mono">grp-platform-sre</span></td><td>IdP group · 9 people</td><td><span class="badge b-per">team viewer</span></td><td>priya.raman</td><td>2026-09-02</td><td>—</td></tr>
</table></div>
<div class="alert"><span class="ic">ⓘ</span><div class="small">Team-admins can grant team roles on this team only. Service-admin access is granted centrally by the platform team.</div></div>
""")

# ------------------------------------------------------------------------------------------------
# Team viewer
# ------------------------------------------------------------------------------------------------

NSCONF = [
    ("LOG_LEVEL", "info", "Default log level for agents", "5 agents", "Nov 02"),
    ("GITHUB_ORG", "acme-payments", "GitHub organization the team's repos live in", "6 agents", "Sep 02"),
    ("JIRA_PROJECT", "PAY", "Jira project for agent-created tickets", "3 agents", "Sep 14"),
    ("MAX_OPEN_PRS", "5", "Cap on open PRs per agent", "2 agents", "Nov 18"),
]

page("16-ta-config-values", "ta", team_nav("config", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Configuration values</div>
<div class="card"><div class="ch"><div><h2>Namespace values <span class="cnt">(4)</span> <span class="info">Info</span></h2>
<div class="sub">Non-secret settings shared by agents in namespace afs-t-payments-factory. An agent uses one by choosing <i>Use namespace value</i> for the same name. Changing a value restarts the agents that use it.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Add value</span></div></div>
<div class="tools"><div class="filter">🔍 Find values</div><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Name</th><th>Value</th><th>Description</th><th>Used by</th><th>Last changed</th></tr>
{"".join(f'<tr><td><span class="cb2"></span></td><td class="mono">{n}</td><td class="mono">{v}</td><td>{d}</td><td><a>{u}</a></td><td>{c}</td></tr>' for n, v, d, u, c in NSCONF)}
</table></div>
<div class="card"><div class="ch"><div><h2>Agent values <span class="cnt">(6)</span></h2>
<div class="sub">What each agent receives and where it comes from. Edit an agent to change its values.</div></div></div>
<table><tr><th>Agent</th><th>Name</th><th>Source</th><th>Effective value</th></tr>
<tr><td><a>reviewer-bot</a></td><td class="mono">LOG_LEVEL</td><td><span class="badge b-per" style="white-space:nowrap">Namespace</span></td><td class="mono">info</td></tr>
<tr><td><a>reviewer-bot</a></td><td class="mono">GITHUB_ORG</td><td><span class="badge b-per" style="white-space:nowrap">Namespace</span></td><td class="mono">acme-payments</td></tr>
<tr><td><a>dependency-updater</a></td><td class="mono">LOG_LEVEL</td><td><span class="badge b-blue" style="white-space:nowrap">Agent value</span></td><td class="mono">debug</td></tr>
<tr><td><a>dependency-updater</a></td><td class="mono">MAX_OPEN_PRS</td><td><span class="badge b-per" style="white-space:nowrap">Namespace</span></td><td class="mono">5</td></tr>
<tr><td><a>incident-scribe</a></td><td class="mono">JIRA_PROJECT</td><td><span class="badge b-per" style="white-space:nowrap">Namespace</span></td><td class="mono">PAY</td></tr>
<tr><td><a>incident-scribe</a></td><td class="mono">PAGER_SERVICE</td><td><span class="badge b-blue" style="white-space:nowrap">Agent value</span></td><td class="mono">payments-core</td></tr>
</table></div>
""")

aws_modal = """<div class="modalwrap"><div class="modal" style="width:720px"><div class="mh">Add cross-account role<span class="muted">✕</span></div><div class="mb">
<div class="grid g2"><div class="field"><label>Account</label><div class="hint">Organization accounts inside this team's allowed-accounts filter</div><div class="input">payments-prod · 444455556666 ▾</div></div>
<div class="field"><label>Profile name</label><div class="hint">The agent uses <span class="mono">--profile</span> with this name</div><div class="input mono">prod-deployer</div></div></div>
<div class="grid g2"><div class="field"><label>Role ARN in that account</label><div class="input mono small">arn:aws:iam::444455556666:role/afs/payments-deployer</div></div>
<div class="field"><label>Maximum session</label><div class="input">1 hour ▾</div></div></div>
<div class="field"><label>Trust policy for the target role</label><div class="hint">The owner of account 444455556666 adds this to the role. Agent Factory checks the link by assuming the role, and shows <i>Verified</i> once it works.</div>
<div class="code" style="font-size:11.5px;line-height:1.45">{<br>&nbsp; "Effect": "Allow",<br>&nbsp; "Principal": { "AWS": "arn:aws:iam::111122223333:role/afs/agents/afs-t-payments-factory/reviewer-bot" },<br>&nbsp; "Action": [ "sts:AssumeRole", "sts:TagSession" ],<br>&nbsp; "Condition": {<br>&nbsp;&nbsp;&nbsp; "StringEquals": { "sts:ExternalId": "afs-7Hq2Lx9TzR4mWc8VbN3k",<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; "aws:PrincipalTag/afs-team-id": "team_01JD3Z…" }<br>&nbsp; }<br>}</div>
<div style="margin-top:8px"><span class="btn sm">Copy policy</span></div></div>
</div><div class="mf"><span class="btn" style="border:0">Cancel</span><span class="btn p">Add role</span></div></div></div>"""

page("17-ta-agent-aws-access", "ta", team_nav("agents", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › <a>Agents</a> › reviewer-bot</div>
<div class="hdr"><div><h1>reviewer-bot</h1><div class="desc">{st('ok','Running')} · claude-opus · omp-review</div></div><div class="btns"><span class="btn">Restart</span><span class="btn">Pause</span><span class="btn p">Edit</span></div></div>
<div class="tabs"><span>Details</span><span>Configuration</span><span class="on">Secrets & identity</span><span>Usage</span><span>Logs</span><span>Revisions</span></div>
<div class="card"><div class="ch"><div><h2>AWS identity <span class="info">Info</span></h2><div class="sub">Who this agent is in AWS. Calls carry session tags <span class="mono">afs-team-id</span> and <span class="mono">afs-agent-id</span>, so CloudTrail shows the agent.</div></div></div><div class="cb"><div class="grid g3">
<div class="kv"><div class="k">IAM identity</div><div class="v">Dedicated role for this agent</div></div>
<div class="kv"><div class="k">Role</div><div class="v mono small">arn:aws:iam::111122223333:role/afs/agents/afs-t-payments-factory/reviewer-bot</div></div>
<div class="kv"><div class="k">Pod Identity association</div><div class="v">{st('ok','Active')}</div></div>
<div class="kv"><div class="k">Accounts this team may use</div><div class="v"><span class="mono">payments-*</span>, <span class="mono">777788889999</span> <span class="muted small">· set by service admins</span></div></div></div></div></div>
<div class="card"><div class="ch"><div><h2>Cross-account roles <span class="cnt">(3)</span></h2><div class="sub">Roles in other organization accounts this agent may assume. They appear as AWS profiles in the agent's config file.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn">Verify now</span><span class="btn p">Add cross-account role</span></div></div>
<table><tr><th></th><th>Profile</th><th>Account</th><th>Role ARN</th><th>Status</th><th>Last verified</th><th></th></tr>
<tr><td><span class="cb2"></span></td><td class="mono">prod-reader</td><td>payments-prod<br><span class="muted small mono">444455556666</span></td><td class="mono small">arn:aws:iam::444455556666:role/afs/payments-reader</td><td>{st('ok','Verified')}</td><td>Today 06:00</td><td><a>Trust policy</a></td></tr>
<tr><td><span class="cb2"></span></td><td class="mono">shared-tools</td><td>shared-tools<br><span class="muted small mono">777788889999</span></td><td class="mono small">arn:aws:iam::777788889999:role/afs/artifact-reader</td><td>{st('ok','Verified')}</td><td>Today 06:00</td><td><a>Trust policy</a></td></tr>
<tr><td><span class="cb2"></span></td><td class="mono">prod-deployer</td><td>payments-prod<br><span class="muted small mono">444455556666</span></td><td class="mono small">arn:aws:iam::444455556666:role/afs/payments-deployer</td><td>{st('pend','Pending trust')}</td><td>—</td><td><a>Trust policy</a></td></tr>
</table></div>
""", modal=aws_modal)

page("18-admin-team-aws-accounts", "admin", admin_nav("teams"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Teams</a> › <a>payments-factory</a> › AWS account access</div>
<div class="hdr"><div><h1>payments-factory</h1><div class="desc">{st('ok','Active')} · namespace afs-t-payments-factory</div></div><div class="btns"><span class="btn">Suspend</span><span class="btn p">Edit</span></div></div>
<div class="tabs"><span>Details</span><span>Members</span><span>Budget</span><span class="on">AWS account access</span><span>Audit</span></div>
<div class="card"><div class="ch"><div><h2>Allowed accounts <span class="info">Info</span></h2>
<div class="sub">Organization accounts this team's agents may assume roles in. Patterns match account ids or names; <span class="mono">*</span> and <span class="mono">?</span> are wildcards, and <span class="mono">*</span> alone means every account. Team-admins see this list, and can change it only if the team manages its own accounts.</div></div>
<div class="btns"><span class="btn p">Save changes</span></div></div><div class="cb">
<div class="field"><label>Who manages this list</label><div style="display:flex;gap:10px;align-items:center">{tg(False)} <span>Team manages its own accounts</span><span class="muted small">Off: only service admins change the list. On: this team's admins can change it too.</span></div></div>
<div class="field"><label>Patterns</label><div class="hint">One per line. Up to 50.</div>
<div class="input mono" style="height:auto;line-height:1.7">payments-*<br>777788889999</div></div>
<div class="alert"><span class="ic">ⓘ</span><div class="small">Enforced three times: the API refuses links outside the filter, the database rejects them, and the team's IAM permissions boundary only allows <span class="mono">sts:AssumeRole</span> into matching accounts. Narrowing the filter disables links that fall outside it.</div></div>
</div></div>
<div class="card"><div class="ch"><div><h2>Matching organization accounts <span class="cnt">(3)</span></h2>
<div class="sub">From AWS Organizations, refreshed hourly. Suspended accounts never match.</div></div></div>
<table><tr><th>Account</th><th>Name</th><th>Matched by</th><th>Agent links</th><th>Verified</th><th>Status</th></tr>
<tr><td class="mono">444455556666</td><td>payments-prod</td><td class="mono">payments-*</td><td>2</td><td>1 of 2</td><td>{st('ok','Active')}</td></tr>
<tr><td class="mono">555566667777</td><td>payments-staging</td><td class="mono">payments-*</td><td>0</td><td>—</td><td>{st('ok','Active')}</td></tr>
<tr><td class="mono">777788889999</td><td>shared-tools</td><td class="mono">777788889999</td><td>1</td><td>1 of 1</td><td>{st('ok','Active')}</td></tr>
</table></div>
<div class="card"><div class="cb"><div class="k small muted">Equivalent CLI</div><div class="code">afs teams update-team --team-id team_01JD3Z… --allowed-aws-accounts "payments-*" 777788889999</div></div></div>
""")

CAT = [('Atlassian (Jira and Confluence)', 'Developer tools', '*.atlassian.net, api.atlassian.com +1', True, 14, 'Built in'), ('GitHub', 'Developer tools', 'github.com, api.github.com +2', True, 18, 'Built in'), ('Microsoft Outlook', 'Email', 'graph.microsoft.com, outlook.office365.com +1', True, 9, 'Built in'), ('Microsoft Teams', 'Collaboration', 'graph.microsoft.com +2', True, 11, 'Built in'), ('Microsoft Azure', 'Cloud', 'management.azure.com +2', True, 3, 'Built in'), ('Google Workspace and Cloud', 'Cloud', '*.googleapis.com, accounts.google.com', True, 5, 'Built in'), ('Slack', 'Collaboration', 'slack.com, *.slack.com', True, 12, 'Built in'), ('Okta', 'Identity', '*.okta.com, *.oktapreview.com', True, 4, 'Built in'), ('OpenAI', 'LLM · not Bedrock', 'api.openai.com', False, 0, 'Built in'), ('OpenRouter', 'LLM · not Bedrock', 'openrouter.ai', False, 0, 'Built in'), ('Internal artifact registry', 'Developer tools', 'nexus.corp.example:8443', True, 16, 'Custom')]

def catrow(n, c, e, on, teams, src):
    unm = ' <span class="badge b-warn" style="white-space:nowrap">Unmetered</span>' if "LLM" in c else ""
    state = st('ok','On for all teams') if on else st('pend','Off for all teams')
    return f'<tr><td><span class="cb2"></span></td><td><a>{n}</a>{unm}</td><td>{c}</td><td class="mono small">{e}</td><td>{src}</td><td>{teams if on else "—"}</td><td>{tg(on)} {state}</td></tr>'


page("19-admin-external-systems", "admin", admin_nav("external"), f"""
<div class="crumbs"><a>Agent Factory</a> › External systems</div>
<div class="alert warn"><span class="ic">⚠</span><div><b>Model providers other than Bedrock are not metered.</b> Calls to OpenAI or OpenRouter go straight from the agent to the provider. They do not pass through the Agent Factory gateway, are not counted in team budgets and are not stopped by hard caps. Turn them on only where the team pays and controls that spend another way.</div></div>
<div class="card"><div class="ch"><div><h2>Service catalog <span class="cnt">(11)</span> <span class="info">Info</span></h2>
<div class="sub">Outside services agents may reach. Every team gets each system that is on here, on by default; team-admins and agents can only turn systems off. Each system's endpoints become the agents' network egress rules.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Add custom system</span></div></div>
<div class="tools"><div class="filter">🔍 Find systems</div><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>System</th><th>Category</th><th>Endpoints</th><th>Source</th><th>Teams using</th><th>Service level</th></tr>
{"".join(catrow(*r) for r in CAT)}
</table></div>
<div class="card"><div class="ch"><div><h2>Team-declared systems</h2><div class="sub">Teams you allow can add systems they depend on, with an owner, a purpose and documentation. Those systems apply to that team only.</div></div><div class="btns"><span class="btn">Manage per team</span></div></div><div class="cb"><div class="grid g3">
<div class="kv"><div class="k">Teams allowed to declare systems</div><div class="v">3 of 12 · payments-factory, search-relevance, data-platform</div></div>
<div class="kv"><div class="k">Systems declared</div><div class="v">7 across 3 teams</div></div>
<div class="kv"><div class="k">Default for new teams</div><div class="v">Not allowed</div></div></div></div></div>
""")

TEAMSYS = [
 ("GitHub", "Service catalog", "github.com, api.github.com +2", True, False, "6 of 6", "github-bot-key"),
 ("Atlassian (Jira and Confluence)", "Service catalog", "*.atlassian.net +2", True, False, "5 of 6", "jira-api-token"),
 ("Slack", "Service catalog", "slack.com, *.slack.com", True, False, "4 of 6", "slack-bot-token"),
 ("Microsoft Outlook", "Service catalog", "graph.microsoft.com +2", False, False, "—", "—"),
 ("Microsoft Azure", "Service catalog", "management.azure.com +2", False, False, "—", "—"),
 ("OpenAI", "Service catalog", "api.openai.com", False, True, "—", "—"),
 ("PagerDuty", "Team-declared", "api.pagerduty.com, events.pagerduty.com", True, False, "1 of 6", "pagerduty-token"),
]
def teamrow(n, src, e, on, svcoff, used, cred):
    if svcoff:
        state = f'{tg(False, True)} {st("pend","Off for all teams")}'
    else:
        state = f'{tg(on)} {st("ok","On") if on else st("pend","Off for this team")}'
    badge = '<span class="badge b-blue" style="white-space:nowrap">Team-declared</span>' if src == "Team-declared" else '<span class="badge b-per" style="white-space:nowrap">Service catalog</span>'
    unm = ' <span class="badge b-warn">Unmetered</span>' if n == "OpenAI" else ""
    return f'<tr><td><a>{n}</a>{unm}</td><td>{badge}</td><td class="mono small">{e}</td><td>{used}</td><td class="mono small">{cred}</td><td>{state}</td></tr>'

declare_modal = """<div class="modalwrap"><div class="modal" style="width:680px"><div class="mh">Declare an external system<span class="muted">✕</span></div><div class="mb">
<div class="grid g2"><div class="field"><label>Name</label><div class="input">PagerDuty</div></div>
<div class="field"><label>Category</label><div class="input">Other ▾</div></div></div>
<div class="field"><label>Endpoints</label><div class="hint">Hosts the agents may reach, one per line. <span class="mono">*.domain</span> and <span class="mono">:port</span> are allowed; port 443 by default.</div><div class="input mono" style="height:auto;line-height:1.7">api.pagerduty.com<br>events.pagerduty.com</div></div>
<div class="grid g2"><div class="field"><label>Owner</label><div class="hint">Who answers for this dependency</div><div class="input">payments-sre</div></div>
<div class="field"><label>Documentation</label><div class="input mono small">https://developer.pagerduty.com/api-reference</div></div></div>
<div class="field"><label>Purpose</label><div class="input">Agents open and resolve incidents for payments services</div></div>
<div class="field"><label>Agents</label><div class="hint">On for every agent in the team by default. Turn it off per agent on the agent's page.</div></div>
</div><div class="mf"><span class="btn" style="border:0">Cancel</span><span class="btn p">Declare system</span></div></div></div>"""

page("20-ta-external-systems", "ta", team_nav("network", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › External systems</div>
<div class="card"><div class="ch"><div><h2>External systems <span class="cnt">(12)</span> <span class="info">Info</span></h2>
<div class="sub">Services this team's agents may reach. Systems from the service catalog are on unless you turn them off here; agents can be narrowed further on their own page. Turning a system off removes its endpoints from the agents' egress rules and stops delivering the secrets that belong to it.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Declare system</span></div></div>
<div class="tools"><div class="filter">🔍 Find systems</div><div class="pager">‹ <b>1</b> 2 › ⚙</div></div>
<table><tr><th>System</th><th>Source</th><th>Endpoints</th><th>Agents with access</th><th>Credentials</th><th>This team</th></tr>
{"".join(teamrow(*r) for r in TEAMSYS)}
</table></div>
""", modal=declare_modal)

AGSYS = [
 ("GitHub", "Service catalog", True, "", "github-bot-key"),
 ("Atlassian (Jira and Confluence)", "Service catalog", True, "", "jira-api-token"),
 ("Slack", "Service catalog", False, "Turned off for this agent by marcus.chen: reviews post to GitHub only", "—"),
 ("PagerDuty", "Team-declared", False, "Turned off for this agent", "—"),
 ("Google Workspace and Cloud", "Service catalog", True, "", "—"),
 ("Microsoft Outlook", "Service catalog", None, "Off for this team", "—"),
 ("OpenAI", "Service catalog", None, "Off for all teams (service admins)", "—"),
]
def agrow(n, src, on, note, cred):
    if on is None:
        state = f'{tg(False, True)} {st("pend","Off above")}'
    else:
        state = f'{tg(on)} {st("ok","On") if on else st("pend","Off")}'
    return f'<tr><td>{n}</td><td class="small">{src}</td><td>{state}</td><td class="small muted">{note}</td><td class="mono small">{cred}</td></tr>'

page("21-ta-agent-external-systems", "ta", team_nav("agents", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › <a>Agents</a> › reviewer-bot</div>
<div class="hdr"><div><h1>reviewer-bot</h1><div class="desc">{st('ok','Running')} · claude-opus · omp-review</div></div><div class="btns"><span class="btn">Restart</span><span class="btn">Pause</span><span class="btn p">Edit</span></div></div>
<div class="tabs"><span>Details</span><span>Configuration</span><span>Secrets & identity</span><span class="on">External systems</span><span>Usage</span><span>Logs</span><span>Revisions</span></div>
<div class="card"><div class="ch"><div><h2>External systems <span class="cnt">(5 of 12 on)</span> <span class="info">Info</span></h2>
<div class="sub">What this agent can reach. It gets every system its team has on; turn off the ones it does not need. Systems turned off above (by the team or the service) cannot be turned on here.</div></div>
<div class="btns"><span class="btn">View egress rules</span><span class="btn p">Save changes</span></div></div>
<table><tr><th>System</th><th>Source</th><th>This agent</th><th>Note</th><th>Credentials delivered</th></tr>
{"".join(agrow(*r) for r in AGSYS)}
</table></div>
<div class="alert"><span class="ic">ⓘ</span><div class="small">Egress is enforced by the network policy for this agent's pod: DNS, the Agent Factory LLM gateway, and the endpoints of the systems that are on. Everything else is blocked and logged.</div></div>
""")


MODELS = [("Claude Opus", "#3f51b5"), ("Claude Sonnet", "#688ae8"), ("Claude Haiku", "#9ab4f0"), ("Nova Pro", "#c33d69"), ("EKS compute", "#b0bec5")]
def stacked(days, scale):
    import math
    cols = []
    for i in range(days):
        w = 0.55 + 0.45 * math.sin(i / 2.3) ** 2 + (0.25 if i % 7 in (5, 6) else 0) * -1
        parts = [w * 0.42, w * 0.33, w * 0.08, w * 0.05, 0.12]
        cols.append('<div class="c">' + "".join(f'<i style="height:{int(v*scale)}px;background:{c}"></i>' for v, (_, c) in zip(parts, MODELS)) + '</div>')
    return '<div class="sb">' + "".join(cols) + '</div><div class="lg">' + "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in MODELS) + '<span>Nov 1 → Nov 20 · daily</span></div>'

def heat(rows):
    out = ['<div class="hm"><span></span>' + "".join(f"<b>{h:02d}</b>" if h % 3 == 0 else "<b></b>" for h in range(24))]
    for name, pattern in rows:
        cells = []
        for h in range(24):
            v = pattern(h)
            col = {0: "#eef1f4", 1: "#c6d4f6", 2: "#7d9de9", 3: "#2f5fd0", -1: "#d5d8dc"}[v]
            cells.append(f'<i style="background:{col}"></i>')
        out.append(f'<span class="n">{name}</span>' + "".join(cells))
    out.append('</div><div class="lg"><span><i style="background:#2f5fd0"></i>Working most of the hour</span><span><i style="background:#7d9de9"></i>Working part</span><span><i style="background:#c6d4f6"></i>Mostly idle</span><span><i style="background:#eef1f4;border:1px solid #ccc"></i>Idle</span><span><i style="background:#d5d8dc"></i>Paused</span><span>Today, hourly (UTC)</span></div>')
    return "".join(out)

def rangebar(extra=""):
    return f'<div class="rbar"><div class="seg"><span>24 h</span><span>7 d</span><span class="on">Month to date</span><span>30 d</span><span>90 d</span><span>Custom</span></div>{extra}<span class="sel">Model: all ▾</span><span class="sel">Group by: model ▾</span><span style="flex:1"></span><span class="btn">Download CSV</span><span class="btn">Schedule report</span></div>'

TEAMS_R = [
 ("payments-factory", 31880, 40000, 18.4, "11 of 12", 64, "2 (avg 3.1 h)", 1),
 ("search-relevance", 22410, 30000, 12.1, "7 of 9", 58, "2 (avg 5.4 h)", 0),
 ("mobile-platform", 15000, 15000, 9.8, "0 of 8", 0, "— (blocked by cap)", 0),
 ("data-platform", 9120, 20000, 6.2, "5 of 10", 41, "5 (avg 9.8 h)", 4),
 ("cve-2026-41873-swarm", 1830, 5000, 2.4, "24 of 24", 92, "0", 0),
]
def team_rows():
    out = []
    for n, sp, bud, tok, act, util, idle, den in TEAMS_R:
        pct = round(100 * sp / bud)
        cls = "r" if pct >= 100 else ("w" if pct >= 80 else "")
        den_s = f'<span class="warn">{den}</span>' if den else "0"
        out.append(f'<tr><td><a>{n}</a></td><td class="num">${sp:,}</td><td style="min-width:150px">{bar(pct, cls)}<span class="small muted">{pct}% of ${bud:,}</span></td><td class="num">{tok} B</td><td>{act}</td><td class="num">{util}%</td><td>{idle}</td><td class="num">{den_s}</td></tr>')
    return "".join(out)

page("22-admin-reports", "admin", admin_nav("reports"), f"""
<div class="crumbs"><a>Agent Factory</a> › Reports & analytics</div>
<div class="hdr"><div><h1>Reports & analytics <span class="info">Info</span></h1><div class="desc">Every team. Spend and tokens from the gateway in near real time, reconciled daily with AWS billing (CUR); compute from EKS split cost allocation.</div></div></div>
{rangebar('<span class="sel">Team: all ▾</span>')}
<div class="grid g4 kpi">
<div class="card"><div class="cb"><div class="k small muted">Spend, month to date</div><div class="big">$80,240</div>{bar(70)}<div class="small muted" style="margin-top:6px">70% of $114,000 total budgets · forecast $118,900</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Model calls · tokens</div><div class="big">1.92 M</div><div class="small muted">48.9 B tokens · 71% input, 9% cache reads</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Agents now</div><div class="big">47 working</div><div class="small muted">9 idle · 8 blocked by cap · 3 paused</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Utilization, month to date</div><div class="big">61%</div><div class="small muted">of running time spent working · 22 agents idle over 4 h today</div></div></div>
</div>
<div class="card"><div class="ch"><h2>Daily cost by Bedrock model</h2><span class="sel">Show: cost ▾</span></div><div class="cb">{stacked(20, 120)}</div></div>
<div class="card"><div class="ch"><div><h2>Teams <span class="cnt">(12)</span></h2><div class="sub">Select a team to open its report. Denied = blocked connections to external systems this month.</div></div></div>
<table><tr><th>Team</th><th class="num">Spend</th><th>Budget</th><th class="num">Tokens</th><th>Working now</th><th class="num">Utilization</th><th>Idle over 1 h</th><th class="num">Denied egress</th></tr>{team_rows()}</table></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>Cost by Bedrock model</h2></div><table><tr><th>Model</th><th class="num">Calls</th><th class="num">Input tok</th><th class="num">Output tok</th><th class="num">Cost</th><th class="num">Share</th></tr>
<tr><td>Claude Opus</td><td class="num">412 K</td><td class="num">9.8 B</td><td class="num">1.9 B</td><td class="num">$34,110</td><td class="num">43%</td></tr>
<tr><td>Claude Sonnet</td><td class="num">1.08 M</td><td class="num">24.1 B</td><td class="num">4.2 B</td><td class="num">$26,920</td><td class="num">34%</td></tr>
<tr><td>Claude Haiku</td><td class="num">380 K</td><td class="num">6.7 B</td><td class="num">1.1 B</td><td class="num">$6,410</td><td class="num">8%</td></tr>
<tr><td>Amazon Nova Pro</td><td class="num">48 K</td><td class="num">0.9 B</td><td class="num">0.2 B</td><td class="num">$3,980</td><td class="num">5%</td></tr>
<tr><td class="muted">EKS compute and storage</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">$8,820</td><td class="num">11%</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>External systems traffic</h2><div class="sub">Connections this month, all teams</div></div></div><table><tr><th>System</th><th class="num">Connections</th><th class="num">Data out / in</th><th class="num">Errors</th><th class="num">Denied</th></tr>
<tr><td>GitHub</td><td class="num">1.24 M</td><td class="num">38 / 412 GB</td><td class="num">0.4%</td><td class="num">0</td></tr>
<tr><td>Atlassian (Jira and Confluence)</td><td class="num">310 K</td><td class="num">4 / 61 GB</td><td class="num">1.1%</td><td class="num">12</td></tr>
<tr><td>Slack</td><td class="num">96 K</td><td class="num">1 / 3 GB</td><td class="num">0.2%</td><td class="num">31</td></tr>
<tr><td>OpenAI <span class="badge b-warn">Unmetered</span></td><td class="num">0</td><td class="num">—</td><td class="num">—</td><td class="num"><span class="warn">118</span></td></tr>
<tr><td class="muted">Hosts in no system</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num"><span class="warn">402</span> <a class="small">Review</a></td></tr></table></div>
</div>
<div class="alert warn"><span class="ic">⚠</span><div class="small">Spend with model providers other than Bedrock (OpenAI, OpenRouter) is not metered and does not appear in these figures. Their traffic does appear under External systems.</div></div>
""")

AG = [("reviewer-bot", "Working", "ok", "reviewing PR #482", 78, "—", 12980, "Claude Opus"),
      ("ledger-maintainer", "Working", "ok", "migrating ledger tests", 71, "—", 9410, "Claude Sonnet"),
      ("test-gap-finder", "Idle", "pend", "", 44, "3 h 10 min", 5760, "Claude Sonnet"),
      ("dependency-updater", "Idle", "pend", "", 22, "11 h 40 min", 2120, "Claude Haiku"),
      ("incident-scribe", "Paused", "pend", "", 0, "—", 1610, "Claude Haiku"),
      ("release-notes-bot", "Working", "ok", "drafting 2026.11.3 notes", 35, "—", 980, "Claude Sonnet")]
def ag_rows():
    out = []
    for n, stt, k, note, util, idle, cost, model in AG:
        note_s = f'<div class="small muted">{note}</div>' if note else ""
        out.append(f'<tr><td><a>{n}</a></td><td>{st(k, stt)}{note_s}</td><td style="min-width:120px">{bar(util)}<span class="small muted">{util}%</span></td><td>{idle}</td><td>{model}</td><td class="num">${cost:,}</td></tr>')
    return "".join(out)

def pat(kind):
    def f(h):
        if kind == "busy": return 3 if 7 <= h <= 21 else (2 if h in (6, 22) else 1)
        if kind == "office": return 3 if 9 <= h <= 17 else 0
        if kind == "burst": return 3 if h in (2, 3, 14) else (1 if h in (4, 15) else 0)
        if kind == "nightly": return 3 if h in (1, 2) else 0
        if kind == "paused": return -1
        return 2 if 10 <= h <= 16 else 0
    return f

page("23-ta-team-reports", "ta", team_nav("reports", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Reports</div>
<div class="hdr"><div><h1>Reports <span class="info">Info</span></h1><div class="desc">payments-factory · namespace afs-t-payments-factory</div></div></div>
<div class="tabs"><span class="on">Budget & usage</span><span>Activity</span><span>Models</span><span>External systems</span></div>
{rangebar('<span class="sel">Agent: all ▾</span>')}
<div class="grid g4 kpi">
<div class="card"><div class="cb"><div class="k small muted">Spend vs budget</div><div class="big">$31,880</div>{bar(80,'w')}<div class="small muted" style="margin-top:6px">80% of $40,000 · forecast to cap Nov 27</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Calls · tokens</div><div class="big">412 K</div><div class="small muted">18.4 B tokens · cost per call $0.077</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Utilization</div><div class="big">64%</div><div class="small muted">3 working now · 2 idle · 1 paused</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Idle time today</div><div class="big">14.9 h</div><div class="small muted">across 6 agents · longest 11 h 40 min</div></div></div>
</div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>Daily cost by model</h2></div><div class="cb">{stacked(20, 95)}</div></div>
<div class="card"><div class="ch"><h2>Activity today</h2><span class="sel">Agents: all ▾</span></div><div class="cb">{heat([("reviewer-bot", pat("busy")), ("ledger-maintainer", pat("office")), ("test-gap-finder", pat("burst")), ("dependency-updater", pat("nightly")), ("incident-scribe", pat("paused")), ("release-notes-bot", pat("x"))])}</div></div>
</div>
<div class="card"><div class="ch"><div><h2>Agents <span class="cnt">(6)</span></h2><div class="sub">Working: the agent made a model call, reported itself busy, or used CPU above the idle threshold in the window.</div></div></div>
<table><tr><th>Agent</th><th>Now</th><th>Utilization</th><th>Idle for</th><th>Top model</th><th class="num">Cost</th></tr>{ag_rows()}</table></div>
""")

TR = [("GitHub", "Service catalog", "8,210", "1.9 / 22.4 GB", "0.3%", "0", ""),
      ("Atlassian (Jira and Confluence)", "Service catalog", "1,340", "0.2 / 3.1 GB", "1.4%", "0", ""),
      ("Slack", "Service catalog", "—", "—", "—", "6", "Off for this agent"),
      ("Google Workspace and Cloud", "Service catalog", "212", "0.1 / 0.4 GB", "0%", "0", ""),
      ("api.openai.com", "OpenAI", "—", "—", "—", "14", "Off at service level"),
      ("paste.example", "No system", "—", "—", "—", "3", "Not in the catalog")]
def tr_rows():
    out = []
    for n, src, c, b, e, d, why in TR:
        d_s = f'<span class="warn">{d}</span>' if d != "0" else d
        out.append(f'<tr><td>{n}</td><td class="small">{src}</td><td class="num">{c}</td><td class="num">{b}</td><td class="num">{e}</td><td class="num">{d_s}</td><td class="small muted">{why}</td></tr>')
    return "".join(out)

def strip():
    segs = [("#eef1f4", 6), ("#2f5fd0", 4), ("#eef1f4", 1), ("#2f5fd0", 9), ("#7d9de9", 1), ("#eef1f4", 2), ("#2f5fd0", 1)]
    return '<div class="strip">' + "".join(f'<i style="width:{w/24*100:.2f}%;background:{c}"></i>' for c, w in segs) + '</div><div class="lg"><span>00:00</span><span style="flex:1"></span><span>06:00</span><span style="flex:1"></span><span>12:00</span><span style="flex:1"></span><span>18:00</span><span style="flex:1"></span><span>24:00</span></div>'

page("24-ta-agent-report", "ta", team_nav("agents", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › <a>Agents</a> › reviewer-bot</div>
<div class="hdr"><div><h1>reviewer-bot</h1><div class="desc">{st('ok','Working')} · reviewing PR #482 · claude-opus</div></div><div class="btns"><span class="btn">Download CSV</span><span class="btn">Pause</span><span class="btn p">Edit</span></div></div>
<div class="tabs"><span>Details</span><span>Configuration</span><span>Secrets & identity</span><span>External systems</span><span class="on">Usage</span><span>Logs</span><span>Revisions</span></div>
<div class="grid g4 kpi">
<div class="card"><div class="cb"><div class="k small muted">Cost, month to date</div><div class="big">$12,980</div><div class="small muted">41% of the team's spend</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Calls · tokens</div><div class="big">96 K</div><div class="small muted">410 M in · 91 M out · 38% cache reads</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Utilization, 7 days</div><div class="big">78%</div><div class="small muted">working 131 h · idle 37 h</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Longest idle, 7 days</div><div class="big">5 h 15 min</div><div class="small muted">Nov 16, 01:00 → 06:15 UTC</div></div></div>
</div>
<div class="card"><div class="ch"><h2>Activity today</h2><span class="sel">Day: Nov 20 ▾</span></div><div class="cb">{strip()}<div class="lg"><span><i style="background:#2f5fd0"></i>Working</span><span><i style="background:#7d9de9"></i>Partly working</span><span><i style="background:#eef1f4;border:1px solid #ccc"></i>Idle</span><span>Five-minute windows</span></div></div></div>
<div class="grid" style="grid-template-columns:2fr 3fr">
<div class="card"><div class="ch"><h2>Cost by model</h2></div><table><tr><th>Model</th><th class="num">Calls</th><th class="num">Tokens</th><th class="num">Cost</th></tr>
<tr><td>Claude Opus</td><td class="num">71 K</td><td class="num">402 M</td><td class="num">$11,240</td></tr>
<tr><td>Claude Haiku</td><td class="num">25 K</td><td class="num">99 M</td><td class="num">$410</td></tr>
<tr><td class="muted">EKS compute and storage</td><td class="num">—</td><td class="num">—</td><td class="num">$1,330</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>External systems traffic</h2><div class="sub">Connections this month. Denied attempts are listed with the reason.</div></div></div>
<table><tr><th>System or host</th><th>Source</th><th class="num">Conns</th><th class="num">Out / in</th><th class="num">Errors</th><th class="num">Denied</th><th>Why denied</th></tr>{tr_rows()}</table></div>
</div>
""")

page("12-tv-team-overview", "tv", team_nav("overview", "tv"), team_overview("tv"))

page("13-tv-secrets", "tv", team_nav("secrets", "tv"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Secrets</div>
<div class="alert"><span class="ic">ⓘ</span><div><b>Read-only.</b> You can see which secrets exist and where they are used. Values are never shown to anyone in Agent Factory.</div></div>
<div class="card"><div class="ch"><div><h2>Secrets <span class="cnt">(5)</span> <span class="info">Info</span></h2>
<div class="sub">Stored in AWS Secrets Manager under paths Agent Factory manages.</div></div>
<div class="btns"><span class="btn dis dd">Actions</span><span class="btn p dis">Create secret</span></div></div>
<div class="tools"><div class="filter">🔍 Find secrets</div><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Name</th><th>Scope</th><th>Description</th><th>Secrets Manager path</th><th>Used by</th><th>Rotation</th><th>Last changed</th><th>Value</th></tr>
{secret_rows(selectable=False)}</table></div>
""")

# ------------------------------------------------------------------------------------------------
# Later phases (shown to service admins and team-admins)
# ------------------------------------------------------------------------------------------------

page("14-admin-ephemeral-team", "admin", admin_nav("teams"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Teams</a> › Create team</div>
<div class="wiz"><div class="steps">
<div><div class="n">Step 1</div><b>Team details</b></div>
<div><div class="n">Step 2</div><b>Models & network</b></div>
<div class="on"><div class="n">Step 3</div><b>Budget</b></div>
<div class="todo"><div class="n">Step 4</div><b>Members</b></div>
<div class="todo"><div class="n">Step 5</div><b>Review and create</b></div></div>
<div style="flex:1;max-width:860px">
<div class="hdr"><div><h1>Budget <span class="badge b-eph">Ephemeral</span></h1><div class="desc">poc-contract-summarizer · budgeted workload / POC</div></div></div>
<div class="card"><div class="ch"><h2>Hard cap and lifetime</h2></div><div class="cb">
<div class="grid g3"><div class="field"><label>Lifetime budget (USD)</label><div class="hint">Never resets. Calls stop at the cap.</div><div class="input">2,000</div></div>
<div class="field"><label>Expires</label><div class="hint">Team is torn down at expiry</div><div class="input">2026-12-15 00:00 UTC</div></div>
<div class="field"><label>When the cap is reached</label><div class="input">Block calls and notify ▾</div></div></div>
<div class="field"><label>Teardown</label><div class="tiles">
<div class="tile on"><b><span class="radio on"></span> At expiry or cap, whichever first</b><span>Agents scaled to zero, IAM revoked, namespace deleted. Config and audit kept.</span></div>
<div class="tile"><b><span class="radio"></span> At expiry only</b><span>At the cap, agents pause and wait for a budget increase.</span></div></div></div>
</div></div>
<div class="card"><div class="ch"><h2>Estimate</h2></div><div class="cb"><div class="grid g3">
<div class="kv"><div class="k">3 agents × claude-sonnet</div><div class="v">≈ $60 / day at typical load</div></div>
<div class="kv"><div class="k">Cap reached in</div><div class="v">≈ 33 days (after expiry)</div></div>
<div class="kv"><div class="k">Charged to</div><div class="v">CC-5150 · Contracts Innovation</div></div></div></div></div>
<div style="display:flex;justify-content:flex-end;gap:8px"><span class="btn" style="border:0">Cancel</span><span class="btn">Previous</span><span class="btn p">Next</span></div>
</div></div>
""")

page("15-admin-work-orders", "admin", admin_nav("wo"), f"""
<div class="crumbs"><a>Agent Factory</a> › Work orders</div>
<div class="hdr"><div><h1>Work orders <span class="info">Info</span></h1><div class="desc">Security creates CVE work orders through the console, CLI, API or EventBridge. Agent Factory assigns a capped remediation team from a swarm template, tracks a PR per repository and notifies owning teams against the SLA.</div></div></div>
<div class="card"><div class="ch"><div><h2>Work orders <span class="cnt">(4 open)</span> <span class="info">Info</span></h2></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Create work order</span></div></div>
<div class="tools"><div class="filter">🔍 Find by CVE, repo or owning team</div><span class="sel">Open ▾</span><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Work order</th><th>Kind</th><th>Status</th><th>Repos</th><th>PRs</th><th>Owning team</th><th>SLA due</th><th>Assigned team</th></tr>
<tr><td><span class="radio"></span></td><td><a>CVE-2026-41873</a> <span class="muted small">netty</span></td><td>CVE remediation</td><td>{st('inf','PRs opened')}</td><td>14</td><td>11 open · 3 merged</td><td>payments, claims</td><td class="warn">Nov 22 (2d)</td><td>cve-2026-41873-swarm</td></tr>
<tr><td><span class="radio"></span></td><td><a>CVE-2026-40210</a> <span class="muted small">jackson-databind</span></td><td>CVE remediation</td><td>{st('ok','In progress')}</td><td>6</td><td>2 open</td><td>identity</td><td>Nov 29 (9d)</td><td>cve-2026-40210-swarm</td></tr>
<tr><td><span class="radio"></span></td><td><a>CVE-2026-39555</a> <span class="muted small">openssl base image</span></td><td>CVE remediation</td><td>{st('pend','Open')}</td><td>31</td><td>—</td><td>8 teams</td><td>Dec 04 (14d)</td><td>—</td></tr>
<tr><td><span class="radio"></span></td><td><a>WO-0192</a> <span class="muted small">Log4j config sweep</span></td><td>General</td><td>{st('ok','In progress')}</td><td>9</td><td>4 open · 5 merged</td><td>platform</td><td>—</td><td>platform-hygiene</td></tr>
</table></div>
""")


# ------------------------------------------------------------------------------------------------
# Cost allocation tags (000010)
# ------------------------------------------------------------------------------------------------

STAGS = [("environment", "Fixed", "prod", "—", "All 42"), ("managed-by", "Fixed", "agent-factory", "—", "All 42"),
         ("business-unit", "Required", "Payments, Claims, Search, Platform, Identity, Unassigned", "Unassigned", "42 (3 on default)"),
         ("product-line", "Required", "Any value", "—", "40 · 2 missing"),
         ("data-classification", "Required", "public, internal, confidential, restricted", "internal", "42")]

def stag_rows():
    out = []
    for k, m, v, d, n in STAGS:
        badge = st('inf', m) if m == "Fixed" else st('ok', m)
        warn = ' class="warn"' if "missing" in n else ""
        out.append(f'<tr><td><span class="radio"></span></td><td class="mono">{k}</td><td>{badge}</td><td>{v}</td><td>{d}</td><td{warn}>{n}</td></tr>')
    return "".join(out)

page("25-admin-cost-tags", "admin", admin_nav("tags"), f"""
<div class="crumbs"><a>Agent Factory</a> › Cost allocation tags</div>
<div class="hdr"><div><h1>Cost allocation tags <span class="info">Info</span></h1><div class="desc">Tags on every AWS resource Agent Factory creates and on every Bedrock call, so spend rolls up the way the organization reports it. Activate the keys as cost allocation tags in AWS Billing to see them in CUR.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Add tag key</span></div></div>
<div class="card"><div class="ch"><div><h2>System tags</h2><div class="sub">Always set by Agent Factory. Nobody configures, changes or removes them.</div></div></div>
<table><tr><th>Key</th><th>Value</th><th>On</th></tr>
<tr><td class="mono">afs-team-id</td><td>The team's id, for example <span class="mono">team_01JD3Z…</span></td><td>Every team resource, every agent resource, every Bedrock call</td></tr>
<tr><td class="mono">afs-agent-id</td><td>The agent's id, for example <span class="mono">agt_01JD41…</span></td><td>Every agent resource and every Bedrock call the agent makes</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>Service tags <span class="cnt">(5)</span></h2><div class="sub"><b>Fixed</b>: one value for every team. <b>Required</b>: each team gives its value when it is created, optionally from a list; a default covers teams that existed before the key.</div></div>
<div class="btns"><span class="btn sm">Edit</span><span class="btn sm">Remove</span></div></div>
<table><tr><th></th><th>Key</th><th>Kind</th><th>Value or allowed values</th><th>Default</th><th>Teams with a value</th></tr>{stag_rows()}</table></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>Spend by business-unit, Nov MTD</h2><span class="sel">Group by: business-unit ▾</span></div>
<table><tr><th>Value</th><th class="num">Teams</th><th class="num">Calls</th><th class="num">Cost</th></tr>
<tr><td>Payments</td><td class="num">9</td><td class="num">1.9 M</td><td class="num">$71,420</td></tr>
<tr><td>Claims</td><td class="num">7</td><td class="num">1.1 M</td><td class="num">$40,210</td></tr>
<tr><td>Search</td><td class="num">6</td><td class="num">820 K</td><td class="num">$31,900</td></tr>
<tr><td>Platform</td><td class="num">12</td><td class="num">610 K</td><td class="num">$24,880</td></tr>
<tr><td class="muted">Unassigned (default)</td><td class="num">3</td><td class="num">90 K</td><td class="num">$4,110</td></tr></table></div>
<div class="card"><div class="ch"><h2>Teams missing a required tag</h2></div>
<table><tr><th>Team</th><th>Missing</th><th>Since</th></tr>
<tr><td><a>legacy-batch-retire</a></td><td class="mono">product-line</td><td>Nov 14 (key added)</td></tr>
<tr><td><a>poc-contract-summarizer</a></td><td class="mono">product-line</td><td>Nov 14 (key added)</td></tr></table>
<div class="cb small muted">New teams cannot be created without required tags. Untagged spend shows as "(untagged)" in reports.</div></div>
</div>
<div class="card"><div class="cb"><div class="k small muted">Equivalent CLI</div><div class="code">afs admin put-service-tag --key business-unit --mode required --allowed-values Payments Claims Search Platform Identity Unassigned --default-value Unassigned</div></div></div>
""")

page("26-ta-team-tags", "ta", team_nav("tags", "ta"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Cost tags</div>
<div class="hdr"><div><h1>Cost tags <span class="info">Info</span></h1><div class="desc">Every AWS resource and Bedrock call of this team carries these tags. Reports roll spend, activity and traffic up by them.</div></div>
<div class="btns"><span class="btn p">Add tag</span></div></div>
<div class="card"><div class="ch"><div><h2>Set by Agent Factory and the service</h2><div class="sub">Read-only here. Required values are yours to set; fixed ones come from service admins.</div></div><div class="btns"><span class="btn sm">Edit required values</span></div></div>
<table><tr><th>Key</th><th>Value</th><th>Source</th></tr>
<tr><td class="mono">afs-team-id</td><td class="mono">team_01JD3Z5Y8K2M4N6P8Q0R2S4T6V</td><td>{st('inf','System')}</td></tr>
<tr><td class="mono">afs-agent-id</td><td class="muted">Each agent's own id</td><td>{st('inf','System')}</td></tr>
<tr><td class="mono">environment</td><td>prod</td><td>Service · fixed</td></tr>
<tr><td class="mono">managed-by</td><td>agent-factory</td><td>Service · fixed</td></tr>
<tr><td class="mono">business-unit</td><td>Payments</td><td>Service · required</td></tr>
<tr><td class="mono">product-line</td><td>merchant-ledger</td><td>Service · required</td></tr>
<tr><td class="mono">data-classification</td><td>confidential</td><td>Service · required</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>Team tags <span class="cnt">(3)</span></h2><div class="sub">Optional. Any key except the service's and the reserved <span class="mono">aws:</span> and <span class="mono">afs-</span> prefixes. Up to 45 tags in total.</div></div><div class="btns"><span class="btn sm">Edit</span><span class="btn sm">Remove</span></div></div>
<table><tr><th></th><th>Key</th><th>Value</th><th>Last changed</th></tr>
<tr><td><span class="radio"></span></td><td class="mono">project</td><td>ledger-modernization</td><td>Nov 03 · marcus.chen</td></tr>
<tr><td><span class="radio"></span></td><td class="mono">initiative</td><td>FY27-reliability</td><td>Oct 21 · marcus.chen</td></tr>
<tr><td><span class="radio"></span></td><td class="mono">owner-team</td><td>payments-eng</td><td>Sep 02 · marcus.chen</td></tr></table></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>Where the tags go</h2></div><div class="cb small">
<div>• IAM roles, EBS volumes and snapshots, Bedrock inference profiles and Secrets Manager secrets, as AWS tags</div>
<div>• Each Bedrock call, as request metadata the gateway adds</div>
<div>• Each agent's pod, as <span class="mono">/etc/afs/tags.json</span> and <span class="mono">AFS_TAGS</span>, so an agent can pass them to other services if it wants</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Equivalent CLI</div><div class="code">afs teams put-team-tags --team-id team_01JD3Z… --tags project=ledger-modernization initiative=FY27-reliability</div></div></div>
</div>
""")


# ------------------------------------------------------------------------------------------------
# Swarms, swarm templates and work order detail (000012)
# ------------------------------------------------------------------------------------------------

def pool_row(n, tmpl, model, desired, rep_, work, idle, imp, hand, store, role, spend):
    impc = f'<span class="warn">{imp} impaired</span>' if imp else "0 impaired"
    return (f'<tr><td><span class="radio"></span></td><td><a>{n}</a></td><td>{tmpl}</td><td>{model}</td>'
            f'<td class="num">{desired}</td><td>{rep_} reporting · {work} working · {idle} idle · {impc}</td>'
            f'<td>{hand}</td><td>{store}</td><td class="small">{role}</td><td class="num">{spend}</td></tr>')

page("27-ta-swarm-pools", "sw", team_nav("pools", "sw", "cve-2026-41873-swarm", True), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>cve-2026-41873-swarm</a> › Pools &amp; stages</div>
<div class="hdr"><div><h1>Pools &amp; stages <span class="badge b-eph">Ephemeral</span> <span class="info">Info</span></h1>
<div class="desc">Work order <a>CVE-2026-41873</a> · tears down when the work order completes, or at expiry Nov 27 00:00 UTC</div></div>
<div class="btns"><span class="btn">Add stage</span><span class="btn dd">Actions</span><span class="btn p">Create pool</span></div></div>
<div class="grid g4">
<div class="card"><div class="cb"><div class="k small muted">Lifetime budget</div><div class="v"><b>$312.40</b> of $500.00</div>{bar(62)}</div></div>
<div class="card"><div class="cb"><div class="k small muted">Workers</div><div class="v"><b>23</b> of 24 desired reporting</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Repositories</div><div class="v">14 · 11 PRs open · 3 merged</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">SLA</div><div class="v">{st('warn','Due soon')} Nov 22 18:00 UTC</div></div></div></div>
<div class="card"><div class="ch"><div><h2>Stage 1 · scan <span class="cnt">(1 pool)</span></h2><div class="sub">Finds affected modules and writes a fix plan per repository</div></div></div>
<table><tr><th></th><th>Pool</th><th>Template</th><th>Model</th><th>Workers</th><th>Status</th><th>Hands work to</th><th>Storage</th><th>Shared role</th><th>Spend</th></tr>
{pool_row("dep-scanner", "dependency-scanner", "claude-haiku", 4, 4, 1, 3, 0, "pr-writer", "Scratch 20 GiB", "—", "$18.90")}
</table></div>
<div class="card"><div class="ch"><div><h2>Stage 2 · fix <span class="cnt">(2 pools)</span></h2><div class="sub">Edits, tests and opens pull requests</div></div></div>
<table><tr><th></th><th>Pool</th><th>Template</th><th>Model</th><th>Workers</th><th>Status</th><th>Hands work to</th><th>Storage</th><th>Shared role</th><th>Spend</th></tr>
{pool_row("pr-writer", "java-maintainer", "claude-sonnet", 16, 15, 12, 3, 1, "pr-reviewer", "Scratch 40 GiB + shared EFS", "afs-cve-remediation · 3 accounts ✓", "$268.10")}
{pool_row("pr-reviewer", "code-reviewer", "claude-sonnet", 4, 4, 2, 2, 0, "—", "Scratch 20 GiB", "—", "$25.40")}
</table></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>Handoffs</h2></div><div class="cb small">
<div>dep-scanner → pr-writer · queue <span class="mono">afs-cve-2026-41873-swarm-pr-writer</span> · 3 waiting</div>
<div>pr-writer → pr-reviewer · queue <span class="mono">afs-cve-2026-41873-swarm-pr-reviewer</span> · 1 waiting</div>
<div class="muted" style="margin-top:6px">Workers get the queue URLs as <span class="mono">AFS_HANDOFF_*_QUEUE_URL</span> and <span class="mono">AFS_INBOX_QUEUE_URL</span>.</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Equivalent CLI</div><div class="code">afs pools scale-pool --team-id team_01JD3Z… --pool-id pool_01JD3Z… --workers 20</div></div></div></div>
""")

page("28-admin-swarm-templates", "admin", admin_nav("swarmt"), f"""
<div class="crumbs"><a>Agent Factory</a> › Swarm templates</div>
<div class="hdr"><div><h1>Swarm templates <span class="info">Info</span></h1><div class="desc">The shape of the remediation teams that work orders create: stages, pools, handoffs, secrets and the default cap.</div></div>
<div class="btns"><span class="btn dd">Actions</span><span class="btn p">Create template</span></div></div>
<div class="card"><div class="ch"><div><h2>Templates <span class="cnt">(3)</span></h2></div></div>
<div class="tools"><div class="filter">🔍 Find templates</div><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Name</th><th>Kind</th><th>Stages · pools</th><th>Default cap</th><th>Time to live</th><th>Teardown</th><th>Used by</th><th>State</th></tr>
<tr><td><span class="radio on"></span></td><td><a>java-cve-remediation</a></td><td>CVE remediation</td><td>2 · 3</td><td class="num">$500</td><td>7 days</td><td>When the work order completes</td><td>2 open work orders</td><td>{st('ok','Enabled')}</td></tr>
<tr><td><span class="radio"></span></td><td><a>base-image-rebuild</a></td><td>CVE remediation</td><td>1 · 2</td><td class="num">$1,200</td><td>14 days</td><td>When the work order completes</td><td>1 open work order</td><td>{st('ok','Enabled')}</td></tr>
<tr><td><span class="radio"></span></td><td><a>config-sweep</a></td><td>General</td><td>1 · 1</td><td class="num">$150</td><td>3 days</td><td>At cap or expiry</td><td>—</td><td>{st('pend','Disabled')}</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>java-cve-remediation</h2><div class="sub">Revision 4 · changed Nov 12 by priya.raman</div></div><div class="btns"><span class="btn sm">Edit</span><span class="btn sm">Disable</span></div></div>
<table><tr><th>Stage</th><th>Pool</th><th>Template · model</th><th>Workers</th><th>Storage</th><th>Shared role</th><th>Secrets the pool needs</th></tr>
<tr><td>1 · scan</td><td class="mono">dep-scanner</td><td>dependency-scanner · claude-haiku</td><td>4</td><td>Scratch 20 GiB</td><td>—</td><td class="mono small">github-app-key (bound from service)</td></tr>
<tr><td>2 · fix</td><td class="mono">pr-writer</td><td>java-maintainer · claude-sonnet</td><td>16</td><td>Scratch 40 GiB + EFS</td><td class="mono small">afs-cve-remediation</td><td class="mono small">github-app-key, maven-mirror-token (team fills)</td></tr>
<tr><td>2 · fix</td><td class="mono">pr-reviewer</td><td>code-reviewer · claude-sonnet</td><td>4</td><td>Scratch 20 GiB</td><td>—</td><td class="mono small">github-app-key</td></tr></table>
<div class="cb small muted">Handoffs: dep-scanner → pr-writer → pr-reviewer. Secrets the team fills are created empty; their values never pass through Agent Factory's database.</div></div>
<div class="card"><div class="cb"><div class="k small muted">Equivalent CLI</div><div class="code">afs swarm-templates create-swarm-template --cli-input-json file://java-cve-remediation.json</div></div></div>
""")

def wo_repo(repo, owner, status, pr, notes):
    return f'<tr><td class="mono">{repo}</td><td>{owner}</td><td>{status}</td><td>{pr}</td><td class="small muted">{notes}</td></tr>'

page("29-sec-work-order-detail", "so", nav("Agent Factory", [("grp", "Security"), ("wo", "Work orders")], "wo"), f"""
<div class="crumbs"><a>Agent Factory</a> › <a>Work orders</a> › CVE-2026-41873</div>
<div class="hdr"><div><h1>CVE-2026-41873 <span class="badge b-eph">Critical</span> <span class="info">Info</span></h1>
<div class="desc">netty: HTTP/2 request smuggling · source EventBridge (security-scanner) · created Nov 18 09:12 UTC</div></div>
<div class="btns"><span class="btn">Add repositories</span><span class="btn">Cancel work order</span></div></div>
<div class="grid g4">
<div class="card"><div class="cb"><div class="k small muted">Status</div><div class="v">{st('inf','PRs opened')}</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">SLA due</div><div class="v">Nov 22 18:00 UTC · {st('warn','Due soon')}</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Remediation team</div><div class="v"><a>cve-2026-41873-swarm</a> · java-cve-remediation</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Spend against cap</div><div class="v"><b>$312.40</b> of $500.00</div>{bar(62)}</div></div></div>
<div class="card"><div class="ch"><div><h2>Repositories <span class="cnt">(14)</span></h2><div class="sub">11 PRs open · 3 merged · 0 not affected · 0 failed</div></div></div>
<div class="tools"><div class="filter">🔍 Find by repository or owner</div><span class="sel">All statuses ▾</span><div class="pager">‹ <b>1</b> 2 › ⚙</div></div>
<table><tr><th>Repository</th><th>Owner</th><th>Status</th><th>Pull request</th><th>Notifications sent</th></tr>
{wo_repo("payments/ledger-core", "payments-factory", st('ok','Merged'), '<a>#4182</a>', "Assigned Nov 18 · PR opened Nov 19 · Merged Nov 20")}
{wo_repo("payments/merchant-api", "payments-factory", st('inf','PR opened'), '<a>#977</a>', "Assigned Nov 18 · PR opened Nov 20")}
{wo_repo("claims/intake-service", "claims-factory", st('inf','PR opened'), '<a>#311</a>', "Assigned Nov 18 · PR opened Nov 20 · SLA warning Nov 20")}
{wo_repo("vendor/edi-gateway", "edi-support@example.com (outside AFS)", st('ok','In progress'), "—", "Emailed Nov 18 · SLA warning Nov 20")}
{wo_repo("claims/fraud-rules", "claims-factory", st('pend','Pending'), "—", "Assigned Nov 18")}
</table></div>
<div class="grid g2">
<div class="card"><div class="ch"><h2>Owning teams</h2></div><div class="cb small">
<div>payments-factory · 6 repositories · channel #payments-alerts</div><div>claims-factory · 7 repositories · channel #claims-oncall</div>
<div>Outside contacts · 1 repository · service email channel</div><div class="muted" style="margin-top:6px">Each owner is notified once per event: assigned, PR opened, merged, SLA warning (48 h before due), SLA breached and completion.</div></div></div>
<div class="card"><div class="cb"><div class="k small muted">Equivalent CLI</div><div class="code">afs work-orders describe-work-order --work-order-id wo_01JD3Z…</div></div></div></div>
""")

# ------------------------------------------------------------------------------------------------
# Paperclip team collaboration (T16, V3)
# ------------------------------------------------------------------------------------------------

def collab_page(ro):
    dis = " dis" if ro else ""
    tip = '<span class="tip"><span class="tipbox">Requires team-admin</span></span>' if ro else ""
    banner = ('<div class="alert"><span class="ic">ⓘ</span><div><b>You have read-only access to this page.</b> '
              'You can open Paperclip and see how it is set up. Team-admins (Marcus Chen) change the endpoints and connections. '
              'Your role decides what you can do inside Paperclip: viewers read, collaborators also write.</div></div>') if ro else ""
    open_btn = '<span class="btn p">Open Paperclip ↗</span>'
    cmd = "" if ro else ('<div class="card"><div class="cb"><div class="k small muted">Equivalent CLI for the last change</div>'
        '<div class="code">afs collaboration put-collaboration --team-id team_01JD3Z… --web-ui-enabled --no-rest-api-enabled</div></div></div>')
    agents = [
        ("reviewer-bot", True, "ag_8f2a41", "linked", "ok", "3 min ago"),
        ("ledger-maintainer", True, "ag_3c77d0", "linked", "ok", "3 min ago"),
        ("dependency-updater", True, "—", "pending", "warn", "—"),
        ("release-notes-bot", True, "ag_91be05", "failed", "err", "12 min ago"),
        ("test-gap-finder", False, "—", "disabled", "pend", "—"),
        ("incident-scribe", False, "—", "disabled", "pend", "—"),
    ]
    rows = "".join(
        f'<tr class="{"sel" if n=="dependency-updater" and not ro else ""}"><td><span class="cb2{" on" if n=="dependency-updater" and not ro else ""}"></span></td><td><a>{n}</a></td>'
        f'<td>{tg(c, ro)}</td><td class="mono">{pid}</td><td>{st(k, ls)}</td><td class="muted">{when}</td></tr>'
        for n, c, pid, ls, k, when in agents)
    return f"""
<div class="crumbs"><a>Agent Factory</a> › <a>payments-factory</a> › Collaboration</div>
{banner}
<div class="hdr"><div><h1>Collaboration <span class="badge b-blue">Paperclip</span> <span class="info">Info</span></h1>
<div class="desc">One board, chat and roster for the team's agents and people. One collaboration agent per team.</div></div>
<div class="btns"><span class="btn dd{dis}">Actions</span>{open_btn}{tip}</div></div>
<div class="card"><div class="ch"><h2>Status</h2></div><div class="cb"><div class="grid g4">
<div class="kv"><div class="k">Collaboration agent</div><div class="v"><a>paperclip-hub</a> <span class="badge b-blue">Collaboration</span></div><div class="k">Phase</div><div class="v">{st('ok','Ready')} · gen 6 / 6</div></div>
<div class="kv"><div class="k">Hostname</div><div class="v mono">payments-factory.collab.example.com</div><div class="k">Registration</div><div class="v">Manual</div></div>
<div class="kv"><div class="k">Web UI</div><div class="v">{st('ok','On')}</div><div class="k">REST API</div><div class="v">{st('pend','Off')}</div></div>
<div class="kv"><div class="k">Conditions</div><div class="v small">EndpointReady {st('ok','True')}<br>PaperclipReady {st('ok','True')}<br>RegistrationHealthy {st('ok','True')}<br>UnmanagedPaperclipAgents {st('ok','False')}</div></div>
</div></div></div>
<div class="card"><div class="ch"><div><h2>Public endpoints</h2><div class="sub">Both are reached through the AFS edge: sign-in with {"your" if ro else "the team's"} company provider and an AFS role check on every request.</div></div></div><div class="cb">
<div class="grid g2">
<div class="tile on"><b>{tg(True, ro)} Web UI</b><span>The Paperclip board and chat in a browser. Viewers read; collaborators and team-admins can write.</span></div>
<div class="tile"><b>{tg(False, ro)} REST API</b><span>Paperclip's API for pipelines, with an AFS token in X-Afs-Authorization. Needs the collaborator or team-admin role to write.</span></div></div>
<div class="small muted" style="margin-top:10px">Switches are disabled with "Not allowed for this team by the service" when the team guardrail is off, or "Public collaboration is off for the service" when the service setting is off.</div></div></div>
{cmd}
<div class="card"><div class="ch"><div><h2>Connected agents <span class="cnt">(6)</span></h2><div class="sub">Connected agents get PAPERCLIP_API_URL, PAPERCLIP_AGENT_ID and PAPERCLIP_AGENT_API_KEY in their environment. Agents that predate the collaboration agent are not connected automatically.</div></div>
<div class="btns"><span class="btn dis">Disconnect</span><span class="btn p{dis if ro else ''}">Connect</span></div></div>
<div class="tools"><div class="filter">🔍 Find agents</div><span class="sel">All link states ▾</span><div class="pager">‹ <b>1</b> › ⚙</div></div>
<table><tr><th></th><th>Agent</th><th>Connected</th><th>Paperclip agent id</th><th>Link state</th><th>Last sync</th></tr>{rows}</table></div>
<div class="grid g2">
<div class="card"><div class="ch"><div><h2>Paperclip-managed secrets <span class="cnt">(3)</span></h2><div class="sub">Created by Paperclip itself under the agent's reserved path. Read-only; values are never shown.</div></div></div>
<table><tr><th>Name</th><th>Managed by</th><th>Last changed</th></tr>
<tr><td class="mono">paperclip-github-connector</td><td><span class="badge b-warn">Managed by Paperclip</span></td><td>2026-11-19</td></tr>
<tr><td class="mono">paperclip-jira-sync-token</td><td><span class="badge b-warn">Managed by Paperclip</span></td><td>2026-11-18</td></tr>
<tr><td class="mono">paperclip-better-auth-secret</td><td><span class="badge b-blue">Managed by AFS</span></td><td>2026-11-12</td></tr></table></div>
<div class="card"><div class="ch"><div><h2>Recent access</h2><div class="sub">Last 7 days, from the edge's records. Counts only, no content.</div></div></div><div class="cb">
<div class="grid g3"><div class="kv"><div class="k">Sign-ins</div><div class="big g">64</div></div><div class="kv"><div class="k">People</div><div class="big g">11</div></div><div class="kv"><div class="k">Denied</div><div class="big g">3</div></div></div>
<table><tr><th>Person</th><th>Sign-ins</th><th>Requests</th><th>Denied</th></tr>
<tr><td>dana.ortiz</td><td>9</td><td class="num">1,204</td><td class="num">0</td></tr>
<tr><td>marcus.chen</td><td>14</td><td class="num">3,880</td><td class="num">1</td></tr>
<tr><td>priya.raman <span class="badge b-warn">Service admin entry</span></td><td>1</td><td class="num">42</td><td class="num">0</td></tr></table></div></div></div>
"""

page("30-ta-collaboration", "ta", team_nav("collab", "ta", collab=True), collab_page(False))
page("31-tv-collaboration", "tv", team_nav("collab", "tv", collab=True), collab_page(True))

# Orchestration agent redesign screens (team-orchestration-agent-PRD.md)
exec((pathlib.Path(__file__).parent / "orch_screens.py").read_text())

# Team model gateway proposal screens (model-endpoint-gateway-PRD.md, not built)
exec((pathlib.Path(__file__).parent / "gw_screens.py").read_text())

print("\n".join(sorted(p.name for p in OUT.glob("*.html"))))
