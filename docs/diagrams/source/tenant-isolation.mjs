// One team's namespace and every control that keeps it apart from other teams.
export default (d) => {
  d.size(1400, 820);
  d.title('Per-tenant isolation', 'Each team gets its own namespace, IAM role, secret path, inference profile, budget and log destination. Nothing is shared by default.');

  d.group({ x: 30, y: 96, w: 670, h: 420, label: 'Namespace afs-t-payments', tone: 'k8s', sub: 'PSA restricted · ResourceQuota · LimitRange · admission blocks LoadBalancer, NodePort, hostNetwork' });
  d.node({ id: 'cm', x: 60, y: 160, w: 270, title: 'ConfigMap + tags', sub: ['/etc/afs/config, envFrom', '/etc/afs/tags.json, AFS_TAGS'], tone: 'k8s' });
  d.node({ id: 'pvc', x: 60, y: 280, w: 270, title: 'EBS volume (encrypted)', sub: ['/var/lib/agent, Retain', 'scheduled snapshots'], tone: 'k8s' });
  d.node({ id: 'es', x: 60, y: 400, w: 270, title: 'ExternalSecret → Secret', sub: ['env vars and files', 'no code, SDK or sidecar'], tone: 'k8s' });
  d.node({ id: 'pod', x: 400, y: 160, w: 270, title: 'Agent pod: reviewer', sub: ['StatefulSet, exactly 1 replica', 'no Kubernetes RBAC'], tone: 'k8s', badge: 'one agent = one pod' });
  d.node({ id: 'np', x: 400, y: 280, w: 270, title: 'Network policy', sub: ['default deny in and out', 'Cilium toFQDNs per agent'], tone: 'k8s' });
  d.node({ id: 'sa', x: 400, y: 400, w: 270, title: 'ServiceAccount agent-reviewer', sub: ['EKS Pod Identity association', 'the agent\'s identity'], tone: 'k8s' });

  d.node({ id: 'gw', x: 770, y: 160, w: 270, title: 'afs-gateway (afs-system)', sub: ['the only route to models', 'metered, capped, fails closed'], tone: 'api' });
  d.node({ id: 'ext', x: 770, y: 280, w: 270, title: 'Allowed external systems', sub: ['github.com, jira.corp :443', 'service → team → agent, narrowing'], tone: 'neutral' });
  d.node({ id: 'deny', x: 770, y: 400, w: 270, title: 'Everything else', sub: ['other namespaces, internet', 'dropped, logged by Hubble'], tone: 'danger' });

  d.group({ x: 30, y: 600, w: 1340, h: 180, label: 'AWS', tone: 'aws' });
  d.node({ id: 'sm', x: 60, y: 660, w: 270, title: 'Secrets Manager', sub: ['afs/afs-t-payments/reviewer/*', 'afs/afs-t-payments/_shared/*'], tone: 'aws', mono: true });
  d.node({ id: 'iam', x: 400, y: 660, w: 270, title: 'IAM role afs-<team id>', sub: ['ABAC on afs-team-id and', 'kubernetes-namespace; boundary'], tone: 'aws' });
  d.node({ id: 'bed', x: 770, y: 660, w: 270, title: 'Bedrock inference profile', sub: ['one per team and model', 'IAM deny when the cap is hit'], tone: 'aws' });

  d.edge('cm', 'pod', { tf: 0.3, tone: 'k8s' });
  d.edge('pvc', 'pod', { from: 'r', to: 'l', tf: 0.6, tone: 'k8s', mid: 365 });
  d.edge('es', 'pod', { from: 'r', to: 'l', tf: 0.85, tone: 'k8s', mid: 375 });
  d.edge('pod', 'gw', { tone: 'api', label: 'allowed', lx: 720, ly: 196 });
  d.edge('np', 'ext', { tone: 'neutral', label: 'allowed', lx: 720, ly: 316 });
  d.edge('np', 'deny', { from: 'r', to: 'l', ff: 0.85, tone: 'danger', dashed: true, label: 'denied', lx: 740, ly: 400, mid: 740 });
  d.edge('sa', 'iam', { from: 'b', to: 't', tone: 'aws', label: 'Pod Identity' });
  d.edge('sm', 'es', { from: 't', to: 'b', tone: 'aws', label: 'ESO, team role' });
  d.edge('iam', 'sm', { from: 'l', to: 'r', tone: 'aws', label: 'path prefix' });
  d.edge('gw', 'bed', { from: 'r', to: 'r', via: [[1065, 200], [1065, 700]], tone: 'api', label: 'team role', lx: 1065, ly: 580 });

  const layers = [
    ['Network', 'Default deny; DNS, gateway and allowed FQDNs only'],
    ['Compute', 'PSA restricted, quotas; optional dedicated NodePool'],
    ['Kubernetes API', 'Agents get no RBAC; humans no kubectl by default'],
    ['AWS IAM', 'Role per team (or agent), ABAC by afs-team-id'],
    ['Secrets', 'Managed path per namespace; values never in the DB'],
    ['Data', 'Row-level security on every team-owned table'],
    ['Spend', 'Own inference profile, budget, counters, IAM deny'],
    ['Logs', 'Own log group, S3 prefix or destination'],
  ];
  d.text({ x: 1100, y: 118, lines: 'ISOLATION LAYERS', size: 13, bold: true, color: '#232f3e' });
  layers.forEach(([k, v], i) => {
    d.step({ x: 1112, y: 150 + i * 58, n: i + 1, tone: 'k8s' });
    d.text({ x: 1132, y: 148 + i * 58, lines: k, size: 13, bold: true, color: '#102a6b' });
    const words = v.split(' '); const l1 = []; const l2 = [];
    for (const w of words) ((l1.join(' ').length + w.length < 34 && !l2.length) ? l1 : l2).push(w);
    d.text({ x: 1132, y: 166 + i * 58, lines: [l1.join(' '), l2.join(' ')].filter(Boolean), size: 11.5, color: '#414d5c' });
  });
};
