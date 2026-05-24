CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION chain_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS chain_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid UNIQUE NOT NULL,
    email text,
    username text UNIQUE,
    display_name text,
    full_name text,
    bio text,
    avatar_url text,
    town text,
    city text,
    location text,
    creator_category text,
    is_verified boolean DEFAULT false,
    verified boolean DEFAULT false,
    is_online boolean DEFAULT false,
    is_creator boolean DEFAULT false,
    dating_mode_enabled boolean DEFAULT false,
    profile_completed boolean DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    caption text,
    content text,
    category text,
    media_url text,
    thumbnail_url text,
    storage_bucket text,
    storage_path text,
    likes_count integer NOT NULL DEFAULT 0,
    comments_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_status_posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    caption text,
    media_url text,
    thumbnail_url text,
    storage_bucket text,
    storage_path text,
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_stories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    caption text,
    media_url text,
    thumbnail_url text,
    storage_bucket text,
    storage_path text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_reels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    caption text,
    media_url text,
    thumbnail_url text,
    storage_bucket text,
    storage_path text,
    likes_count integer NOT NULL DEFAULT 0,
    comments_count integer NOT NULL DEFAULT 0,
    is_private boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_live_rooms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    title text,
    category text,
    cover_url text,
    thumbnail_url text,
    storage_bucket text,
    storage_path text,
    status text DEFAULT 'draft',
    is_live boolean DEFAULT false,
    viewer_count integer DEFAULT 0,
    entry_fee numeric(12,2),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    sender_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    recipient_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    body text,
    media_url text,
    thumbnail_url text,
    storage_bucket text,
    storage_path text,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    notification_type text,
    title text,
    body text,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_follows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    follower_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    following_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_likes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    post_id uuid REFERENCES chain_posts(id) ON DELETE CASCADE,
    reel_id uuid REFERENCES chain_reels(id) ON DELETE CASCADE,
    story_id uuid REFERENCES chain_stories(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    post_id uuid REFERENCES chain_posts(id) ON DELETE CASCADE,
    reel_id uuid REFERENCES chain_reels(id) ON DELETE CASCADE,
    body text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_wallet_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    transaction_type text,
    amount numeric(12,2) NOT NULL DEFAULT 0,
    currency text DEFAULT 'CHAIN',
    reference text,
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_media_uploads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    upload_type text NOT NULL,
    storage_bucket text NOT NULL,
    storage_path text NOT NULL,
    media_url text,
    thumbnail_url text,
    mime_type text,
    file_size bigint,
    original_filename text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_chain_profiles_deleted_at ON chain_profiles(deleted_at);
CREATE INDEX IF NOT EXISTS idx_chain_posts_profile_created ON chain_posts(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_status_posts_profile_created ON chain_status_posts(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_stories_profile_created ON chain_stories(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_reels_profile_created ON chain_reels(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_live_rooms_status_created ON chain_live_rooms(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_messages_recipient_created ON chain_messages(recipient_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_notifications_profile_created ON chain_notifications(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_wallet_transactions_profile_created ON chain_wallet_transactions(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_media_uploads_profile_created ON chain_media_uploads(profile_id, created_at DESC);

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'chain_profiles',
        'chain_posts',
        'chain_status_posts',
        'chain_stories',
        'chain_reels',
        'chain_live_rooms',
        'chain_messages',
        'chain_notifications',
        'chain_follows',
        'chain_likes',
        'chain_comments',
        'chain_wallet_transactions',
        'chain_media_uploads'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_touch_updated_at ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER trg_%s_touch_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION chain_touch_updated_at()',
            table_name,
            table_name
        );
    END LOOP;
END $$;
