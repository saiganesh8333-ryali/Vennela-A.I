# Gemini Live proxy

The backend exposes `wss://<host>/ws/gemini/live`. Clients must send an
`Authorization: Bearer <VENNELA_REALTIME_TOKEN>` header. If that variable is
unset, `VENNELA_AGENT_TOKEN` is used; an unset token rejects every connection.

The first JSON frame is:

```json
{
  "type": "session.start",
  "user_id": "user-1",
  "session_id": "session-1"
}
```

Client frames:

- `{"type":"audio","data":"<base64 PCM>","mime_type":"audio/pcm;rate=16000"}`
- `{"type":"text","text":"..."}`
- `{"type":"tool_result","call_id":"...","name":"...","result":{...}}`
- `{"type":"ping"}`

Server frames include `session.ready`, `audio` (base64 PCM), `text`,
`tool_call`, `interrupted`, `pong`, and sanitized `error` events.

`GEMINI_API_KEY` and `GEMINI_LIVE_MODEL` are server-only environment
variables. The API key is never accepted from a client frame and is never
included in logs or downstream events. Set `VENNELA_REALTIME_USER_ID` to bind
the authenticated token to one user, and
`VENNELA_REALTIME_ALLOWED_ORIGINS` to a comma-separated origin allowlist when
browser clients are enabled.
