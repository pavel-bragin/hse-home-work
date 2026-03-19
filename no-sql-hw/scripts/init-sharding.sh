#!/bin/bash
set -euo pipefail

echo "=== Waiting for mongos router ==="

wait_for_mongo() {
  local host="$1" port="$2"
  until mongosh --quiet --host "$host" --port "$port" --eval "db.adminCommand({ ping: 1 })" >/dev/null 2>&1; do
    sleep 2
  done
}

wait_for_mongo mongos 27017

sleep 5

echo "=== Registering shards ==="

mongosh --quiet --host mongos --port 27017 --eval '
  function addShardSafe(rsName, host) {
    try {
      sh.addShard(rsName + "/" + host);
      print("✓ Added shard " + rsName);
    } catch (e) {
      if (e.message.includes("already exists") || e.codeName === "ShardAlreadyExists") {
        print("✓ Shard " + rsName + " already exists");
      } else {
        throw e;
      }
    }
  }

  addShardSafe("shard1ReplSet", "shard1a:27018");
  addShardSafe("shard2ReplSet", "shard2a:27018");
'

echo "=== Enabling sharding for database and collection ==="

mongosh --quiet --host mongos --port 27017 --eval '
  try { sh.enableSharding("university"); }
  catch (e) { if (!e.message.includes("already enabled")) throw e; }

  db = db.getSiblingDB("university");
  if (!db.getCollectionNames().includes("students")) {
    db.createCollection("students");
  }

  db.students.createIndex({ faculty: 1, program: 1 });
  db.students.createIndex({ group_number: 1 });
  db.students.createIndex({ updated_at: -1 });

  try {
    sh.shardCollection("university.students", { _id: "hashed" });
  } catch (e) {
    if (!e.message.includes("already sharded")) throw e;
  }
'

echo "MongoDB sharded cluster is ready!"