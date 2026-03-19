db = db.getSiblingDB("university");
printjson(db.students.getShardDistribution());
