// The five repositories, what each owns, and the contracts between them.
export default (d) => {
  d.size(1400, 600);
  d.title('Repositories and contracts', 'Five repositories, one product. Each boundary is a written contract in the root repository\'s docs/contracts.');

  d.node({ id: 'root', x: 520, y: 100, w: 360, title: 'enterprise-agent-factory-service', sub: ['root: PRD, solution design, ADRs,', 'contracts, UI mockups, cross-repo specs'], tone: 'dark' });
  d.node({ id: 'db', x: 30, y: 300, w: 270, title: '-db', sub: ['PostgreSQL 17 schema, 19 migrations', 'roles, row-level security', 'Go module + afs-migrate'], tone: 'data' });
  d.node({ id: 'api', x: 440, y: 300, w: 300, title: '-restapi', sub: ['afs-api · afs-reconciler', 'afs-gateway · afs-billing', 'owns api/openapi.yaml'], tone: 'api' });
  d.node({ id: 'cli', x: 820, y: 240, w: 260, title: '-cli', sub: ['afs, AWS CLI conventions', '180 operations, 5 outputs'], tone: 'client' });
  d.node({ id: 'web', x: 820, y: 380, w: 260, title: '-website', sub: ['@afs/sdk (GitHub Packages)', 'web console, 33 screens'], tone: 'client' });
  d.node({ id: 'agents', x: 1140, y: 300, w: 230, title: 'Agents', sub: ['Agentic Teammates runtime', 'in team namespaces'], tone: 'k8s' });

  d.edge('db', 'api', { tone: 'data', label: ['database contract', 'Go module at a tag'], lx: 370, ly: 360 });
  d.edge('api', 'cli', { from: 'r', to: 'l', tone: 'client', label: 'API contract', lx: 780, ly: 357 });
  d.edge('api', 'web', { from: 'r', to: 'l', tone: 'client' });
  d.edge('api', 'agents', { from: 'b', to: 'b', via: [[590, 520], [1255, 520]], tone: 'k8s', label: 'gateway contract (Bedrock and Anthropic compatible)', lx: 900, ly: 520 });
  d.edge('root', 'db', { from: 'b', to: 't', ff: 0.15, tone: 'neutral', dashed: true });
  d.edge('root', 'api', { from: 'b', to: 't', ff: 0.5, tf: 0.6, tone: 'neutral', dashed: true, label: 'specs + contracts', lx: 700, ly: 240 });
  d.edge('root', 'cli', { from: 'b', to: 't', ff: 0.85, tone: 'neutral', dashed: true });
};
