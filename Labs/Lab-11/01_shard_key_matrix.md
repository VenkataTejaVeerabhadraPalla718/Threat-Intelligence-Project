# Lab 11.1 Shard key decision matrix (e-commerce orders)

| Key | Cardinality | Distribution | Query targeting | Verdict |
|---|---|---|---|---|
| order_id | High | Even | Poor: customer queries hit all shards | No |
| customer_id | High | Uneven (heavy buyers = jumbo chunks) | Good | Maybe |
| order_date | Low per day | Hot-spot: all new orders go to one shard | Good for ranges only | No |
| hashed customer_id | High | Even | Good: one customer = one shard | **Yes** |

Recommendation: hashed customer_id. Writes spread evenly, and "orders of customer X" targets one shard.
Trade-off: range queries on customer_id become scatter-gather.

Activity (resharding, MongoDB 5.0+): reshardCollection copies data into a new layout online,
then briefly blocks writes at the end. It needs spare disk and IO, so run it off-peak.