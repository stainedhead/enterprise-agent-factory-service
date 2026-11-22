// Human identity and roles on the left; agent identity and AWS access on the right.
export default (d) => {
  d.size(1400, 700);
  d.title('Identity and access', 'People sign in through the enterprise IdP and get a role per team. Agents get a Kubernetes identity and an IAM role, never a person\'s.');

  d.group({ x: 30, y: 100, w: 640, h: 560, label: 'People and automation', tone: 'client' });
  d.node({ id: 'idp', x: 55, y: 150, w: 270, title: 'Okta or Entra ID', sub: ['service admins enable providers', 'each team picks one'], tone: 'neutral' });
  d.node({ id: 'cred', x: 55, y: 260, w: 270, title: 'Credentials', sub: ['console: code + PKCE', 'CLI: device flow (afs sso login)', 'pipelines: API keys, ≤ 90 days'], tone: 'client' });
  d.node({ id: 'api', x: 375, y: 260, w: 270, title: 'afs-api', sub: ['validate JWT against JWKS', 'resolve role bindings', 'Authorize(principal, perm, team)'], tone: 'api' });
  d.text({ x: 55, y: 395, lines: 'ROLES, BOUND PER TEAM', size: 12, bold: true, color: '#0972d3' });
  d.node({ id: 'sa', x: 55, y: 410, w: 135, h: 92, title: 'service_admin', sub: ['everything'], tone: 'dark' });
  d.node({ id: 'ta', x: 200, y: 410, w: 135, h: 92, title: 'team_admin', sub: ['one team'], tone: 'client' });
  d.node({ id: 'tv', x: 345, y: 410, w: 135, h: 92, title: 'team_viewer', sub: ['read only,', 'no secret values'], tone: 'client' });
  d.node({ id: 'so', x: 490, y: 410, w: 155, h: 92, title: 'security_operator', sub: ['work orders only'], tone: 'danger' });
  d.text({ x: 55, y: 540, lines: ['Bindings go to a user or an IdP group, per team.', 'GET /v1/me returns effective permissions so clients can', 'disable controls; the API is still the only decision point.', 'Row-level security in PostgreSQL is the second wall.'], size: 12.5 });

  d.group({ x: 710, y: 100, w: 660, h: 560, label: 'Agents', tone: 'k8s' });
  d.node({ id: 'ksa', x: 735, y: 150, w: 280, title: 'ServiceAccount agent-<name>', sub: ['in afs-t-<team>, no RBAC'], tone: 'k8s' });
  d.node({ id: 'pi', x: 735, y: 260, w: 280, title: 'EKS Pod Identity', sub: ['session tags: namespace,', 'service account, pod'], tone: 'aws' });
  d.node({ id: 'shared', x: 735, y: 380, w: 280, title: 'Team role afs-<team id>', sub: ['default: shared by the team', 'ABAC on afs-team-id'], tone: 'aws' });
  d.node({ id: 'ded', x: 1060, y: 380, w: 290, title: 'Dedicated role afs-<agent id>', sub: ['least privilege per agent', 'team permissions boundary'], tone: 'aws' });
  d.node({ id: 'xacct', x: 1060, y: 520, w: 290, title: 'Cross-account role links', sub: ['allowed-accounts glob filter', 'external ID; profile in /etc/afs/aws'], tone: 'aws' });
  d.node({ id: 'gwid', x: 1100, y: 150, w: 250, title: 'Gateway identity', sub: ['source pod IP via Cilium', 'optional projected token'], tone: 'api' });
  d.node({ id: 'ext', x: 735, y: 520, w: 280, title: 'External identities', sub: ['GitHub App, bot accounts', 'credentials as team secrets'], tone: 'neutral' });

  d.edge('idp', 'cred', { tone: 'client', label: 'OIDC' });
  d.edge('cred', 'api', { tone: 'client', label: 'Bearer' });
  d.edge('ksa', 'pi', { tone: 'k8s' });
  d.edge('pi', 'shared', { tone: 'aws', label: 'team_shared' });
  d.edge('pi', 'ded', { from: 'r', to: 't', tone: 'aws', label: 'dedicated' });
  d.edge('ded', 'xacct', { tone: 'aws', label: 'sts:AssumeRole' });
  d.edge('ksa', 'gwid', { tone: 'api', label: 'model calls', lx: 1057, ly: 140 });
};
