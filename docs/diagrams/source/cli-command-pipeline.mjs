// How afs commands are generated from the contract and what one invocation does.
export default (d) => {
  d.size(1400, 560);
  d.title('afs: from contract to command', 'Commands are generated from the pinned OpenAPI contract, so the CLI cannot drift from the API. One operation is one API call.');
  d.group({ x: 30, y: 100, w: 1340, h: 150, label: 'Build time', tone: 'neutral', dashed: false });
  d.node({ id: 'oa', x: 50, y: 150, w: 270, title: 'api/openapi.yaml', sub: ['pinned snapshot + SOURCE', '(repo, commit, sha256)'], tone: 'data' });
  d.node({ id: 'gen', x: 380, y: 150, w: 270, title: 'tools/afsgen', sub: ['one descriptor per operation'], tone: 'neutral' });
  d.node({ id: 'reg', x: 710, y: 150, w: 290, title: 'Registry', sub: ['internal/spec + per-service', 'overrides, examples, columns'], tone: 'client' });
  d.node({ id: 'doc', x: 1060, y: 150, w: 290, title: 'tools/docgen', sub: ['user-docs/reference, help'], tone: 'neutral' });
  d.edge('oa', 'gen', { tone: 'data' }); d.edge('gen', 'reg', { tone: 'neutral' }); d.edge('reg', 'doc', { tone: 'neutral' });

  d.group({ x: 30, y: 280, w: 1340, h: 230, label: 'Run time: afs agents update-agent --team-id … --model …', tone: 'client', dashed: false });
  const run = [
    ['p', 'Parse', ['global options,', 'profile, env, config']],
    ['b', 'Build', ['flags +', '--cli-input-json']],
    ['su', 'Safe update', ['read version,', 'send If-Match']],
    ['c', 'Client', ['credential chain,', 'retries, idempotency']],
    ['pg', 'Paginate / wait', ['nextToken pages,', '--wait polling']],
    ['o', 'Render', ['json yaml table', 'text csv + --query']],
  ];
  run.forEach(([id, t, s], i) => d.node({ id, x: 45 + i * 222, y: 340, w: 196, h: 92, title: t, sub: s, tone: 'client' }));
  for (let i = 0; i < run.length - 1; i++) d.edge(run[i][0], run[i + 1][0], { tone: 'client' });
  d.edge('reg', 'p', { from: 'b', to: 'l', via: [[855, 266], [16, 266], [16, 386]], tone: 'client', dashed: true });
  d.text({ x: 45, y: 470, lines: ['Credentials: AFS_API_KEY → ~/.afs/credentials → SSO token cache (0600) → workload token. Tokens and keys are redacted, even with --debug.', 'Exit codes follow the AWS CLI: 0 success, 252 usage, 254 service error (AccessDenied, …), 255 other. Secret values come only from a file, stdin or a prompt.'], size: 12.5 });
};
