"""Bounded, explainable transaction anomaly scoring; no automatic blocking."""
from statistics import median

def score_transactions(rows):
    amounts=[abs(float(r.get("amount_cents",0) or 0)) for r in rows]
    baseline=median(amounts) if amounts else 0
    result=[]
    for row, amount in zip(rows,amounts):
        reasons=[]
        if baseline and amount >= baseline*5: reasons.append("amount_at_least_5x_median")
        if str(row.get("status","")).lower() in {"failed","reversed"}: reasons.append("failed_or_reversed_status")
        result.append({"transaction_id":row.get("transaction_id"),"amount_cents":amount,
                       "risk_score":min(100, 50*("amount_at_least_5x_median" in reasons)+25*("failed_or_reversed_status" in reasons)),
                       "reasons":reasons})
    return result
