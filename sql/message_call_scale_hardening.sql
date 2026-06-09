-- ============================================================
-- CALL + MESSAGE SCALE HARDENING
-- Idempotent — safe to re-run
-- ============================================================

-- === MESSAGE DELIVERY STATES ===
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS client_message_id TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS failed_reason TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS delivery_state TEXT DEFAULT 'sent';
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS queued_at TIMESTAMPTZ;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS retrying_at TIMESTAMPTZ;

-- Unique index on sender_profile_id + client_message_id for duplicate prevention
-- (only when client_message_id is not null)
CREATE UNIQUE INDEX IF NOT EXISTS idx_chain_messages_client_dedup
    ON chain_messages(sender_profile_id, client_message_id)
    WHERE client_message_id IS NOT NULL;

-- Delivery state index for pending/retrying messages
CREATE INDEX IF NOT EXISTS idx_chain_messages_delivery_state
    ON chain_messages(delivery_state)
    WHERE delivery_state IN ('queued', 'sending', 'retrying', 'failed');

-- Message delivery performance indexes
CREATE INDEX IF NOT EXISTS idx_chain_messages_delivered_at
    ON chain_messages(delivered_at)
    WHERE delivered_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chain_messages_seen_at
    ON chain_messages(seen_at)
    WHERE seen_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chain_messages_retry
    ON chain_messages(retry_count)
    WHERE retry_count > 0;

-- === CALL STATE INDEXES ===
CREATE INDEX IF NOT EXISTS idx_chain_calls_status_active
    ON chain_calls(status, created_at DESC)
    WHERE status IN ('ringing', 'accepted', 'connecting', 'reconnecting');

CREATE INDEX IF NOT EXISTS idx_chain_calls_end_reason
    ON chain_calls(end_reason)
    WHERE end_reason IS NOT NULL;

-- === CALL PARTICIPANTS CONNECTION STATUS ===
CREATE INDEX IF NOT EXISTS idx_call_participants_connection
    ON chain_call_participants(connection_status)
    WHERE connection_status IN ('connecting', 'reconnecting', 'disconnected', 'failed');

-- === ONLINE PRESENCE INDEX ===
CREATE INDEX IF NOT EXISTS idx_online_presence_status
    ON chain_online_presence(status)
    WHERE status IN ('online', 'busy', 'in_call');

-- === MESSAGE RETRY QUEUE TABLE ===
CREATE TABLE IF NOT EXISTS chain_message_retry_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES chain_messages(id) ON DELETE CASCADE,
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id),
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_retry_queue_next
    ON chain_message_retry_queue(next_retry_at)
    WHERE next_retry_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_retry_queue_sender
    ON chain_message_retry_queue(sender_profile_id);

-- === BLOCKED / MUTED USERS ===
CREATE TABLE IF NOT EXISTS chain_blocked_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blocked_by_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    blocked_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(blocked_by_profile_id, blocked_profile_id)
);

CREATE TABLE IF NOT EXISTS chain_muted_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    muter_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    muted_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(muter_profile_id, muted_profile_id)
);
