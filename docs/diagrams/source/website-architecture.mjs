// Console clean architecture on top of the generated SDK.
export default (d) => {
  d.size(1400, 660);
  d.title('-website: console and SDK', 'The console is layered so React never talks to the API directly. The SDK is generated from the same OpenAPI contract as the CLI.');
  d.group({ x: 30, y: 100, w: 820, h: 520, label: '@afs/console (apps/console)', tone: 'client', dashed: false });
  d.node({ id: 'main', x: 60, y: 150, w: 760, title: 'main/: composition root', sub: ['builds adapters, wires use cases, renders the app'], tone: 'dark' });
  d.node({ id: 'pres', x: 60, y: 260, w: 360, title: 'presentation/', sub: ['React 19 screens, shell, routes', 'TanStack Query around use cases', 'controls gated by can(…)'], tone: 'client' });
  d.node({ id: 'app', x: 60, y: 400, w: 360, title: 'application/', sub: ['use cases and ports'], tone: 'client' });
  d.node({ id: 'dom', x: 60, y: 510, w: 760, title: 'domain/', sub: ['entities, value objects, permission policy mirroring internal/authz'], tone: 'data' });
  d.node({ id: 'infra', x: 460, y: 260, w: 360, title: 'infrastructure/', sub: ['adapters implement the ports:', '@afs/sdk, OIDC session (memory', 'only), runtime config.json'], tone: 'neutral' });
  d.edge('pres', 'app', { tone: 'client' });
  d.edge('app', 'dom', { from: 'b', to: 't', ff: 0.5, tf: 0.237, tone: 'client' });
  d.edge('infra', 'app', { from: 'b', to: 'r', tone: 'neutral', label: 'implements' });
  d.edge('main', 'pres', { from: 'b', to: 't', ff: 0.316, tone: 'neutral' });
  d.edge('main', 'infra', { from: 'b', to: 't', ff: 0.842, tone: 'neutral' });

  d.group({ x: 890, y: 100, w: 480, h: 520, label: '@afs/sdk (packages/sdk)', tone: 'api', dashed: false, sub: 'published as @stainedhead/afs-sdk' });
  d.node({ id: 'contract', x: 915, y: 160, w: 430, title: 'contract/', sub: ['pinned openapi.yaml, permissions.json', 'operations.json, contract.lock.json'], tone: 'data' });
  d.node({ id: 'gen', x: 915, y: 270, w: 430, title: 'src/generated/', sub: ['182 operations in 41 resource modules'], tone: 'api' });
  d.node({ id: 'core', x: 915, y: 370, w: 430, title: 'src/core/', sub: ['transport, auth, retry, idempotency,', 'async-iterator pagination, AfsError'], tone: 'api' });
  d.node({ id: 'res', x: 915, y: 490, w: 430, title: 'src/resources/', sub: ['waitFor, typed reports'], tone: 'api' });
  d.edge('contract', 'gen', { tone: 'data', label: 'codegen' });
  d.edge('gen', 'core', { tone: 'api' });
  d.edge('core', 'res', { tone: 'api' });
  d.edge('infra', 'gen', { from: 'r', to: 'l', tone: 'neutral', label: 'calls' });
  d.text({ x: 30, y: 645, lines: 'src/architecture.test.ts fails the build if a layer imports the wrong way. The SDK has zero runtime dependencies and uses fetch.', size: 12.5 });
};
