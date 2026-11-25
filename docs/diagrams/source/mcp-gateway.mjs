// Release 1.3.0: an MCP tool call through the team gateway: governed catalog, three-level admission, upstream auth.
export default (d) => {
  d.size(1400, 1120);
  d.title('Governed MCP servers', 'Agents reach MCP servers only through the team gateway. It admits each call against the approved catalog and the team and agent policy, then calls the server with credentials the agent never holds.');
  d.seq({
    x0: 30, y0: 96, colW: 222, boxW: 196, rowH: 44,
    participants: [
      { id: 'agent', title: 'Agent pod', sub: 'any MCP client', tone: 'k8s' },
      { id: 'gw', title: 'Team gateway', sub: 'afs-gateway /mcp', tone: 'api' },
      { id: 'db', title: 'PostgreSQL', sub: 'catalog, policy, ledger', tone: 'data' },
      { id: 'up', title: 'MCP server', sub: 'enterprise, corporate or hosted', tone: 'neutral' },
      { id: 'idp', title: 'Token issuer', sub: 'OAuth AS or STS', tone: 'aws' },
      { id: 'rec', title: 'afs-reconciler', sub: 'leader', tone: 'api' },
    ],
    steps: [
      { note: ['the reconciler gives agents AFS_MCP_URL, AFS_MCP_MODE, AFS_MCP_SERVERS and /etc/afs/mcp.json,', 'renders hosted servers behind afs-mcp-bridge, and gives the gateway credentials and egress'], over: ['agent', 'rec'], tone: 'k8s' },
      { from: 'agent', to: 'gw', label: 'POST /mcp initialize (aggregated) or /mcp/<server>', tone: 'k8s' },
      { from: 'gw', to: 'agent', label: 'sealed Mcp-Session-Id; search mode lists afs_search, afs_describe, afs_call', dashed: true, tone: 'api' },
      { from: 'agent', to: 'gw', label: 'tools/call github__create_issue', tone: 'k8s' },
      { from: 'gw', to: 'db', label: 'mcp_admission: approved, team on, agent allowed (cached 60 s)', tone: 'api' },
      { frame: 'if refused', over: ['agent', 'gw', 'db'], tone: 'danger' },
      { from: 'gw', to: 'agent', label: '-32602 Unknown tool (reason only in the ledger)', dashed: true, tone: 'danger' },
      { endFrame: true },
      { from: 'gw', to: 'gw', label: 'policy: service ⊇ team ⊇ agent, block wins; read_only mode; rate and size limits', tone: 'api' },
      { frame: 'federated or OAuth server', over: ['gw', 'db', 'up', 'idp'], tone: 'aws' },
      { from: 'gw', to: 'idp', label: 'RFC 8693 exchange of the projected token, or refresh', tone: 'api' },
      { from: 'idp', to: 'gw', label: 'short-lived access token', dashed: true, tone: 'aws' },
      { endFrame: true },
      { from: 'gw', to: 'up', label: 'tools/call create_issue + credential', tone: 'api' },
      { from: 'up', to: 'gw', label: 'result', dashed: true, tone: 'neutral' },
      { from: 'gw', to: 'db', label: 'mcp_events ledger row (batched, fails open)', tone: 'api' },
      { from: 'gw', to: 'agent', label: 'result + io.afs/requestId', dashed: true, tone: 'api' },
      { frame: 'inventory refresh', over: ['gw', 'db', 'up'], tone: 'data' },
      { from: 'gw', to: 'up', label: 'tools/list · resources/list · prompts/list', tone: 'api' },
      { from: 'gw', to: 'db', label: 'new or changed definitions held; compatible ones auto-approved by policy', tone: 'api' },
      { endFrame: true },
      { from: 'rec', to: 'db', label: 'McpServerReady · McpAuthExpired · McpDriftPending per team', tone: 'api' },
    ],
  });
};
