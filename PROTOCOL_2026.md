# MCP 2026-07-28: production migration notes

This repository teaches the current MCP protocol revision, `2026-07-28`. The
one-line operational change is significant: **the protocol core is stateless**.
There is no `initialize`/`initialized` handshake and no `Mcp-Session-Id` on the
modern path. Each request carries what the server needs to handle it.

The official Python SDK v2 `Client` uses modern MCP by default. In `mode="auto"`
it probes optional `server/discover` and falls back to the legacy initialize
handshake only when it meets an older server.

## Modern request anatomy

```http
POST /mcp HTTP/1.1
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: search
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"tools/call",
 "params":{"name":"search","arguments":{"q":"otters"},
 "_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",
 "io.modelcontextprotocol/clientCapabilities":{},
 "io.modelcontextprotocol/clientInfo":{"name":"my-app","version":"1.0"}}}}
```

- `MCP-Protocol-Version` selects the wire contract.
- `Mcp-Method` and `Mcp-Name` let gateways, WAFs, rate limiters, and telemetry
  route the call without parsing JSON.
- `_meta` carries protocol version and client capabilities on every request;
  client identity should be included as well.
- `server/discover` is useful for eager capability discovery, but it is not a
  prerequisite for `tools/list`, `resources/read`, or `tools/call`.

Application state is still allowed. Make it explicit: a tool can mint a job,
cart, or workflow handle and require that handle on later calls. Do not hide
application state in a transport session that the model cannot see.

## What replaced server-to-client requests

Modern MCP has no back-channel for a server to push `elicitation/create`,
`sampling/createMessage`, or `roots/list` during a call. Multi Round-Trip
Requests (MRTR) reverse the flow:

1. The server returns `resultType: "input_required"` with typed questions and
   opaque `requestState`.
2. The client obtains the input.
3. The client retries the original method with `inputResponses` and the exact
   `requestState`.
4. The server completes or requests another bounded round.

In Python SDK v2, prefer `Annotated[T, Resolve(resolver)]`; the high-level
`Client` drives the loop. See [examples/10_multi_round_trip.py](examples/10_multi_round_trip.py).
For multiple replicas, configure the same request-state signing keys on every
replica. Treat `requestState` as opaque and never deserialize or edit it in the
client.

## Cacheable catalogs

`server/discover`, `tools/list`, `prompts/list`, `resources/list`, resource
templates, and `resources/read` can return:

- `ttlMs`: how long the response may be considered fresh.
- `cacheScope`: `private` for one authorization context, or `public` when the
  response is genuinely identical and safe to share.

The Python client honors these hints by default. Notifications invalidate
affected entries. A custom shared cache must derive its private partition from
a verified principal, not request-controlled input. See
[examples/11_cacheable_catalogs.py](examples/11_cacheable_catalogs.py).

## Extensions, Tasks, and deprecations

The 2026 revision formalizes extensions so optional features do not expand the
protocol core. **Tasks** are an extension for durable, pollable work; use them
for jobs whose lifetime should outlive one tool response. Negotiate extensions
and ignore ones a peer does not advertise.

Roots, client sampling, and MCP-level logging are deprecated across protocol
versions. `ping` is removed from modern MCP. Resource subscription uses
`subscriptions/listen` rather than the old standalone GET stream and
`resources/subscribe`.

## Authorization hardening

- Validate the authorization-server issuer (`iss`, RFC 9207) before exchanging
  an authorization code; bind credentials to the issuer that minted them.
- Prefer Client ID Metadata Documents (CIMD). Dynamic Client Registration is
  deprecated and remains only for compatibility.
- Keep HTTP transport protections: TLS, exact Host and Origin allowlists,
  audience validation, least-privilege scopes, and per-tool authorization.
- Headers improve routing and policy enforcement, but they are untrusted input;
  verify that they agree with the parsed JSON-RPC body.

## Migration checklist

1. Upgrade both peer SDKs to versions that support `2026-07-28`.
2. Replace raw `ClientSession.initialize()` flows with the high-level `Client`.
3. Remove code that reads, stores, routes on, or deletes `Mcp-Session-Id` for
   modern traffic.
4. Put client info/capabilities in request `_meta` and required routing data in
   HTTP headers.
5. Move push elicitation/sampling/roots into MRTR resolvers.
6. Add honest `ttlMs`/`cacheScope` hints and authorization-safe cache partitions.
7. Share request-state signing keys and notification infrastructure across
   replicas when those features are used.
8. Serve legacy clients deliberately during migration; do not mistake
   `stateless_http=True` for the modern protocol switch. It only affects the
   SDK's legacy HTTP path.

Primary references: the [2026-07-28 specification announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
and the official Python SDK's [v2 changes](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/whats-new.md).
