# Gateway — WhatsApp and Discord

## Overview

Gateways are **separate processes** that translate inbound messages from
external messaging platforms into harness requests and relay the responses back.

```
WhatsApp / Discord → Gateway → POST /v3/agent/question → Agent → reply
```

All gateways share a single `HarnessForwarder` (`ai.gateway.http_forwarder`)
which handles rate limiting, request serialisation, and HTTP I/O.

---

## Environment Variables

### Common (all gateways)

| Variable | Default | Description |
|---|---|---|
| `HARNESS_URL` | `http://localhost:8005` | Base URL of the running harness |
| `GATEWAY_JWT` | — | Bearer token forwarded to the harness in every request |
| `GATEWAY_TIMEOUT_S` | `60` | Per-request HTTP timeout (seconds) |
| `GATEWAY_RATE_LIMIT_MAX` | `10` | Max messages per sender per window |
| `GATEWAY_RATE_LIMIT_WINDOW_S` | `60` | Rate-limit sliding window (seconds) |
| `GATEWAY_MAX_TEXT_LEN` | `4000` | Max characters from an inbound message (truncated beyond) |

### WhatsApp (neonize)

| Variable | Default | Description |
|---|---|---|
| `WHATSAPP_DEVICE_NAME` | `ai-harness` | Display name shown to contacts |
| `WHATSAPP_STORE_PATH` | `./wa_session.db` | Path to the neonize SQLite session store |
| `WHATSAPP_PAIR_PHONE` | — | Phone number for phone-pairing auth (e.g. `+447700900000`). Omit to use QR-code pairing |

### Discord (planned)

| Variable | Description |
|---|---|
| `DISCORD_BOT_TOKEN` | Bot token from discord.com/developers |
| `DISCORD_GUILD_ID` | Optional guild ID to restrict events |

---

## Installation

### WhatsApp

```bash
# Install the optional extra
uv add 'ai[whatsapp]'   # or: pip install 'ai[whatsapp]'

# Start the gateway (separate process from the main harness)
python -m ai.gateway.whatsapp.client
```

On first run, neonize will print a QR code to the terminal.  Scan it with
WhatsApp → Linked Devices → Link a Device.  The session is persisted to
`WHATSAPP_STORE_PATH`.

### Discord

The Discord gateway is a **stub** — see `FUTURE.md`.  Installing `discord.py`
is not yet required.

---

## Security

> **Warning:** Gateways hold long-lived credentials.

- **Run as an isolated process** with minimal filesystem and network permissions.
- **Never commit** `WHATSAPP_STORE_PATH` (session DB) or `DISCORD_BOT_TOKEN` to
  version control.
- **Rotate `GATEWAY_JWT`** on the same schedule as other service tokens.
- The `GATEWAY_JWT` is forwarded verbatim to the harness; use a dedicated
  service-account token, not a user JWT.
- Apply **network-level rate limiting** (e.g. nginx) in addition to the
  in-process `RateLimiter` for multi-process deployments.

---

## Direct harness WebSocket (local smoke)

Gateways use HTTP (`POST /v3/agent/question`). To exercise **`WS /v3/ws/{client_id}`** with the same auth and `chat_request` envelope as the integration tests, use the example client from the `ai/` project root:

```bash
cd ai
uv run --group dev python example/client_ws.py --preset 1
```

**Auth (same idea as ai-master `client/example.py`):**

- **GraphQL login:** set **`CLIENT_EXAMPLE_EMAIL`** and **`CLIENT_EXAMPLE_PASSWORD`**, or pass **`--email`** / **`--password`**. The client posts the **`auth_login`** mutation to **`GRAPHQL_URL`** if set, otherwise **`config.GATEWAY_URL`**`/graphql` from **`ai.config`** (same base as tools), and uses **`accessToken`** as the WebSocket Bearer token. On a TTY, it can prompt for email/password if no JWT is configured.
- **JWT without login:** **`--token`**, or **`AI_HARNESS_JWT`** / **`GATEWAY_JWT`**, or **`--mint --sub <user_id>`** (requires **`AUTH_SECRETPHRASE`** or **`SECRET_KEY`** to match the harness).

Use **`--auth-first-message`** to send `{"type":"authenticate","token":"..."}` as the first frame instead of an `Authorization` header. **`--list-presets`** prints built-in queries.

---

## Architecture Notes

- The `HarnessForwarder` builds a minimal `AgentChatRequestV3`-compatible JSON
  body and POSTs it to `POST /v3/agent/question`.
- The `channel` field in `routeMetadata` is set to `"whatsapp"` or
  `"discord"` so the agent runner can tailor its response format.
- Rate limiting is **per sender id** (WhatsApp JID / Discord user id) using a
  sliding-window counter.  For multi-process gateways, replace the in-process
  `RateLimiter` with a Redis-backed implementation.
