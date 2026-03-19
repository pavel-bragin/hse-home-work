from __future__ import annotations

import argparse
import json
from typing import Any

from pymongo.errors import DuplicateKeyError

from src.repository import StudentRepository


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI for sharded university MongoDB")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("add-student", help="Create a student document")
    create_parser.add_argument("--student-id", required=True)
    create_parser.add_argument("--full-name", required=True)
    create_parser.add_argument("--faculty", required=True)
    create_parser.add_argument("--program", required=True)
    create_parser.add_argument("--year", type=int, required=True)
    create_parser.add_argument("--group-number", required=True)
    create_parser.add_argument("--email", required=True)

    get_parser = subparsers.add_parser("get-student", help="Get one student by id")
    get_parser.add_argument("--student-id", required=True)

    list_parser = subparsers.add_parser("list-students", help="List students")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--faculty")
    list_parser.add_argument("--group-number")

    gpa_parser = subparsers.add_parser("update-gpa", help="Update GPA")
    gpa_parser.add_argument("--student-id", required=True)
    gpa_parser.add_argument("--gpa", type=float, required=True)

    enrollment_parser = subparsers.add_parser("add-enrollment", help="Add course enrollment")
    enrollment_parser.add_argument("--student-id", required=True)
    enrollment_parser.add_argument("--course-code", required=True)
    enrollment_parser.add_argument("--title", required=True)
    enrollment_parser.add_argument("--semester", required=True)
    enrollment_parser.add_argument("--credits", type=int, required=True)
    enrollment_parser.add_argument("--grade")

    subparsers.add_parser("faculty-stats", help="Aggregate statistics by faculty")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    repository = StudentRepository()

    try:
        if args.command == "add-student":
            student = repository.create_student(
                student_id=args.student_id,
                full_name=args.full_name,
                faculty=args.faculty,
                program=args.program,
                year=args.year,
                group_number=args.group_number,
                email=args.email,
            )
            print_json(student)
        elif args.command == "get-student":
            student = repository.get_student(args.student_id)
            print_json(student or {"error": "student not found"})
        elif args.command == "list-students":
            students = repository.list_students(
                limit=args.limit,
                faculty=args.faculty,
                group_number=args.group_number,
            )
            print_json(students)
        elif args.command == "update-gpa":
            result = repository.update_gpa(args.student_id, args.gpa)
            print_json(result or {"error": "student not found"})
        elif args.command == "add-enrollment":
            result = repository.add_enrollment(
                student_id=args.student_id,
                course_code=args.course_code,
                title=args.title,
                semester=args.semester,
                credits=args.credits,
                grade=args.grade,
            )
            print_json(result or {"error": "student not found"})
        elif args.command == "faculty-stats":
            print_json(repository.faculty_stats())
    except DuplicateKeyError:
        print_json({"error": "student with the same id already exists"})


if __name__ == "__main__":
    main()
