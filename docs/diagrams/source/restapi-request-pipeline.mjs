// What happens to one mutating request in afs-api.
export default (d) => {
  d.size(1400, 520);
  d.title('afs-api request pipeline', 'Every /v1 route declares a permission. A mutation commits its row, audit record and outbox event together, or nothing.');
  const steps = [
    ['m', 'Metrics', ['RED per route']],
    ['an', 'Authenticate', ['OIDC JWT, API key', 'or workload token']],
    ['rl', 'Rate limit', ['+ CORS']],
    ['im', 'If-Match', ['required on updates']],
    ['az', 'Authorize', ['route permission', '+ teamId from path']],
    ['sg', 'Suspended guard', ['team state']],
  ];
  steps.forEach(([id, t, s], i) => d.node({ id, x: 30 + i * 225, y: 120, w: 195, h: 92, title: t, sub: s, tone: id === 'az' ? 'danger' : 'client' }));
  for (let i = 0; i < steps.length - 1; i++) d.edge(steps[i][0], steps[i + 1][0], { tone: 'client' });

  d.group({ x: 30, y: 260, w: 1340, h: 170, label: 'Use case: one database transaction as afs_app', tone: 'api', dashed: false });
  const tx = [
    ['t1', 'SET LOCAL', ['actor, team_ids,', 'service_admin']],
    ['t2', 'Claim Idempotency-Key', ['HMAC fingerprint']],
    ['t3', 'Write row', ['version check → 412', 'on mismatch']],
    ['t4', 'audit_log', ['who, what, request id']],
    ['t5', 'outbox_events', ['when the contract', 'names an event']],
    ['t6', 'Store response, COMMIT', ['replay-safe']],
  ];
  tx.forEach(([id, t, s], i) => d.node({ id, x: 45 + i * 222, y: 310, w: 200, h: 92, title: t, sub: s, tone: 'api' }));
  for (let i = 0; i < tx.length - 1; i++) d.edge(tx[i][0], tx[i + 1][0], { tone: 'api' });
  d.edge('sg', 't1', { from: 'b', to: 'l', via: [[1252, 240], [16, 240], [16, 356]], tone: 'api' });
  d.text({ x: 30, y: 470, lines: ['Denied requests are audited too. Errors are {code, message, requestId}; secrets and Authorization headers are redacted from logs.', 'afs-api calls AWS only to write secret values (Secrets Manager) and never calls Kubernetes.'], size: 12.5 });
};
