from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ReplaceOne

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import get_collection

FACULTIES = [
    "Computer Science",
    "Mathematics",
    "Economics",
    "Physics",
    "Linguistics",
]

PROGRAMS = {
    "Computer Science": ["Data Engineering", "Applied AI", "Software Engineering"],
    "Mathematics": ["Statistics", "Financial Mathematics"],
    "Economics": ["Business Analytics", "International Economics"],
    "Physics": ["Materials Science", "Quantum Technologies"],
    "Linguistics": ["Computational Linguistics", "Translation Studies"],
}

COURSES = [
    ("DB101", "Databases", 4),
    ("DS201", "Data Structures", 5),
    ("ML310", "Machine Learning", 5),
    ("ST120", "Probability Theory", 4),
    ("EC205", "Microeconomics", 4),
    ("PH220", "Electromagnetism", 4),
]

FIRST_NAMES = ["Ivan", "Anna", "Maria", "Pavel", "Elena", "Dmitry", "Olga", "Nikita"]
LAST_NAMES = ["Ivanov", "Petrova", "Sidorov", "Kuznetsova", "Smirnov", "Volkova"]


def build_student(index: int) -> dict:
    faculty = random.choice(FACULTIES)
    program = random.choice(PROGRAMS[faculty])
    year = random.randint(1, 4)
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    student_id = f"S{index:06d}"
    now = datetime.now(timezone.utc)

    enrollments = []
    for course_code, title, credits in random.sample(COURSES, k=random.randint(2, 4)):
        enrollments.append(
            {
                "course_code": course_code,
                "title": title,
                "semester": f"2025-{random.choice(['spring', 'autumn'])}",
                "credits": credits,
                "grade": random.choice(["A", "B", "C", "D", None]),
            }
        )

    return {
        "_id": student_id,
        "student_id": student_id,
        "full_name": f"{first_name} {last_name}",
        "faculty": faculty,
        "program": program,
        "year": year,
        "group_number": f"{faculty[:2].upper()}-{year}{random.randint(1, 9)}",
        "contacts": {"email": f"{student_id.lower()}@university.local"},
        "gpa": round(random.uniform(2.8, 5.0), 2),
        "status": random.choices(["active", "academic_leave", "graduated"], weights=[85, 5, 10])[0],
        "enrollments": enrollments,
        "created_at": now,
        "updated_at": now,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic students into MongoDB")
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()

    collection = get_collection()

    operations = []
    for index in range(1, args.count + 1):
        document = build_student(index)
        operations.append(ReplaceOne({"_id": document["_id"]}, document, upsert=True))

        if len(operations) >= args.batch_size:
            collection.bulk_write(operations, ordered=False)
            operations.clear()

    if operations:
        collection.bulk_write(operations, ordered=False)

    print(f"Seed completed. Students in collection: {collection.count_documents({})}")


if __name__ == "__main__":
    main()
