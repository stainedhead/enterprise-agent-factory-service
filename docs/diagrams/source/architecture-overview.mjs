// System context: clients, control plane, database, EKS tenancy and AWS services.
export default (d) => {
  d.size(1500, 930);
  d.title('Architecture overview', 'Clients call one API; the API writes desired state; the reconciler makes EKS and AWS match it; the gateway meters every model call.');

  // Identity provider and clients
  d.node({ id: 'idp', x: 30, y: 96, w: 250, title: 'Enterprise IdP (OIDC)', sub: ['Okta (default) or Entra ID', 'groups → role bindings'], tone: 'neutral' });
  d.group({ x: 20, y: 200, w: 270, h: 440, label: 'Clients', tone: 'client', sub: 'UX only; never the access decision' });
  d.node({ id: 'console', x: 40, y: 262, w: 230, title: 'Web console', sub: ['React 19 on @afs/sdk', 'OIDC code + PKCE'], tone: 'client', badge: '-website' });
  d.node({ id: 'cli', x: 40, y: 384, w: 230, title: 'afs CLI', sub: ['AWS CLI conventions', 'SSO device flow, API keys'], tone: 'client', badge: '-cli' });
  d.node({ id: 'sdk', x: 40, y: 506, w: 230, title: '@afs/sdk', sub: ['pipelines and automation', 'TypeScript, zero deps'], tone: 'client', badge: '-website' });

  // Control plane
  d.group({ x: 320, y: 200, w: 830, h: 440, label: 'Control plane', tone: 'api', sub: '-restapi, Go 1.27' });
  d.node({ id: 'api', x: 345, y: 300, w: 200, title: 'afs-api', sub: ['REST /v1 · OpenAPI 3.1', 'RBAC on every route', 'audit + outbox per write'], tone: 'api' });
  d.node({ id: 'db', x: 630, y: 285, w: 230, h: 130, title: 'RDS PostgreSQL 17', sub: ['desired state · audit', 'usage ledger · outbox', 'row-level security'], tone: 'data', shape: 'db', badge: '-db' });
  d.node({ id: 'rec', x: 930, y: 300, w: 200, title: 'afs-reconciler', sub: ['leader-elected', 'converges namespaces,', 'agents, pools, IAM, secrets'], tone: 'api' });
  d.node({ id: 'bill', x: 345, y: 500, w: 200, title: 'afs-billing', sub: ['daily CUR reconciliation', 'price proposals, reports'], tone: 'api' });
  d.node({ id: 'bus', x: 630, y: 500, w: 230, title: 'EventBridge afs-events', sub: ['outbox, at least once'], tone: 'aws' });
  d.node({ id: 'notify', x: 920, y: 500, w: 150, title: 'Notifications', sub: ['Slack · email', 'Jira · webhook'], tone: 'neutral' });

  // Orchestration entry: the only path from outside the cluster, public or private per surface
  d.node({ id: 'alb', x: 600, y: 96, w: 200, title: 'Public / internal ALB', sub: ['public: internet + WAF', 'private: VPC + corporate'], tone: 'aws' });
  d.node({ id: 'edge', x: 850, y: 96, w: 280, title: 'afs-edge', sub: ['host → team and level, SSO, authz', 'scan, limits → orchestration agent'], tone: 'api', badge: '-restapi' });

  // EKS
  d.group({ x: 1180, y: 96, w: 300, h: 560, label: 'EKS cluster', tone: 'k8s', sub: 'Agentic Teammates runtime (CRDs)' });
  d.node({ id: 'ns1', x: 1200, y: 150, w: 260, title: 'ns afs-t-payments', sub: ['◆ orchestration agent + workers', 'one agent = one pod + EBS', 'default-deny network'], tone: 'k8s' });
  d.node({ id: 'ns2', x: 1200, y: 272, w: 260, title: 'ns afs-t-search', sub: ['long-running dev team'], tone: 'k8s' });
  d.node({ id: 'ns3', x: 1200, y: 360, w: 260, title: 'ns afs-t-cve-2026-…', sub: ['ephemeral swarm: pools', 'of workers, lifetime budget'], tone: 'k8s' });
  d.node({ id: 'gw', x: 1200, y: 530, w: 260, title: 'afs-gateway', sub: ['ns afs-system · multi-AZ', 'reserve → invoke → settle'], tone: 'api', badge: '-restapi' });

  // AWS
  d.group({ x: 320, y: 680, w: 1160, h: 210, label: 'AWS account', tone: 'aws', });
  d.text({ x: 1460, y: 874, lines: 'Every resource is tagged afs-team-id and afs-agent-id', anchor: 'end', size: 12, color: '#7d3cff' });
  d.node({ id: 'cur', x: 345, y: 750, w: 200, title: 'CUR 2.0 + Athena', sub: ['billed actuals', 'split cost by namespace'], tone: 'aws' });
  d.node({ id: 'logs', x: 565, y: 750, w: 175, title: 'CloudWatch / S3', sub: ['per-team log delivery'], tone: 'aws' });
  d.node({ id: 'sm', x: 760, y: 750, w: 170, title: 'Secrets Manager', sub: ['managed paths', 'synced by ESO'], tone: 'aws' });
  d.node({ id: 'iam', x: 950, y: 750, w: 200, title: 'IAM + Pod Identity', sub: ['role per team or agent', 'ABAC + boundary'], tone: 'aws' });
  d.node({ id: 'bedrock', x: 1200, y: 750, w: 260, title: 'Amazon Bedrock', sub: ['inference profile per team', 'and model, via VPC endpoint'], tone: 'aws' });

  d.edge('alb', 'edge', { tone: 'aws', label: 'HTTPS' });
  d.edge('edge', 'ns1', { from: 'r', to: 'l', ff: 0.3, tone: 'api' });
  d.edge('edge', 'db', { from: 'b', to: 't', ff: 0.15, tf: 0.8, tone: 'data', dashed: true, label: 'routes (afs_edge)', lx: 905, ly: 215 });
  d.edge('idp', 'api', { from: 'r', to: 't', tf: 0.8, label: 'JWT (JWKS)', dashed: true });
  d.edge('console', 'api', { tf: 0.25, label: 'HTTPS /v1', tone: 'client', lx: 305, ly: 455 });
  d.edge('cli', 'api', { tf: 0.5, tone: 'client' });
  d.edge('sdk', 'api', { tf: 0.75, tone: 'client' });
  d.edge('api', 'db', { label: ['1 tx: row,', 'audit, outbox'], tone: 'api', lx: 588, ly: 318 });
  d.edge('db', 'rec', { tf: 0.5, label: ['NOTIFY', '+ poll'], tone: 'data', lx: 895, ly: 318 });
  d.edge('rec', 'ns1', { from: 'r', to: 'l', tone: 'api', label: 'K8s API', lx: 1155, ly: 270 });
  d.edge('rec', 'ns2', { from: 'r', to: 'l', tone: 'api' });
  d.edge('rec', 'ns3', { from: 'r', to: 'l', tone: 'api' });
  d.edge('db', 'bus', { from: 'b', to: 't', tone: 'aws', label: 'publish outbox' });
  d.edge('bus', 'notify', { tone: 'aws' });
  d.edge('rec', 'iam', { from: 'b', to: 't', ff: 0.9, tf: 0.9, tone: 'api', dashed: true, label: 'AWS APIs', lx: 1110, ly: 645 });
  d.edge('ns3', 'gw', { from: 'b', to: 't', tone: 'k8s', label: 'model calls', lx: 1330, ly: 487 });
  d.edge('gw', 'bedrock', { from: 'b', to: 't', tone: 'api', label: 'team Bedrock role', lx: 1330, ly: 645 });
  d.edge('gw', 'db', { from: 'l', to: 'r', ff: 0.75, tf: 0.82, via: [[895, 600], [895, 392]], tone: 'data', dashed: true, label: 'reserve / settle spend', lx: 1080, ly: 600 });
  d.edge('cur', 'bill', { from: 't', to: 'b', ff: 0.6, tf: 0.6, tone: 'aws', dashed: true, label: 'Athena', lx: 465, ly: 630 });
  d.edge('bill', 'db', { from: 'r', to: 'b', ff: 0.25, tf: 0.12, via: [[600, 520], [600, 440], [658, 440]], tone: 'api' });
};
