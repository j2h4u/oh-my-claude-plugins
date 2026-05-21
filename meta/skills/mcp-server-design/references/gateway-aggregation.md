# Remote Gateway Aggregation

> **Load when:** Designing or auditing a deployment where multiple MCP servers are exposed
> through one remote MCP endpoint with a shared OAuth/OIDC edge, especially with Docker MCP
> Gateway, an auth proxy, and a public tunnel or ingress.
>
> **Scope:** STACK-SPECIFIC / CONDITIONAL. This is a deployment recipe, not a recommendation
> that every MCP server should sit behind an aggregator.

This pattern is for operators who do not want every backend MCP server to implement public
OAuth, TLS, DNS, and client onboarding independently. The backend servers stay private; one
gateway presents a single MCP endpoint to remote clients.

---

## Target Shape

```text
Claude / ChatGPT / IDE client
  -> public HTTPS ingress or tunnel
  -> OAuth/OIDC MCP auth proxy
  -> MCP gateway / registry / aggregator
  -> private MCP backend containers
```

One public URL is configured in the client:

```text
https://mcp.example.com/mcp
```

The gateway then routes tool calls to private upstreams such as:

```text
http://docs-mcp:8080/mcp
http://tasks-mcp:3100/mcp
http://shop-mcp:3001/mcp
```

The public URL belongs to the auth edge, not to any backend server.

---

## Layer Responsibilities

| Layer | Owns | Must not own |
|-------|------|--------------|
| Public ingress | TLS, DNS, public reachability, path forwarding | MCP auth semantics, backend routing |
| Auth proxy | OAuth/OIDC, allowlists, token/session handling, protected-resource metadata | Tool execution, backend business auth |
| MCP gateway | Registry/catalog, server selection, MCP routing, optional lifecycle management, tracing | Public unauthenticated exposure |
| Backend MCP servers | Domain tools, input validation, structured output, domain credentials | Public OAuth, public TLS, public DNS |

Keep the layers boring. If a backend server already has its own OAuth for direct public access,
disable that path for the aggregated deployment unless there is a clear reason to keep both.

---

## Docker Gateway Implementation

Docker MCP Gateway can run as a Docker Desktop Toolkit component, a `docker mcp` CLI plugin, or
a pinned container image on plain Docker Engine. In infrastructure stacks, the containerized form
keeps the gateway with the rest of the deployment.

Minimal catalog shape for pre-existing HTTP MCP servers:

```yaml
registry:
  docs:
    remote:
      url: "http://docs-mcp:8080/mcp"
      transport_type: http
  tasks:
    remote:
      url: "http://tasks-mcp:3100/mcp"
      transport_type: http
```

Minimal gateway service:

```yaml
services:
  mcp-gateway:
    image: docker/mcp-gateway:<pinned-version>
    command:
      - --catalog=/mcp/catalog.yaml
      - --servers=docs,tasks
      - --transport=streaming
      - --port=8811
    volumes:
      - ./catalog.yaml:/mcp/catalog.yaml:ro
    expose:
      - "8811"
    networks:
      - edge
      - mcp-backends
```

Two gates must both include a server:

- `catalog.yaml` defines how to reach it
- `--servers=...` decides whether this gateway instance enables it

If the catalog is updated but the `--servers` list is not, the backend exists on paper but will
not appear in `tools/list`.

### Backend Network Rules

- Put backend MCP containers on a private Docker network shared with the gateway.
- Bind backend servers to `0.0.0.0` **inside the container** so sibling containers can reach them.
- Avoid host port publishing for private backends; if needed for local debugging, bind to
  `127.0.0.1`, never `0.0.0.0`.
- Prefer Docker DNS names (`http://service:port/mcp`) over host ports.
- Treat `host.docker.internal` as a migration bridge, not the final architecture.

The common failure: a backend listens on `127.0.0.1` inside its own container. Host port mapping
may still work, but the gateway container gets `connection refused`.

### Docker Socket Caution

Some Docker MCP Gateway modes need Docker daemon access for lifecycle management. A mounted
Docker socket is effectively root on the host. Use it only in the gateway layer, never in backend
servers, and prefer remote-only catalog entries when backend lifecycle is managed separately.

---

## Auth Proxy Edge

The auth proxy sits between public ingress and the gateway:

```yaml
services:
  mcp-auth-proxy:
    image: ghcr.io/sigbit/mcp-auth-proxy:<pinned-version>
    environment:
      EXTERNAL_URL: ${MCP_EXTERNAL_URL}
      NO_AUTO_TLS: "true"
      OIDC_CONFIGURATION_URL: ${OIDC_CONFIGURATION_URL}
      OIDC_CLIENT_ID: ${OIDC_CLIENT_ID}
      OIDC_CLIENT_SECRET: ${OIDC_CLIENT_SECRET}
      OIDC_ALLOWED_USERS: ${OIDC_ALLOWED_USERS:-}
      OIDC_ALLOWED_USERS_GLOB: ${OIDC_ALLOWED_USERS_GLOB:-}
      TRUSTED_PROXIES: 172.16.0.0/12
    command:
      - http://mcp-gateway:8811/mcp
    expose:
      - "80"
    networks:
      - edge
```

Rules:

- `EXTERNAL_URL` must exactly match the public URL clients use.
- Use OIDC allowlists or attribute filters; password auth is acceptable for spikes, not preferred
  for production.
- Set `NO_AUTO_TLS=true` when TLS is terminated by a tunnel, reverse proxy, or managed ingress.
- Point the public ingress to the auth proxy, never directly to the gateway.
- Verify unauthenticated `/mcp` returns `401` and authenticated `/mcp` reaches the gateway.

---

## Public Ingress / Tunnel

The public ingress only forwards HTTPS to the auth proxy. Tailscale Funnel, Cloudflare Tunnel,
a reverse proxy, or a load balancer can play this role.

For a sidecar tunnel container, the flow is:

```text
public HTTPS hostname
  -> tunnel sidecar
  -> http://mcp-auth-proxy:80
```

Do not expose private backend ports through the tunnel. The only public service should be the
auth edge.

---

## Tool Surface Control

Aggregation solves deployment and authentication sprawl. It does **not** solve tool pollution.
Every enabled backend contributes tools to the same `tools/list`, and the client may load all
of them into the model context.

Rules:

- Keep gateway profiles workflow-sized: one endpoint per audience or job, not one endpoint for
  every tool you own.
- Use `--servers=...`, Docker profiles, or tool allowlists to curate the exposed surface.
- Split into multiple public endpoints when tool count or domain scope grows too broad.
- Watch for tool name collisions. If two backends expose `search`, either rename at the backend
  or expose them through separate gateway profiles.
- Preserve each backend's `title`, annotations, `outputSchema`, and `structuredContent`; the
  gateway should not be a reason to weaken tool contracts.

As a rough audit trigger: if the aggregated endpoint exposes more than 15 primary tools, ask
whether the endpoint should be split or filtered.

---

## Security Requirements

- Gateway and backends are private-network services only.
- Auth edge is the only public HTTP service.
- Backends still validate all model-controlled input. Outer OAuth does not make tool arguments
  trustworthy.
- Secrets stay in backend secret stores or environment, not in catalog URLs.
- Logs must redact authorization headers, cookies, tokens, OAuth codes, and tool arguments that
  can contain secrets.
- Public scanners will hit the ingress. Confirm they get `401` and cannot reach gateway health,
  catalog, backend ports, or config files.
- If the gateway has Docker socket access, treat gateway compromise as host compromise.

---

## Smoke Test Protocol

Run these checks from the same Docker network as the gateway:

```bash
curl -i http://mcp-gateway:8811/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
```

Then send `notifications/initialized` and call `tools/list` with the returned
`Mcp-Session-Id`. Check:

- Server info identifies the gateway, not a backend.
- `tools/list` includes only the intended servers.
- Tool count is acceptable for the target client.
- Backend schemas survive aggregation (`title`, annotations, `outputSchema`, no incompatible
  nullable schemas).

Auth edge checks:

```bash
curl -i http://mcp-auth-proxy/healthz
curl -i http://mcp-auth-proxy/mcp
```

Expected unauthenticated `/mcp`: `401 Unauthorized`.

Backend reachability checks:

```bash
curl -i http://docs-mcp:8080/health
curl -i http://docs-mcp:8080/mcp
```

Run them from a container attached to the gateway's backend network, not from the host.

---

## Common Failure Modes

- Backend binds to `127.0.0.1` inside the container, so the gateway cannot connect.
- Server added to catalog but missing from `--servers`.
- Public ingress points directly at the gateway and bypasses OAuth.
- `EXTERNAL_URL` mismatches the actual public URL, breaking OAuth redirects or protected resource
  metadata.
- Password-only auth shipped to production.
- Docker socket mounted into too many containers.
- Aggregated tool count is high enough that model tool selection gets worse.
- Duplicate generic tool names (`search`, `read`, `status`) collide across backends.
- Backend returns schemas that remote clients reject; aggregation does not normalize bad schemas.
- Long-running backend calls exceed auth proxy, tunnel, or client timeouts.

---

## When Not To Use This Pattern

Do not aggregate everything just because it is convenient. Prefer direct per-server exposure when:

- A server has a mature, domain-specific OAuth flow that clients need to see directly
- Different user groups require sharply different access controls
- Backend latency or streaming semantics are sensitive to extra proxy layers
- Tool count would become too large and no allowlist/profile mechanism is available

The architecture is strongest when it is a curated remote MCP endpoint for a clear workflow,
not a universal dump of every internal MCP server.
