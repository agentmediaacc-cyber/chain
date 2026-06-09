# CHAIN Call + Message Scale Hardening Plan

> **Honest Assessment:** A single local Mac cannot serve millions of users.  
> Millions require: **Redis, TURN servers, Gunicorn/gevent workers, load balancer, CDN, object storage, monitoring, and multiple servers.**

## Current Architecture

- **Web Server:** Flask with Socket.IO (single process or Gunicorn workers)
- **Database:** PostgreSQL (Neon) via connection pool
- **Cache:** Redis (optional, local fallback)
- **WebRTC:** STUN only by default (TURN optional)
- **File Storage:** Local filesystem
- **Frontend:** Server-rendered Jinja2 templates + vanilla JS

## Production Requirements for Millions

| Component | Required | Current Status |
|-----------|----------|----------------|
| Redis | Session store, Socket.IO message queue, cache | Configured but optional |
| TURN server | WebRTC for NAT traversal | Missing by default |
| Gunicorn/gevent | Multi-worker WSGI | Configured but single worker typical |
| Load balancer | Distribute traffic | None |
| CDN | Static assets, media delivery | None |
| Object storage | Media files (S3-compatible) | Local filesystem |
| Monitoring | APM, errors, metrics | Basic logging |
| Database pooling | Connection pooling for scale | Configured |

## Call System Scale Hardening

### Call State Machine
```
idle → ringing → connecting → connected → reconnecting → ended
  ↘          ↘          ↘            ↘            ↘
  failed    missed     failed        failed       failed
  busy
```

- 9 states: idle, ringing, connecting, connected, reconnecting, ended, failed, missed, busy
- Self-call prevention
- Duplicate call detection (10s window)
- Rate limiting (3 calls per 30s per pair)
- TURN warning when not configured

### WebRTC Reconnection
- ICE restart support
- 30s reconnection timeout
- Quality monitoring (weak → reconnecting → failed)
- Participant connection state tracking

## Message System Scale Hardening

### Delivery State Machine
```
queued → sending → sent → delivered → seen
  ↘        ↘          ↘
 failed   failed     failed
  ↕
retrying
```

- 7 states: queued, sending, sent, delivered, seen, failed, retrying
- client_message_id + sender_profile_id unique dedup
- Retry queue with backoff
- Offline message queue (localStorage)

### Duplicate Prevention
- Unique index on (sender_profile_id, client_message_id)
- Client-generated message IDs
- Server-side dedup check before INSERT
- Idempotent retry

## Socket.IO Scale Hardening

### Redis Manager
- Auto-detects REDIS_URL for production
- Falls back to single-node for dev/testing
- Warning logged when Redis unavailable

### Auth Checks
- Thread membership verified before joining thread rooms
- Profile authentication required for all events
- Call room access gated via auth

### Rate Limiting
| Event | Limit |
|-------|-------|
| message:send | 30/min per user |
| typing | 20/min per user |
| call:start | 10/min per user |
| call:offer | 20/min per user |
| call:ice-candidate | 60/min per user |

### Heartbeat
- 30s presence heartbeat
- Room state recovery on reconnect
- Profile SID tracking for multi-device

## Database Indexes

New indexes in `sql/message_call_scale_hardening.sql`:
- `idx_chain_messages_client_dedup` — unique on (sender_profile_id, client_message_id)
- `idx_chain_messages_delivery_state` — filtered on queued/sending/retrying/failed
- `idx_chain_messages_delivered_at` — filtered
- `idx_chain_messages_seen_at` — filtered
- `idx_chain_messages_retry` — filtered on retry_count > 0
- `idx_chain_calls_status_active` — filtered on active states
- `idx_chain_calls_end_reason` — filtered
- `idx_call_participants_connection` — filtered on connection states
- `idx_online_presence_status` — filtered on online/busy/in_call
- `idx_retry_queue_next` — for retry scheduler

## UI Improvements

- Sending spinner for pending messages
- Delivered (single check) / Seen (double check) indicators
- Failed message retry button with exponential backoff
- Offline banner when browser goes offline
- Call reconnecting overlay with retry count
- Call failed reason banner (network_error, timeout, ice_failed, etc.)
- Incoming call modal (z-index 9999, above all pages)

## Test Plan

1. **Call State Tests** — all 9 states, transitions, self-call, duplicate, rate limit
2. **Message Delivery Tests** — 7 states, client_message_id dedup, retry
3. **Socket Hardening Tests** — auth checks, rate limits, heartbeat, rooms
4. **Diagnostics Tests** — TURN warning, /api/diagnostics, /api/socket-diagnostics
5. **UI Tests** — spinner, checks, retry, offline, reconnect, failed reason, modal

## Required Infrastructure (Not in this PR)

- [ ] TURN server (coturn) — for WebRTC NAT traversal
- [ ] Redis in production — for Socket.IO scaling
- [ ] Gunicorn with gevent workers — `gunicorn -k gevent -w 4 app:app`
- [ ] Load balancer (nginx/haproxy) — round-robin across workers
- [ ] CDN (Cloudflare, Fastly) — static assets + media cache
- [ ] Object storage (S3/R2) — media uploads
- [ ] APM (Datadog, Sentry) — production monitoring
- [ ] Database read replicas — for read-heavy queries
- [ ] WebSocket load testing — before going live
