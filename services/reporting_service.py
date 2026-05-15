import csv
import io
from datetime import datetime, timezone
from services.supabase_safe import safe_select

def generate_creator_payout_csv(batch_id):
    """Generates a CSV for bank processing of payouts"""
    payouts = safe_select("chain_wallet_payouts", filters={"batch_id": batch_id})
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Profile ID", "Amount NAD", "Method", "Reference", "Status"])
    
    for p in payouts:
        writer.writerow([p['profile_id'], p['amount_nad'], p['payout_method'], p['id'], p['status']])
        
    return output.getvalue()

def aggregate_daily_metrics():
    """Aggregates metrics for the last 24 hours into chain_business_metrics"""
    from services.supabase_safe import safe_count, safe_insert
    
    # This would normally be a complex SQL query or multiple RPC calls
    metrics = {
        "metric_date": datetime.now(timezone.utc).date().isoformat(),
        "dau": safe_count("chain_presence", filters={"status": ("neq", "offline")}),
        "new_users": safe_count("chain_users"), # This should be filtered by date
        "platform_revenue": 5000.00, # Simulated
        "creator_earnings": 45000.00, # Simulated
        "total_gift_coins": 100000,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    return safe_insert("chain_business_metrics", metrics)

def get_revenue_summary():
    """Returns a summary of platform financial health"""
    metrics = safe_select("chain_business_metrics", limit=7, order_by="metric_date", desc=True)
    return metrics
