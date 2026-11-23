// Release 1.1.0: every team's orchestration agent, its endpoint exposure, and model admission.
export default (d) => {
  d.size(1500, 860);
  d.title('Orchestration agent and model access', 'Every team gets one orchestration agent at creation. Only it can be reached from outside the cluster, and every model call must pass three narrowing lists.');

  // Callers outside the cluster
  d.group({ x: 20, y: 96, w: 300, h: 380, label: 'Outside the cluster', tone: 'client', sub: 'people and pipelines' });
  d.node({ id: 'web', x: 40, y: 160, w: 260, title: 'Browser (Web UI)', sub: ['team members, SSO per team'], tone: 'client' });
  d.node({ id: 'apic', x: 40, y: 260, w: 260, title: 'Web API client', sub: ['automation with team tokens', 'Paperclip only'], tone: 'client' });
  d.node({ id: 'corp', x: 40, y: 360, w: 260, title: 'Corporate network', sub: ['reaches private endpoints only'], tone: 'neutral' });

  // Entry points
  d.node({ id: 'pub', x: 380, y: 140, w: 240, title: 'Public ALB + WAF', sub: ['public_base_domain', 'internet-facing'], tone: 'aws' });
  d.node({ id: 'prv', x: 380, y: 330, w: 240, title: 'Internal ALB', sub: ['private_base_domain', 'VPC and corporate only'], tone: 'aws' });
  d.node({ id: 'edge', x: 680, y: 220, w: 270, title: 'afs-edge', sub: ['host → team and level', 'wrong level → 404', 'SSO, RBAC, scan, limits', 'only target: orchestration agent'], tone: 'api', badge: '-restapi' });

  // Team namespace
  d.group({ x: 1000, y: 96, w: 480, h: 470, label: 'Team namespace afs-t-<team>', tone: 'k8s', sub: 'created with the team; default-deny network' });
  d.node({ id: 'orch', x: 1025, y: 160, w: 430, h: 150, title: '◆ Orchestration agent (one per team)', sub: ['orchestration runtime (harness hidden on screens)', 'collaboration tool: Paperclip AI (default) or Buzz', 'Web UI and Web API: Off · Private · Public', 'Buzz: both surfaces N/A (no browser client or REST API)'], tone: 'api' });
  d.node({ id: 'w1', x: 1025, y: 360, w: 200, title: 'Worker agent', sub: ['cluster-internal only'], tone: 'k8s' });
  d.node({ id: 'w2', x: 1255, y: 360, w: 200, title: 'Worker agent', sub: ['cluster-internal only'], tone: 'k8s' });
  d.text({ x: 1240, y: 470, lines: ['Workers join the collaboration tool', 'through AFS_COLLAB_TOOL and AFS_COLLAB_URL'], anchor: 'middle', size: 12, color: '#326ce5' });

  // Exposure rule
  d.node({ id: 'rule', x: 380, y: 470, w: 570, title: 'Effective level per surface', sub: ['min(team-admin choice, service-admin team limit, service switches, tool support)', 'refusal reasons: team_limit · service_switch_* · base_domain_unset · tool_not_supported'], tone: 'neutral' });

  // Model admission
  d.group({ x: 20, y: 610, w: 1460, h: 230, label: 'Model admission at afs-gateway', tone: 'api', sub: 'service ∩ team ∩ agent (∩ pool), and the model must have an approved price; fails closed' });
  d.node({ id: 'svc', x: 45, y: 690, w: 270, title: 'Service models', sub: ['service admin: All or selected', 'extra-terms models approved above AFS'], tone: 'neutral' });
  d.node({ id: 'team', x: 375, y: 690, w: 270, title: 'Team models', sub: ['service admin narrows (default All)'], tone: 'neutral' });
  d.node({ id: 'agent', x: 705, y: 690, w: 270, title: 'Agent models + default', sub: ['team-admin narrows per agent', 'AFS_DEFAULT_MODEL · AFS_MODELS'], tone: 'neutral' });
  d.node({ id: 'gw', x: 1035, y: 690, w: 200, title: 'afs-gateway', sub: ['reserve → invoke → settle'], tone: 'api', badge: '-restapi' });
  d.node({ id: 'br', x: 1275, y: 690, w: 185, title: 'Amazon Bedrock', sub: ['team inference profile'], tone: 'aws' });
  d.text({ x: 1135, y: 815, lines: 'Refused: model_not_enabled_for_service · _for_team · _for_agent · model_not_priced', anchor: 'middle', size: 12, color: '#d13212' });

  d.edge('web', 'pub', { tone: 'client', label: 'HTTPS' });
  d.edge('apic', 'pub', { from: 'r', to: 'l', tf: 0.8, tone: 'client' });
  d.edge('corp', 'prv', { tone: 'neutral', label: 'HTTPS' });
  d.edge('pub', 'edge', { from: 'r', to: 'l', tf: 0.3, tone: 'aws' });
  d.edge('prv', 'edge', { from: 'r', to: 'l', tf: 0.7, tone: 'aws' });
  d.edge('edge', 'orch', { from: 'r', to: 'l', tone: 'api' });
  d.edge('orch', 'w1', { from: 'b', to: 't', ff: 0.25, tone: 'k8s' });
  d.edge('orch', 'w2', { from: 'b', to: 't', ff: 0.75, tone: 'k8s' });
  d.edge('svc', 'team', { tone: 'neutral', label: '⊇' });
  d.edge('team', 'agent', { tone: 'neutral', label: '⊇' });
  d.edge('agent', 'gw', { tone: 'api', label: 'admit' });
  d.edge('gw', 'br', { tone: 'api' });
};
