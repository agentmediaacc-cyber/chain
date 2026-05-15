from utils.supabase_client import get_supabase_admin

def record_ledger(profile_id, transaction_type, coins, description="", related_profile_id=None):
    supabase = get_supabase_admin()
    return supabase.table("chain_wallet_transactions").insert({
        "profile_id": profile_id,
        "transaction_type": transaction_type,
        "coins": int(coins),
        "description": description,
        "related_profile_id": related_profile_id,
    }).execute()


def coins_to_nad(coins):
    return int(coins or 0) * 5


def nad_to_coins(nad):
    return int(nad or 0) // 5
