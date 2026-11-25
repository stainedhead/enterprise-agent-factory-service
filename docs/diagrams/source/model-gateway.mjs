// Release 1.2.0: a model call on a route through the team gateway, metering and caps, and the provider bill reconcile.
export default (d) => {
  d.size(1400, 1090);
  d.title('Team model gateway', 'Agents call a route by name. The team gateway admits, reserves, forwards with the route credential and settles; billing reconciles against each provider.');
  d.seq({
    x0: 30, y0: 96, colW: 222, boxW: 196, rowH: 44,
    participants: [
      { id: 'agent', title: 'Agent pod', sub: 'any OpenAI SDK', tone: 'k8s' },
      { id: 'gw', title: 'Team gateway', sub: 'afs-gateway in afs-t-<team>', tone: 'api' },
      { id: 'db', title: 'PostgreSQL', sub: 'routes, spend, ledger', tone: 'data' },
      { id: 'pv', title: 'Route upstream', sub: 'provider or internal', tone: 'neutral' },
      { id: 'rec', title: 'afs-reconciler', sub: 'leader', tone: 'api' },
      { id: 'bill', title: 'afs-billing', sub: 'CronJobs', tone: 'api' },
    ],
    steps: [
      { note: ['per_namespace team: the reconciler renders the team gateway, route-host egress', 'from the gateway only, and AFS_LLM_*, OPENAI_BASE_URL, /etc/afs/llm-routes.json for agents'], over: ['agent', 'rec'], tone: 'k8s' },
      { from: 'agent', to: 'gw', label: 'POST /r/<route>/v1/chat/completions', tone: 'k8s' },
      { from: 'gw', to: 'gw', label: 'caller = source pod IP; or /openai/v1 with model <route>/<model>', tone: 'api' },
      { from: 'gw', to: 'db', label: 'route_admission (cached 60 s, change feed)', tone: 'api' },
      { frame: 'if not admitted', over: ['agent', 'gw', 'db'], tone: 'danger' },
      { from: 'gw', to: 'agent', label: '403 provider_disabled · route_not_enabled_* · model_not_priced', dashed: true, tone: 'danger' },
      { endFrame: true },
      { from: 'gw', to: 'db', label: 'reserve_spend_held(output cap × route price)', tone: 'api' },
      { frame: 'if no budget left', over: ['agent', 'gw', 'db'], tone: 'danger' },
      { from: 'gw', to: 'agent', label: '402 BudgetExceeded (no retry)', dashed: true, tone: 'danger' },
      { endFrame: true },
      { from: 'gw', to: 'pv', label: 'forward: route key or federated token, cap written in', tone: 'api' },
      { from: 'pv', to: 'gw', label: 'response + usage (SSE, include_usage)', dashed: true, tone: 'neutral' },
      { from: 'gw', to: 'db', label: 'settle(tokens × price, or usage.cost if larger) + usage row', tone: 'api' },
      { from: 'gw', to: 'agent', label: 'response (stream passes through)', dashed: true, tone: 'api' },
      { note: ['upstream 429 → 429 · 5xx → 502 · timeout → 504 · no credential → 503: reservation released', 'Bedrock route /r/bedrock: Chat Completions → Converse on the team inference profile'], over: ['gw', 'pv'], tone: 'data' },
      { frame: 'daily and monthly', over: ['db', 'pv', 'rec', 'bill'], tone: 'aws' },
      { from: 'bill', to: 'pv', label: 'route-pull: provider costs (OpenAI, OpenRouter, Azure, Google)', tone: 'api' },
      { from: 'bill', to: 'db', label: 'route-statements · route-capacity · route-price-sync proposals', tone: 'api' },
      { from: 'bill', to: 'db', label: 'cost_daily route rows; variance → cost.variance_detected', tone: 'api' },
      { endFrame: true },
    ],
  });
};
