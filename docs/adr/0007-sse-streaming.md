# ADR-0007 — REST + Server-Sent Events instead of WebSockets

## Status

Accepted.

## Context

`docs/09` requires streaming responses in the conversation area — an assistant that
renders a complete answer after ten seconds of silence does not feel intelligent.
`docs/08` specifies "REST API initially, WebSocket support later". These appear to
conflict: streaming is usually associated with WebSockets.

Ray's streaming is also not just tokens. The HUD needs to show *which agent activated*
and *which tool is running* while the answer is still being produced.

## Decision

**REST for everything, with `POST /chat/message` responding as an SSE event stream.**

The stream carries typed events, not just raw text:

```
event: trace     data: {"stage":"routing"}
event: trace     data: {"agent":"coding","memories_used":4}
event: tool      data: {"tool":"github.read_repo","status":"running"}
event: approval  data: {"tool":"calendar.create_event","payload":{...}}
event: token     data: {"text":"Next you should "}
event: done      data: {"message_id":"...","trace_id":"..."}
```

This gives the Ray Status panel, the agent visualization, the approval cards, and the
streaming text all from one connection.

SSE is chosen over WebSockets because the data flow is one-directional (server → client
during a response; the client's contribution is the initial POST). SSE is plain HTTP, so
it needs no separate connection lifecycle, no reconnection logic beyond the browser's
built-in retry, no separate auth path, and it works with the existing bearer token. A
WebSocket would add bidirectional machinery that nothing in V1 uses.

WebSockets remain the right answer later for live wake-word audio streaming to the
backend — that is genuinely bidirectional and is addressed in ADR-0009.

## Alternatives considered

* **WebSockets now.** More capable, but more moving parts for a flow that is
  request/response shaped. Also contradicts `docs/08`'s stated ordering.
* **Poll a job status endpoint.** Works with plain REST, but adds latency and produces
  chunky rather than smooth token rendering.

## Consequences

* The frontend uses `fetch` with a `ReadableStream` reader rather than `EventSource`,
  because `EventSource` cannot issue a POST or set an `Authorization` header.
* Any proxy in front of Ray must not buffer responses.
* Errors mid-stream are delivered as an `event: error` rather than an HTTP status, so
  the client must handle both failure shapes.
