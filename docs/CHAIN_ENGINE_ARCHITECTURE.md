# Chain Engine Architecture

## Engines Added

- cache_engine: page/data caching
- safety_engine: text cleanup, profanity filter, username normalization
- media_engine: upload save + image compression
- matching_engine: profile scoring
- wallet_ledger_engine: wallet transaction logic
- notification_engine: central notification creation
- analytics_engine: dashboard metrics
- search_engine: profile search
- realtime_engine: channel naming for Supabase Realtime
- scheduler_engine: APScheduler startup
- maintenance_jobs: stale live cleanup + profile completion refresh

## Recommended Environment Variables

REDIS_URL=
CACHE_DEFAULT_TIMEOUT=60

## Coin Rule

1 Chain coin = N$5
