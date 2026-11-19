"""Explainable IOC correlation primitives; read-only over supplied records."""
from collections import defaultdict

def correlate(records):
    """Group records by normalized IOC value and return shared-indicator links."""
    index=defaultdict(list)
    for record in records:
        for ioc in record.get("iocs",[]) or []:
            value=str(ioc.get("value","")).strip().lower()
            kind=str(ioc.get("type","unknown")).lower()
            if value:
                index[(kind,value)].append(str(record.get("_id",record.get("title","unknown"))))
    edges=[]
    for (kind,value), ids in index.items():
        unique=list(dict.fromkeys(ids))
        if len(unique)>1:
            edges.append({"indicator_type":kind,"indicator":value,"records":unique,"degree":len(unique)})
    return sorted(edges,key=lambda x:(-x["degree"],x["indicator"]))
