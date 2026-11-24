from backend.threat_correlation import correlate
from backend.transaction_intelligence import score_transactions

def test_correlate_shared_indicator():
    rows=[{"_id":"a","iocs":[{"type":"ip","value":"1.2.3.4"}]},
          {"_id":"b","iocs":[{"type":"ip","value":"1.2.3.4"}]}]
    out=correlate(rows)
    assert len(out)==1 and out[0]["degree"]==2

def test_transaction_scoring_is_explainable():
    out=score_transactions([
      {"transaction_id":"a","amount_cents":100,"status":"committed"},
      {"transaction_id":"c","amount_cents":100,"status":"committed"},
      {"transaction_id":"b","amount_cents":1000,"status":"failed"}])
    assert out[2]["risk_score"]==75
    assert "failed_or_reversed_status" in out[2]["reasons"]
