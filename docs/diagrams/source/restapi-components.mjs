// The four binaries and the clean-architecture layers they share.
export default (d) => {
  d.size(1400, 740);
  d.title('-restapi: binaries and layers', 'Four binaries share one domain and use-case core. Dependencies point inward; cmd/* is the only place adapters are wired.');
  const bins = [['api', 'afs-api', 'REST /v1, RBAC, audit'], ['rec', 'afs-reconciler', 'EKS + AWS convergence'], ['gw', 'afs-gateway', 'Bedrock metering'], ['bill', 'afs-billing', 'CUR, prices, reports']];
  bins.forEach(([id, t, s], i) => d.node({ id, x: 40 + i * 335, y: 110, w: 300, title: t, sub: [`cmd/${t}`, s], tone: 'api', badge: 'binary' }));

  d.group({ x: 30, y: 230, w: 1340, h: 170, label: 'Adapters (internal/adapter)', tone: 'neutral', dashed: false });
  const ad = [['http', 'httpapi', 'routes, middleware,', 'error mapping'], ['pg', 'postgres', 'pgx repositories,', 'audit, outbox'], ['k8s', 'k8s', 'client-go, CRDs,', 'policies'], ['aws', 'aws', 'IAM, Pod Identity, SM,', 'Bedrock, EventBridge, Athena']];
  ad.forEach(([id, t, a, b], i) => d.node({ id, x: 50 + i * 330, y: 285, w: 300, title: t, sub: [a, b], tone: 'neutral' }));

  d.group({ x: 30, y: 430, w: 1340, h: 140, label: 'internal/usecase', tone: 'client', dashed: false, sub: 'use cases and ports (interfaces); imports domain and authz only' });
  d.node({ id: 'uc', x: 50, y: 488, w: 600, h: 64, title: 'teams · agents · secrets · budgets · reports · work orders …', sub: ['ports: repositories, cluster, cloud, clock, ids'], tone: 'client' });
  d.node({ id: 'authz', x: 980, y: 488, w: 370, h: 64, title: 'internal/authz', sub: ['Authorize(principal, permission, team)'], tone: 'danger', badge: 'only access decision' });

  d.group({ x: 30, y: 600, w: 1340, h: 70, label: 'internal/domain', tone: 'data', dashed: false, sub: 'entities and invariants; standard library only' });
  [190, 525, 860, 1195].forEach((x) => d.arrow({ x1: x, y1: 207, x2: x, y2: 229, tone: 'api' }));
  [200, 530, 860, 1190].forEach((x) => d.arrow({ x1: x, y1: 367, x2: x, y2: 429, tone: 'neutral', label: x === 530 ? 'implement ports' : undefined }));
  d.arrow({ x1: 600, y1: 571, x2: 600, y2: 599, tone: 'client' });
  d.text({ x: 40, y: 220, lines: '', size: 1 });
  d.text({ x: 1360, y: 700, lines: 'golangci-lint and tests enforce the dependency rule; domain, usecase and authz hold ≥ 90 % coverage.', anchor: 'end', size: 12 });
};
