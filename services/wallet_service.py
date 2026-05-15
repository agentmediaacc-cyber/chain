from datetime import datetime, timezone

from services.profile_service import get_current_profile
from services.notification_service import create_notification
from services.supabase_safe import safe_insert, safe_select, safe_update


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _normalize_wallet(wallet, transactions=None):
    wallet = dict(wallet or {})
    transactions = transactions or []
    derived_balance = sum(int(tx.get("coins") or 0) for tx in transactions)

    if wallet.get("coin_balance") is None:
        wallet["coin_balance"] = derived_balance
    wallet.setdefault("gift_earnings", 0)
    wallet.setdefault("pending_withdrawal", 0)
    wallet.setdefault("total_spent", sum(abs(int(tx.get("coins") or 0)) for tx in transactions if int(tx.get("coins") or 0) < 0))
    wallet.setdefault("total_received", sum(int(tx.get("coins") or 0) for tx in transactions if int(tx.get("coins") or 0) > 0))
    wallet["transaction_count"] = len(transactions)
    wallet["gifts_received_count"] = len([tx for tx in transactions if tx.get("transaction_type") == "gift_received"])
    wallet["topup_count"] = len([tx for tx in transactions if tx.get("transaction_type") == "topup"])
    return wallet


def _load_wallet_transactions(profile_id, limit=20):
    return safe_select(
        "chain_wallet_transactions",
        filters={"profile_id": profile_id},
        limit=limit,
    )


def ensure_wallet(profile_id):
    try:
        wallets = safe_select("chain_wallets", filters={"profile_id": profile_id}, limit=1)
        transactions = _load_wallet_transactions(profile_id)
        if wallets:
            return _normalize_wallet(wallets[0], transactions)

        created = safe_insert(
            "chain_wallets",
            {
                "profile_id": profile_id,
                "coin_balance": 0,
                "gift_earnings": 0,
                "pending_withdrawal": 0,
                "total_spent": 0,
                "total_received": 0,
                "updated_at": _utcnow_iso(),
            },
        )
        if created is not None:
            refreshed = safe_select("chain_wallets", filters={"profile_id": profile_id}, limit=1)
            if refreshed:
                return _normalize_wallet(refreshed[0], transactions)

        return _normalize_wallet({"profile_id": profile_id}, transactions)
    except Exception as error:
        print(f"[wallet_service] ensure_wallet failed: {error}")
        return None


def get_wallet_home():
    try:
        current = get_current_profile()
        if not current:
            return None, None, [], []

        wallet = ensure_wallet(current["id"])
        transactions = _load_wallet_transactions(current["id"], limit=20)
        wallet = _normalize_wallet(wallet, transactions) if wallet else _normalize_wallet({}, transactions)
        gifts = safe_select("chain_gift_catalog", filters={"is_active": True}, limit=30, order_by="coin_price", desc=False)

        return current, wallet, gifts, transactions
    except Exception as error:
        print(f"[wallet_service] get_wallet_home failed: {error}")
        return None, None, [], []


def top_up_wallet(coins):
    try:
        current = get_current_profile()
        if not current:
            return False

        coins = int(coins or 0)
        if coins <= 0:
            return False

        wallet = ensure_wallet(current["id"])
        new_balance = (wallet.get("coin_balance") or 0) + coins

        safe_update(
            "chain_wallets",
            {"coin_balance": new_balance, "updated_at": _utcnow_iso()},
            eq={"profile_id": current["id"]},
        )

        safe_insert("chain_wallet_transactions", {
            "profile_id": current["id"],
            "transaction_type": "topup",
            "coins": coins,
            "description": f"Added {coins} coins to wallet",
        })
        return True
    except Exception as error:
        print(f"[wallet_service] top_up_wallet failed: {error}")
        return False


def send_gift_to_username(username, gift_id):
    try:
        sender = get_current_profile()
        receiver = (safe_select("chain_profiles", filters={"username": username}, limit=1) or [None])[0]

        if not sender or not receiver:
            return False, "Profiles not found"

        gift = (safe_select("chain_gift_catalog", filters={"id": gift_id}, limit=1, order_by=None) or [None])[0]
        if not gift:
            return False, "Gift not found"

        price = int(gift["coin_price"])
        sender_wallet = ensure_wallet(sender["id"])
        if (sender_wallet.get("coin_balance") or 0) < price:
            return False, "Insufficient balance"

        safe_update(
            "chain_wallets",
            {
                "coin_balance": sender_wallet["coin_balance"] - price,
                "total_spent": (sender_wallet.get("total_spent") or 0) + price,
                "updated_at": _utcnow_iso(),
            },
            eq={"profile_id": sender["id"]},
        )

        receiver_wallet = ensure_wallet(receiver["id"])
        safe_update(
            "chain_wallets",
            {
                "gift_earnings": (receiver_wallet.get("gift_earnings") or 0) + price,
                "total_received": (receiver_wallet.get("total_received") or 0) + price,
                "updated_at": _utcnow_iso(),
            },
            eq={"profile_id": receiver["id"]},
        )

        safe_insert("chain_wallet_transactions", [
            {
                "profile_id": sender["id"],
                "transaction_type": "gift_sent",
                "coins": -price,
                "description": f"Sent {gift['emoji']} to {receiver['full_name']}",
                "related_profile_id": receiver["id"],
            },
            {
                "profile_id": receiver["id"],
                "transaction_type": "gift_received",
                "coins": price,
                "description": f"Received {gift['emoji']} from {sender['full_name']}",
                "related_profile_id": sender["id"],
            }
        ])

        safe_insert("chain_gift_events", {
            "sender_profile_id": sender["id"],
            "receiver_profile_id": receiver["id"],
            "gift_id": gift["id"],
            "gift_name": gift["name"],
            "emoji": gift["emoji"],
            "coins": price,
        })

        create_notification(
            receiver["id"],
            "Gift Received!",
            f"{sender['full_name']} sent you a {gift['emoji']}!",
            "gift",
            "/wallet/"
        )

        return True, "Gift sent!"
    except Exception as error:
        print(f"[wallet_service] send_gift_to_username failed: {error}")
        return False, str(error)


def get_gift_page(username):
    try:
        current = get_current_profile()
        receiver = (safe_select("chain_profiles", filters={"username": username}, limit=1) or [None])[0]
        wallet = ensure_wallet(current["id"]) if current else None
        gifts = safe_select("chain_gift_catalog", filters={"is_active": True}, limit=30, order_by="coin_price", desc=False)
        return current, receiver, wallet, gifts
    except Exception as error:
        print(f"[wallet_service] get_gift_page failed: {error}")
        return None, None, None, []
