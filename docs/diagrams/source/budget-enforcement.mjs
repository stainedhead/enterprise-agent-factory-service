// Near-real-time spend enforcement: reserve, invoke, settle; then daily reconciliation against CUR.
export default (d) => {
  d.size(1400, 1010);
  d.title('Budget enforcement', 'Every model call reserves its worst-case cost before it reaches Bedrock. A team can never spend past its hard cap.');
  d.seq({
    x0: 30, y0: 96, colW: 222, boxW: 196, rowH: 44,
    participants: [
      { id: 'agent', title: 'Agent pod', sub: 'standard Bedrock SDK', tone: 'k8s' },
      { id: 'gw', title: 'afs-gateway', sub: 'afs-system', tone: 'api' },
      { id: 'db', title: 'PostgreSQL', sub: 'spend counters, ledger', tone: 'data' },
      { id: 'br', title: 'Bedrock + IAM', sub: 'team inference profile', tone: 'aws' },
      { id: 'rec', title: 'afs-reconciler', sub: 'leader', tone: 'api' },
      { id: 'bill', title: 'afs-billing', sub: 'daily job', tone: 'api' },
    ],
    steps: [
      { from: 'agent', to: 'gw', label: 'POST /model/{id}/converse', tone: 'k8s' },
      { from: 'gw', to: 'gw', label: 'caller = source pod IP → team, agent', tone: 'api' },
      { from: 'gw', to: 'db', label: 'reserve_spend_held(worst case)', tone: 'api' },
      { frame: 'if no budget left', over: ['agent', 'gw', 'db'], tone: 'danger' },
      { from: 'db', to: 'gw', label: 'NULL', dashed: true, tone: 'danger' },
      { from: 'gw', to: 'agent', label: '402 BudgetExceeded (no retry)', dashed: true, tone: 'danger' },
      { endFrame: true },
      { frame: 'if the database is unreachable', over: ['agent', 'gw', 'db'], tone: 'danger' },
      { from: 'gw', to: 'agent', label: '503 within 2 s: fail closed', dashed: true, tone: 'danger' },
      { endFrame: true },
      { from: 'gw', to: 'br', label: 'invoke as team Bedrock role, tags as metadata', tone: 'api' },
      { from: 'br', to: 'gw', label: 'response + token usage', dashed: true, tone: 'aws' },
      { from: 'gw', to: 'db', label: 'settle_reservation(actual) + usage row', tone: 'api' },
      { from: 'gw', to: 'agent', label: 'response (stream passes through)', dashed: true, tone: 'api' },
      { note: ['thresholds 50 / 80 / 100 % → budget.threshold_crossed events', 'unsettled reservations expire after 15 min and are released'], over: ['db', 'rec'], tone: 'data' },
      { from: 'rec', to: 'br', label: 'at 100 %: attach explicit IAM deny', tone: 'api' },
      { frame: 'daily', over: ['db', 'br', 'rec', 'bill'], tone: 'aws' },
      { from: 'bill', to: 'br', label: 'read CUR 2.0 via Athena', tone: 'api' },
      { from: 'bill', to: 'db', label: 'cost_daily, reconciliation, variance alert', tone: 'api' },
      { endFrame: true },
    ],
  });
};
