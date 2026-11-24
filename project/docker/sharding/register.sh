#!/usr/bin/env bash
set -euo pipefail

mongosh --host router:27017 --quiet --eval '
  const current = db.adminCommand({listShards:1}).shards.map(shard => shard._id);
  if (!current.includes("sh1rs")) db.adminCommand({addShard:"sh1rs/shard1:27018"});
  if (!current.includes("sh2rs")) db.adminCommand({addShard:"sh2rs/shard2:27018"});
  printjson(db.adminCommand({listShards:1}));
'
