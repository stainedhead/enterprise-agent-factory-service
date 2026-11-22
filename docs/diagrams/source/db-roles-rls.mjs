// Database roles per service and how row-level security scopes afs_app to the caller's teams.
export default (d) => {
  d.size(1400, 640);
  d.title('Roles and row-level security', 'Each service connects as its own least-privilege role. The API role sees only the caller\'s teams, enforced inside PostgreSQL.');
  const svc = [
    ['api', 'afs-api', 'afs_app', 'desired state read/write, audit + outbox insert; RLS applies', 'client'],
    ['rec', 'afs-reconciler', 'afs_reconciler', 'read all; write status, lifecycle, outbox publication', 'api'],
    ['gw', 'afs-gateway', 'afs_gateway', 'read budgets and prices; reserve, settle, insert usage', 'api'],
    ['bill', 'afs-billing', 'afs_billing', 'write daily costs and reconciliations', 'api'],
    ['ro', 'reporting, support', 'afs_readonly', 'read all except key hashes and audit payloads', 'neutral'],
  ];
  svc.forEach(([id, s, role, what, tone], i) => {
    const y = 110 + i * 96;
    d.node({ id: `s_${id}`, x: 30, y, w: 190, h: 72, title: s, tone });
    d.node({ id: `r_${id}`, x: 290, y, w: 400, h: 72, title: role, sub: [what], tone: 'data' });
    d.edge(`s_${id}`, `r_${id}`, { tone: 'data' });
  });
  d.node({ id: 'set', x: 760, y: 110, w: 610, title: 'Per transaction, afs-api runs SET LOCAL', sub: ['afs.actor = \'usr_…\'   afs.team_ids = \'team_A,team_B\'', 'afs.service_admin = off   afs.security_operator = off'], tone: 'client', mono: true });
  d.node({ id: 'pol', x: 760, y: 250, w: 610, title: 'Policy on every team-owned table', sub: ['USING (afs.caller_sees_team(team_id))', 'WITH CHECK (afs.caller_sees_team(team_id))'], tone: 'data', mono: true });
  d.node({ id: 'ok', x: 760, y: 390, w: 290, title: 'team_A rows', sub: ['visible and writable'], tone: 'data' });
  d.node({ id: 'no', x: 1080, y: 390, w: 290, title: 'team_C rows', sub: ['invisible; writes change nothing'], tone: 'danger' });
  d.edge('r_api', 'set', { from: 'r', to: 'l', tone: 'client' });
  d.edge('set', 'pol', { tone: 'data' });
  d.edge('pol', 'ok', { from: 'b', to: 't', ff: 0.24, tone: 'data' });
  d.edge('pol', 'no', { from: 'b', to: 't', ff: 0.76, tone: 'danger', dashed: true });
  d.text({ x: 760, y: 520, lines: ['afs.audit_log rejects UPDATE, DELETE and TRUNCATE by trigger.', 'TestCrossTeamWritesChangeNothing seeds other teams\' rows in every', 'team-owned table and proves they cannot be read or changed.'], size: 12.5 });
};
