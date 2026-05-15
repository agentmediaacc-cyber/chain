from datetime import datetime, timezone
import uuid

def initiate_mtc_maris_payment(profile_id, amount_nad):
    """
    Simulates initiating an MTC Maris payment (USSD/SMS push).
    Returns a reference and external URL.
    """
    ref = f"MARIS-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "pending",
        "reference": ref,
        "instructions": f"Dial *140*666# and enter ref {ref} to complete your {amount_nad} NAD payment."
    }

def verify_bank_transfer(profile_id, amount_nad, reference_id):
    """
    Simulates manual/semi-auto verification of FNB/Bank transfers.
    In a real app, this would query a statement API or wait for admin approval.
    """
    # Placeholder: record a pending verification
    return {"status": "awaiting_proof", "ref": reference_id}

def process_webhook(provider, payload):
    """
    Main entry point for payment provider webhooks (Paystack, Flutterwave, etc.)
    """
    # 1. Validate signature
    # 2. Extract transaction ID and status
    # 3. Trigger wallet update if successful
    pass

def log_payout_request(profile_id, amount_nad, method):
    """Logs a creator payout request for admin review"""
    from services.supabase_safe import safe_insert
    payload = {
        "profile_id": profile_id,
        "amount_nad": amount_nad,
        "coins_deducted": int(amount_nad * 10), # 1 NAD = 10 coins
        "payout_method": method,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_insert("chain_wallet_payouts", payload)
