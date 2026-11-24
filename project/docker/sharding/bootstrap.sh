#!/usr/bin/env bash
set -euo pipefail

wait_for_primary() {
  local host="$1"
  local port="$2"
  local deadline=$((SECONDS + 120))
  until mongosh --host "$host:$port" --quiet --eval 'rs.isMaster().ismaster' 2>/dev/null | grep -q true; do
    if (( SECONDS >= deadline )); then
      echo "Timed out waiting for $host:$port to become primary" >&2
      exit 1
    fi
    sleep 2
  done
}

init_replica_set() {
  local host="$1"
  local port="$2"
  local config="$3"
  mongosh --host "$host:$port" --quiet --eval \
    "try { rs.status(); } catch (e) { rs.initiate($config); }" >/dev/null
  wait_for_primary "$host" "$port"
}

init_replica_set cfg1 27019 \
  '{_id:"cfgrs",configsvr:true,members:[{_id:0,host:"cfg1:27019"},{_id:1,host:"cfg2:27019"},{_id:2,host:"cfg3:27019"}]}'
init_replica_set shard1 27018 \
  '{_id:"sh1rs",members:[{_id:0,host:"shard1:27018"}]}'
init_replica_set shard2 27018 \
  '{_id:"sh2rs",members:[{_id:0,host:"shard2:27018"}]}'
