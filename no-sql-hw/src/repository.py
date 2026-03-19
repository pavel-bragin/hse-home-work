from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from src.db import get_collection


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StudentRepository:
    def __init__(self) -> None:
        self.collection = get_collection()

    def create_student(
        self,
        student_id: str,
        full_name: str,
        faculty: str,
        program: str,
        year: int,
        group_number: str,
        email: str,
    ) -> dict[str, Any]:
        now = utcnow()
        document = {
            "_id": student_id,
            "student_id": student_id,
            "full_name": full_name,
            "faculty": faculty,
            "program": program,
            "year": year,
            "group_number": group_number,
            "contacts": {
                "email": email,
            },
            "gpa": None,
            "status": "active",
            "enrollments": [],
            "created_at": now,
            "updated_at": now,
        }
        self.collection.insert_one(document)
        return document

    def get_student(self, student_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": student_id}, {"_id": 0})

    def list_students(
        self,
        limit: int = 20,
        faculty: str | None = None,
        group_number: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if faculty:
            query["faculty"] = faculty
        if group_number:
            query["group_number"] = group_number
        cursor = self.collection.find(query, {"_id": 0}).sort("updated_at", -1).limit(limit)
        return list(cursor)

    def update_gpa(self, student_id: str, gpa: float) -> dict[str, Any] | None:
        return self.collection.find_one_and_update(
            {"_id": student_id},
            {"$set": {"gpa": gpa, "updated_at": utcnow()}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )

    def add_enrollment(
        self,
        student_id: str,
        course_code: str,
        title: str,
        semester: str,
        credits: int,
        grade: str | None = None,
    ) -> dict[str, Any] | None:
        enrollment = {
            "course_code": course_code,
            "title": title,
            "semester": semester,
            "credits": credits,
            "grade": grade,
        }
        return self.collection.find_one_and_update(
            {"_id": student_id},
            {
                "$push": {"enrollments": enrollment},
                "$set": {"updated_at": utcnow()},
            },
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )

    def faculty_stats(self) -> list[dict[str, Any]]:
        pipeline = [
            {
                "$group": {
                    "_id": "$faculty",
                    "students_total": {"$sum": 1},
                    "avg_gpa": {"$avg": "$gpa"},
                    "active_students": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", "active"]}, 1, 0]
                        }
                    },
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "faculty": "$_id",
                    "students_total": 1,
                    "active_students": 1,
                    "avg_gpa": {"$round": ["$avg_gpa", 2]},
                }
            },
            {"$sort": {"students_total": -1}},
        ]
        return list(self.collection.aggregate(pipeline))
