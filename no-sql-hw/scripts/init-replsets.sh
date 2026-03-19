#!/bin/bash
set -euo pipefail

echo "=== Waiting for MongoDB nodes to accept connections ==="

wait_for_mongo() {
  local host="$1" port="$2"
  until mongosh --quiet --host "$host" --port "$port" --eval "db.adminCommand({ ping: 1 })" >/dev/null 2>&1; do
    sleep 2
  done
}

wait_for_primary() {
  local host="$1" port="$2"
  until mongosh --quiet --host "$host" --port "$port" --eval '
    const hello = db.adminCommand({ hello: 1 });
    if (!hello.isWritablePrimary) quit(1);
  ' >/dev/null 2>&1; do
    sleep 2
  done
}

wait_for_mongo cfgsvr1 27019
wait_for_mongo shard1a 27018
wait_for_mongo shard2a 27018

echo "=== Initializing replica sets ==="

mongosh --quiet --host cfgsvr1 --port 27019 --eval '
  try { rs.status(); } catch (_) {
    rs.initiate({
      _id: "cfgReplSet",
      configsvr: true,
      members: [{ _id: 0, host: "cfgsvr1:27019" }]
    });
  }
'

mongosh --quiet --host shard1a --port 27018 --eval '
  try { rs.status(); } catch (_) {
    rs.initiate({
      _id: "shard1ReplSet",
      members: [{ _id: 0, host: "shard1a:27018" }]
    });
  }
'

mongosh --quiet --host shard2a --port 27018 --eval '
  try { rs.status(); } catch (_) {
    rs.initiate({
      _id: "shard2ReplSet",
      members: [{ _id: 0, host: "shard2a:27018" }]
    });
  }
'

echo "=== Waiting for replica sets to elect primaries ==="
wait_for_primary cfgsvr1 27019
wait_for_primary shard1a 27018
wait_for_primary shard2a 27018

echo "Replica sets initialized successfully."