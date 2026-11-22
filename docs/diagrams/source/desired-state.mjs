// How a change flows: API transaction, change feed, reconcile loop, status back to clients.
export default (d) => {
  d.size(1400, 680);
  d.title('Desired state and reconciliation', 'The API never touches Kubernetes. It commits intent; the reconciler converges the world to it and reports back.');

  d.node({ id: 'user', x: 30, y: 130, w: 200, title: 'Team admin', sub: ['console, afs CLI or SDK', 'PUT …/agents/reviewer', 'If-Match: "7"'], tone: 'client' });
  d.group({ x: 270, y: 100, w: 300, h: 340, label: 'afs-api: one transaction', tone: 'api' });
  d.node({ id: 'authz', x: 290, y: 150, w: 260, title: 'Authorize', sub: ['agents:write on team_…'], tone: 'api' });
  d.node({ id: 'row', x: 290, y: 240, w: 260, title: 'Write desired-state row', sub: ['version 7 → 8, generation +1'], tone: 'api' });
  d.node({ id: 'aud', x: 290, y: 330, w: 260, h: 90, title: 'audit_log + outbox_events', sub: ['+ config_revisions snapshot', '(trigger)'], tone: 'api' });

  d.node({ id: 'db', x: 620, y: 220, w: 220, h: 130, title: 'PostgreSQL', sub: ['NOTIFY afs_desired_state', '"agents:team_…:agt_…"'], tone: 'data', shape: 'db' });

  d.group({ x: 890, y: 100, w: 480, h: 340, label: 'afs-reconciler (leader)', tone: 'api' });
  d.node({ id: 'q', x: 910, y: 150, w: 210, title: 'Work queue', sub: ['notify, 30 s poll of', 'generation ≠ observed,', '10 min full resync'], tone: 'api' });
  d.node({ id: 'conv', x: 1140, y: 150, w: 210, title: 'Converge', sub: ['render, apply, compare', 'revert drift (audited)'], tone: 'api' });
  d.node({ id: 'k8s', x: 910, y: 300, w: 210, title: 'EKS', sub: ['namespace, StatefulSet,', 'policies, ExternalSecrets'], tone: 'k8s' });
  d.node({ id: 'aws', x: 1140, y: 300, w: 210, title: 'AWS', sub: ['IAM roles, Pod Identity,', 'profiles, secrets, logs'], tone: 'aws' });

  d.node({ id: 'status', x: 620, y: 480, w: 220, title: 'resource_status', sub: ['observedGeneration 8', 'phase Ready, conditions'], tone: 'data' });
  d.node({ id: 'bus', x: 910, y: 480, w: 210, title: 'EventBridge', sub: ['agent.updated …'], tone: 'aws' });
  d.node({ id: 'poll', x: 30, y: 480, w: 200, title: '--wait / waitFor', sub: ['CLI and SDK poll status', 'console shows dot + word'], tone: 'client' });

  d.edge('user', 'authz', { tf: 0.5, tone: 'client', label: 'HTTPS', lx: 250, ly: 150 });
  d.edge('authz', 'row', { tone: 'api' });
  d.edge('row', 'aud', { tone: 'api' });
  d.edge('row', 'db', { tone: 'api', label: 'COMMIT', lx: 595, ly: 238 });
  d.edge('db', 'q', { from: 't', to: 'l', ff: 0.5, tf: 0.3, tone: 'data', label: 'LISTEN', lx: 730, ly: 185 });
  d.edge('q', 'conv', { tone: 'api' });
  d.edge('conv', 'k8s', { from: 'b', to: 't', ff: 0.25, tf: 0.75, tone: 'k8s', mid: 270 });
  d.edge('conv', 'aws', { from: 'b', to: 't', tone: 'aws' });
  d.edge('conv', 'status', { from: 'r', to: 'b', ff: 0.8, via: [[1385, 212], [1385, 610], [730, 610]], tone: 'data', label: 'write status', lx: 1250, ly: 610 });
  d.edge('db', 'bus', { from: 'r', to: 'l', ff: 0.9, via: [[875, 337], [875, 520]], tone: 'aws', label: 'outbox', lx: 875, ly: 455 });
  d.edge('status', 'poll', { from: 'l', to: 'r', tone: 'client', label: 'GET … status', lx: 425, ly: 520 });
  d.text({ x: 30, y: 652, lines: 'Optimistic concurrency: a stale If-Match gets 412 PreconditionFailed. A restored database plus a new cluster converge with no manual steps.', size: 12.5 });
};
