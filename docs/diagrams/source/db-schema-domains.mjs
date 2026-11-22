// The afs schema grouped by domain. Every team-owned table carries team_id and row-level security.
export default (d) => {
  d.size(1400, 760);
  d.title('Schema by domain (schema afs, migrations 000001–000019)', 'Every team-owned table carries team_id, composite (team_id, id) foreign keys and a row-level security policy.');
  const box = (id, x, y, title, tables, tone, badge) =>
    d.node({ id, x, y, w: 320, h: 34 + 18 + tables.length * 17 + 10, title, sub: tables, tone, mono: true, badge });
  box('ten', 30, 110, 'Tenancy and access', ['teams, users, role_bindings', 'api_keys (hash only)', 'identity_providers, service_settings'], 'client');
  box('agt', 370, 110, 'Agents', ['agents, agent_templates', 'storage_classes', 'agent_volume_snapshots', 'agent_config_values', 'namespace_config_values'], 'k8s');
  box('idn', 710, 110, 'Identity and AWS access', ['agent_identities', 'agent_role_links, pool_role_links', 'org_aws_accounts'], 'aws');
  box('sec', 1050, 110, 'Secrets (references only)', ['secrets (ARN + metadata)', 'agent_secret_bindings', 'pool_secret_bindings'], 'danger', 'no values');

  box('ext', 30, 290, 'External systems and egress', ['external_systems', 'external_system_optouts', 'team_egress_rules'], 'neutral');
  box('mon', 370, 290, 'Models and budgets', ['models, model_prices', 'model_price_proposals, team_models', 'budgets, spend_counters', 'spend_reservations', 'budget_threshold_events'], 'api', 'hot path');
  box('use', 710, 290, 'Usage, cost and reporting', ['usage_events (monthly partitions)', 'cost_daily, cost_reconciliations', 'agent_activity, external_traffic', 'tag_sets, service_tags, team_tags', 'cost_allocation_tag_status', 'report_schedules'], 'data');
  box('swm', 1050, 290, 'Swarms and work orders', ['swarm_stages, agent_pools', 'pool_handoffs, pool_config_values', 'swarm_templates', 'work_orders, work_order_repos', 'work_order_notifications'], 'k8s');

  box('del', 30, 500, 'Delivery', ['log_destinations', 'notification_channels'], 'neutral');
  box('rec', 370, 500, 'Reconcile status', ['resource_status', '(observed_generation,', ' phase, conditions)'], 'api');
  box('his', 710, 500, 'History and integrity', ['audit_log (append-only)', 'config_revisions', 'outbox_events, idempotency_keys', 'export_bundles'], 'dark');

  d.node({ id: 'fn', x: 1050, y: 500, w: 320, h: 150, title: 'Functions the services call', sub: ['reserve_spend_held, settle_reservation', 'ensure_spend_counter', 'authenticate_api_key, resolve_workload', 'instantiate_work_order_team', 'secret_path, account_allowed'], tone: 'data', mono: true });
  d.text({ x: 30, y: 690, lines: ['Conventions: prefixed ULID ids (team_…, agt_…) checked by afs.ulid_ok; desired-state tables carry version, generation, created/updated and a revision trigger;', 'money is numeric USD; enumerations are text + CHECK; every change NOTIFYs afs_desired_state at commit. Full dictionary: docs/data-model.md.'], size: 12.5 });
};
