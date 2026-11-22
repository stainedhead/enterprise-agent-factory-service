// CVE remediation: a security work order becomes an ephemeral swarm that opens PRs and tears itself down.
export default (d) => {
  d.size(1400, 720);
  d.title('Work orders and swarms: CVE remediation', 'Security files one work order. AFS builds a budget-capped swarm, tracks every repository to merge, notifies owners and tears the team down.');

  d.node({ id: 'sec', x: 30, y: 130, w: 220, title: 'Security team', sub: ['security_operator role', 'or EventBridge event'], tone: 'danger' });
  d.node({ id: 'wo', x: 300, y: 130, w: 240, title: 'Work order', sub: ['CVE-2026-1234, due in 14 days', 'affected repos, swarm template', 'lifetime budget $2,000'], tone: 'api' });
  d.node({ id: 'rec', x: 590, y: 130, w: 220, title: 'afs-reconciler', sub: ['instantiates the team', 'from the swarm template'], tone: 'api' });

  d.group({ x: 860, y: 96, w: 510, h: 380, label: 'Ephemeral team afs-t-cve-2026-1234', tone: 'k8s', sub: 'teardown at work complete · hard budget cap · expiry' });
  d.node({ id: 's1', x: 885, y: 160, w: 140, title: 'Stage 1', sub: ['triage pool', '4 workers'], tone: 'k8s' });
  d.node({ id: 's2', x: 1045, y: 160, w: 140, title: 'Stage 2', sub: ['fix pool', '20 workers'], tone: 'k8s' });
  d.node({ id: 's3', x: 1205, y: 160, w: 140, title: 'Stage 3', sub: ['review pool', '6 workers'], tone: 'k8s' });
  d.node({ id: 'inbox', x: 885, y: 285, w: 460, title: 'Per-pool SQS inboxes for handoffs', sub: ['one identity per pool, scratch volume per worker'], tone: 'aws' });
  d.node({ id: 'gw', x: 885, y: 385, w: 460, title: 'afs-gateway', sub: ['every model call counts against the lifetime budget'], tone: 'api' });

  d.node({ id: 'gh', x: 860, y: 560, w: 240, title: 'GitHub', sub: ['one PR per affected repo', 'state polled via GitHub App'], tone: 'neutral' });
  d.node({ id: 'prog', x: 560, y: 560, w: 250, title: 'Progress per repository', sub: ['PATCH …/repos/{host}/{owner}/{repo}', 'workload token, own team only'], tone: 'api' });
  d.node({ id: 'own', x: 260, y: 560, w: 250, title: 'Owning teams notified', sub: ['their channels or email', 'pr_opened, sla_warning, merged'], tone: 'client' });
  d.node({ id: 'done', x: 30, y: 400, w: 220, title: 'Done → teardown', sub: ['all merged, not affected', 'or skipped: team deleted,', 'usage and audit kept'], tone: 'data' });

  d.edge('sec', 'wo', { tone: 'danger', label: 'POST /v1/work-orders', lx: 275, ly: 112 });
  d.edge('wo', 'rec', { tone: 'api' });
  d.edge('rec', 's1', { from: 'r', to: 'l', tone: 'api', via: [[835, 175], [835, 200]] });
  d.edge('s1', 's2', { tone: 'k8s' });
  d.edge('s2', 's3', { tone: 'k8s' });
  d.edge('s2', 'inbox', { from: 'b', to: 't', tone: 'aws', label: 'hand off' });
  d.edge('inbox', 'gw', { from: 'b', to: 't', tone: 'api', label: 'model calls' });
  d.edge('gw', 'gh', { from: 'b', to: 't', ff: 0.1, tf: 0.5, tone: 'neutral', label: 'open PRs', lx: 980, ly: 530 });
  d.edge('gh', 'prog', { tone: 'api' });
  d.edge('prog', 'own', { tone: 'client' });
  d.edge('wo', 'prog', { from: 'b', to: 't', ff: 0.7, tf: 0.2, tone: 'api', dashed: true, label: 'SLA tracking', lx: 470, ly: 360 });
  d.edge('own', 'done', { from: 'l', to: 'b', tone: 'data' });
  d.text({ x: 30, y: 690, lines: 'Phase 2 of the product; built and shipped in this release. Long-running development teams use the same isolation, identity, secrets and budget controls.', size: 12.5 });
};
