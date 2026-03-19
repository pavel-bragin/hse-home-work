from __future__ import annotations

import argparse
import itertools
import math
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db import get_client

OPERATION_LABELS = {
    "point_read": "Point read",
    "targeted_update": "Targeted update",
    "read_modify_write": "Read-modify-write",
    "insert": "Insert",
    "filtered_scan": "Filtered scan",
    "faculty_aggregation": "Faculty aggregation",
}

WORKLOADS = {
    "a_balanced": {
        "description": "Classic A profile: 50% point reads and 50% targeted updates.",
        "mix": {
            "point_read": 0.50,
            "targeted_update": 0.50,
        },
    },
    "b_read_heavy": {
        "description": "Classic B profile: 95% point reads and 5% targeted updates.",
        "mix": {
            "point_read": 0.95,
            "targeted_update": 0.05,
        },
    },
    "f_read_modify_write": {
        "description": "F style profile with read-modify-write transactions.",
        "mix": {
            "point_read": 0.50,
            "read_modify_write": 0.50,
        },
    },
    "analytics_mixed": {
        "description": "Application-like mixed workload with inserts and scatter-gather analytics.",
        "mix": {
            "point_read": 0.45,
            "targeted_update": 0.20,
            "insert": 0.15,
            "filtered_scan": 0.15,
            "faculty_aggregation": 0.05,
        },
    },
}

COLORS = {
    "a_balanced": "#1f77b4",
    "b_read_heavy": "#2ca02c",
    "f_read_modify_write": "#ff7f0e",
    "analytics_mixed": "#d62728",
}


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (q / 100) * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def parse_concurrency_levels(raw_value: str) -> list[int]:
    levels = []
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        level = int(item)
        if level <= 0:
            raise ValueError("Concurrency levels must be positive integers.")
        levels.append(level)
    if not levels:
        raise ValueError("At least one concurrency level is required.")
    return sorted(set(levels))


def build_sampler(mix: dict[str, float]) -> list[tuple[float, str]]:
    cumulative = 0.0
    sampler = []
    for operation_name, weight in mix.items():
        cumulative += weight
        sampler.append((cumulative, operation_name))
    if not math.isclose(cumulative, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError(f"Workload weights must sum to 1.0, got {cumulative:.4f}")
    return sampler


def pick_operation(sampler: list[tuple[float, str]], rng: random.Random) -> str:
    probe = rng.random()
    for threshold, operation_name in sampler:
        if probe <= threshold:
            return operation_name
    return sampler[-1][1]


def split_operations(total_operations: int, workers: int) -> list[int]:
    base, remainder = divmod(total_operations, workers)
    distribution = [base] * workers
    for index in range(remainder):
        distribution[index] += 1
    return [chunk for chunk in distribution if chunk > 0]


def build_insert_document(student_id: str, rng: random.Random, now: datetime) -> dict:
    faculty = rng.choice(
        [
            "Computer Science",
            "Mathematics",
            "Economics",
            "Physics",
            "Linguistics",
        ]
    )
    program = {
        "Computer Science": ["Data Engineering", "Applied AI", "Software Engineering"],
        "Mathematics": ["Statistics", "Financial Mathematics"],
        "Economics": ["Business Analytics", "International Economics"],
        "Physics": ["Materials Science", "Quantum Technologies"],
        "Linguistics": ["Computational Linguistics", "Translation Studies"],
    }[faculty]
    return {
        "_id": student_id,
        "student_id": student_id,
        "full_name": f"Benchmark Student {student_id}",
        "faculty": faculty,
        "program": rng.choice(program),
        "year": rng.randint(1, 4),
        "group_number": f"{faculty[:2].upper()}-{rng.randint(10, 49)}",
        "contacts": {"email": f"{student_id.lower()}@benchmark.local"},
        "gpa": round(rng.uniform(3.0, 5.0), 2),
        "status": "active",
        "enrollments": [],
        "created_at": now,
        "updated_at": now,
        "benchmark_generated": True,
    }


class BenchmarkRunner:
    def __init__(self, collection, student_ids: list[str], faculties: list[str]) -> None:
        self.collection = collection
        self.student_ids = student_ids
        self.faculties = faculties
        self.insert_sequence = itertools.count(1)
        self.insert_lock = threading.Lock()

    def next_insert_id(self, run_key: str) -> str:
        with self.insert_lock:
            return f"B{run_key}-{next(self.insert_sequence):09d}"

    def point_read(self, rng: random.Random) -> None:
        student_id = rng.choice(self.student_ids)
        self.collection.find_one({"_id": student_id}, {"_id": 1, "faculty": 1, "gpa": 1})

    def targeted_update(self, rng: random.Random) -> None:
        student_id = rng.choice(self.student_ids)
        self.collection.update_one(
            {"_id": student_id},
            {
                "$inc": {"benchmark_counter": 1},
                "$set": {
                    "gpa": round(rng.uniform(3.0, 5.0), 2),
                    "updated_at": datetime.now(timezone.utc),
                },
            },
        )

    def read_modify_write(self, rng: random.Random) -> None:
        student_id = rng.choice(self.student_ids)
        document = self.collection.find_one({"_id": student_id}, {"gpa": 1})
        gpa = 4.0
        if document and document.get("gpa") is not None:
            gpa = float(document["gpa"])
        new_gpa = round(min(5.0, max(2.0, gpa + rng.uniform(-0.2, 0.2))), 2)
        self.collection.update_one(
            {"_id": student_id},
            {"$set": {"gpa": new_gpa, "updated_at": datetime.now(timezone.utc)}},
        )

    def insert(self, rng: random.Random, run_key: str) -> None:
        now = datetime.now(timezone.utc)
        student_id = self.next_insert_id(run_key)
        self.collection.insert_one(build_insert_document(student_id, rng, now))

    def filtered_scan(self, rng: random.Random) -> None:
        faculty = rng.choice(self.faculties)
        list(
            self.collection.find(
                {"faculty": faculty},
                {"_id": 1, "full_name": 1, "updated_at": 1},
            )
            .sort("updated_at", -1)
            .limit(20)
        )

    def faculty_aggregation(self) -> None:
        pipeline = [
            {
                "$group": {
                    "_id": "$faculty",
                    "students_total": {"$sum": 1},
                    "avg_gpa": {"$avg": "$gpa"},
                }
            },
            {"$sort": {"students_total": -1}},
        ]
        list(self.collection.aggregate(pipeline))

    def execute_operation(self, operation_name: str, rng: random.Random, run_key: str) -> None:
        if operation_name == "point_read":
            self.point_read(rng)
        elif operation_name == "targeted_update":
            self.targeted_update(rng)
        elif operation_name == "read_modify_write":
            self.read_modify_write(rng)
        elif operation_name == "insert":
            self.insert(rng, run_key)
        elif operation_name == "filtered_scan":
            self.filtered_scan(rng)
        elif operation_name == "faculty_aggregation":
            self.faculty_aggregation()
        else:
            raise ValueError(f"Unsupported operation: {operation_name}")


def combine_worker_stats(results: list[dict[str, dict[str, list[float]]]]) -> tuple[dict[str, list[float]], dict[str, int], dict[str, int]]:
    latencies: dict[str, list[float]] = {}
    counts: dict[str, int] = {}
    errors: dict[str, int] = {}

    for worker_result in results:
        for operation_name, values in worker_result["latencies"].items():
            latencies.setdefault(operation_name, []).extend(values)
        for operation_name, value in worker_result["counts"].items():
            counts[operation_name] = counts.get(operation_name, 0) + value
        for operation_name, value in worker_result["errors"].items():
            errors[operation_name] = errors.get(operation_name, 0) + value

    return latencies, counts, errors


def run_phase(
    runner: BenchmarkRunner,
    workload_name: str,
    mix: dict[str, float],
    total_operations: int,
    concurrency: int,
    repeat_index: int,
    phase_name: str,
) -> tuple[dict, list[dict]]:
    sampler = build_sampler(mix)
    run_key = f"{workload_name}-{phase_name}-c{concurrency}-r{repeat_index}"

    def worker(worker_idx: int, operations_to_run: int) -> dict[str, dict[str, list[float]]]:
        rng = random.Random(hash((run_key, worker_idx)) & 0xFFFFFFFF)
        local_latencies: dict[str, list[float]] = {}
        local_counts: dict[str, int] = {}
        local_errors: dict[str, int] = {}

        for _ in range(operations_to_run):
            operation_name = pick_operation(sampler, rng)
            started = time.perf_counter()
            try:
                runner.execute_operation(operation_name, rng, run_key)
                local_counts[operation_name] = local_counts.get(operation_name, 0) + 1
            except Exception:
                local_errors[operation_name] = local_errors.get(operation_name, 0) + 1
            finally:
                latency_ms = (time.perf_counter() - started) * 1000
                local_latencies.setdefault(operation_name, []).append(latency_ms)

        return {
            "latencies": local_latencies,
            "counts": local_counts,
            "errors": local_errors,
        }

    started = time.perf_counter()
    chunks = split_operations(total_operations, concurrency)
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(worker, worker_idx, operations_to_run)
            for worker_idx, operations_to_run in enumerate(chunks)
        ]
        worker_results = [future.result() for future in futures]
    elapsed = time.perf_counter() - started

    latencies_by_operation, counts_by_operation, errors_by_operation = combine_worker_stats(worker_results)
    all_latencies = [value for values in latencies_by_operation.values() for value in values]

    run_row = {
        "phase": phase_name,
        "workload": workload_name,
        "description": WORKLOADS[workload_name]["description"],
        "concurrency": concurrency,
        "repeat": repeat_index,
        "requested_operations": total_operations,
        "completed_operations": sum(counts_by_operation.values()),
        "error_operations": sum(errors_by_operation.values()),
        "duration_sec": round(elapsed, 3),
        "throughput_ops_sec": round(sum(counts_by_operation.values()) / elapsed, 2) if elapsed else 0.0,
        "avg_latency_ms": round(mean(all_latencies), 2),
        "median_latency_ms": round(percentile(all_latencies, 50), 2),
        "p95_latency_ms": round(percentile(all_latencies, 95), 2),
        "p99_latency_ms": round(percentile(all_latencies, 99), 2),
        "max_latency_ms": round(max(all_latencies) if all_latencies else 0.0, 2),
        "error_rate_pct": round((sum(errors_by_operation.values()) / total_operations) * 100, 3),
    }

    operation_rows = []
    for operation_name in sorted(latencies_by_operation):
        op_latencies = latencies_by_operation[operation_name]
        total_for_operation = len(op_latencies)
        operation_rows.append(
            {
                "phase": phase_name,
                "workload": workload_name,
                "description": WORKLOADS[workload_name]["description"],
                "concurrency": concurrency,
                "repeat": repeat_index,
                "operation": operation_name,
                "operation_label": OPERATION_LABELS[operation_name],
                "operations": total_for_operation,
                "completed_operations": counts_by_operation.get(operation_name, 0),
                "error_operations": errors_by_operation.get(operation_name, 0),
                "share_pct": round((total_for_operation / total_operations) * 100, 2),
                "avg_latency_ms": round(mean(op_latencies), 2),
                "median_latency_ms": round(percentile(op_latencies, 50), 2),
                "p95_latency_ms": round(percentile(op_latencies, 95), 2),
                "p99_latency_ms": round(percentile(op_latencies, 99), 2),
                "max_latency_ms": round(max(op_latencies), 2),
            }
        )

    return run_row, operation_rows


def aggregate_results(runs_df: pd.DataFrame, operations_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    measured_runs = runs_df[runs_df["phase"] == "measure"].copy()
    measured_ops = operations_df[operations_df["phase"] == "measure"].copy()

    summary_df = (
        measured_runs.groupby(["workload", "description", "concurrency"], as_index=False)
        .agg(
            repeats=("repeat", "count"),
            requested_operations=("requested_operations", "mean"),
            completed_operations=("completed_operations", "mean"),
            error_rate_pct=("error_rate_pct", "mean"),
            duration_sec_mean=("duration_sec", "mean"),
            throughput_ops_sec_mean=("throughput_ops_sec", "mean"),
            throughput_ops_sec_std=("throughput_ops_sec", "std"),
            avg_latency_ms_mean=("avg_latency_ms", "mean"),
            p95_latency_ms_mean=("p95_latency_ms", "mean"),
            p99_latency_ms_mean=("p99_latency_ms", "mean"),
            max_latency_ms_mean=("max_latency_ms", "mean"),
        )
        .fillna(0.0)
    )

    operation_summary_df = (
        measured_ops.groupby(["workload", "concurrency", "operation", "operation_label"], as_index=False)
        .agg(
            repeats=("repeat", "count"),
            operations=("operations", "mean"),
            share_pct=("share_pct", "mean"),
            avg_latency_ms=("avg_latency_ms", "mean"),
            p95_latency_ms=("p95_latency_ms", "mean"),
            p99_latency_ms=("p99_latency_ms", "mean"),
        )
        .fillna(0.0)
    )

    return summary_df, operation_summary_df


def render_plots(summary_df: pd.DataFrame, operation_summary_df: pd.DataFrame, output_dir: Path) -> None:
    workloads = list(WORKLOADS.keys())

    plt.figure(figsize=(11, 6))
    for workload_name in workloads:
        subset = summary_df[summary_df["workload"] == workload_name].sort_values("concurrency")
        plt.errorbar(
            subset["concurrency"],
            subset["throughput_ops_sec_mean"],
            yerr=subset["throughput_ops_sec_std"],
            marker="o",
            linewidth=2,
            capsize=4,
            color=COLORS[workload_name],
            label=workload_name,
        )
    plt.title("Throughput scaling by workload")
    plt.xlabel("Concurrency")
    plt.ylabel("Throughput, ops/sec")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "throughput_vs_concurrency.png", dpi=180)
    plt.close()

    plt.figure(figsize=(11, 6))
    for workload_name in workloads:
        subset = summary_df[summary_df["workload"] == workload_name].sort_values("concurrency")
        plt.plot(
            subset["concurrency"],
            subset["p95_latency_ms_mean"],
            marker="o",
            linewidth=2,
            color=COLORS[workload_name],
            label=f"{workload_name} p95",
        )
        plt.plot(
            subset["concurrency"],
            subset["p99_latency_ms_mean"],
            marker="x",
            linestyle="--",
            linewidth=1.5,
            color=COLORS[workload_name],
            alpha=0.75,
        )
    plt.title("Tail latency vs concurrency")
    plt.xlabel("Concurrency")
    plt.ylabel("Latency, ms")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "latency_vs_concurrency.png", dpi=180)
    plt.close()

    plt.figure(figsize=(11, 6))
    for workload_name in workloads:
        subset = summary_df[summary_df["workload"] == workload_name]
        plt.scatter(
            subset["p95_latency_ms_mean"],
            subset["throughput_ops_sec_mean"],
            s=110,
            color=COLORS[workload_name],
            label=workload_name,
            alpha=0.9,
        )
        for _, row in subset.iterrows():
            plt.annotate(
                f"c={int(row['concurrency'])}",
                (row["p95_latency_ms_mean"], row["throughput_ops_sec_mean"]),
                textcoords="offset points",
                xytext=(6, 4),
                fontsize=8,
            )
    plt.title("Throughput / p95 latency trade-off")
    plt.xlabel("p95 latency, ms")
    plt.ylabel("Throughput, ops/sec")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "throughput_latency_tradeoff.png", dpi=180)
    plt.close()

    highest_concurrency = int(summary_df["concurrency"].max())
    heatmap_df = (
        operation_summary_df[operation_summary_df["concurrency"] == highest_concurrency]
        .pivot(index="workload", columns="operation_label", values="p95_latency_ms")
        .reindex(workloads)
    )

    plt.figure(figsize=(12, 5.5))
    image = plt.imshow(heatmap_df.fillna(0.0).values, aspect="auto", cmap="YlOrRd")
    plt.title(f"p95 latency by operation at concurrency {highest_concurrency}")
    plt.xticks(range(len(heatmap_df.columns)), heatmap_df.columns, rotation=25, ha="right")
    plt.yticks(range(len(heatmap_df.index)), heatmap_df.index)
    plt.colorbar(image, label="p95 latency, ms")
    for row_idx, workload_name in enumerate(heatmap_df.index):
        for col_idx, operation_label in enumerate(heatmap_df.columns):
            value = heatmap_df.loc[workload_name, operation_label]
            if pd.notna(value):
                plt.text(col_idx, row_idx, f"{value:.1f}", ha="center", va="center", fontsize=8)
    plt.tight_layout()
    plt.savefig(output_dir / "operation_latency_heatmap.png", dpi=180)
    plt.close()

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    for workload_name in workloads:
        subset = summary_df[summary_df["workload"] == workload_name].sort_values("concurrency")
        axes[0, 0].plot(
            subset["concurrency"],
            subset["throughput_ops_sec_mean"],
            marker="o",
            linewidth=2,
            color=COLORS[workload_name],
            label=workload_name,
        )
        axes[0, 1].plot(
            subset["concurrency"],
            subset["p95_latency_ms_mean"],
            marker="o",
            linewidth=2,
            color=COLORS[workload_name],
            label=workload_name,
        )

    axes[0, 0].set_title("Throughput scaling")
    axes[0, 0].set_xlabel("Concurrency")
    axes[0, 0].set_ylabel("Ops/sec")
    axes[0, 0].grid(alpha=0.25)
    axes[0, 0].legend()

    axes[0, 1].set_title("p95 latency scaling")
    axes[0, 1].set_xlabel("Concurrency")
    axes[0, 1].set_ylabel("Latency, ms")
    axes[0, 1].grid(alpha=0.25)

    top_ops = (
        operation_summary_df[operation_summary_df["concurrency"] == highest_concurrency]
        .sort_values(["workload", "share_pct"], ascending=[True, False])
        .copy()
    )
    pivot_mix = top_ops.pivot(index="workload", columns="operation_label", values="share_pct").fillna(0.0)
    cumulative = pd.Series([0.0] * len(pivot_mix.index), index=pivot_mix.index)
    palette = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#b279a2"]
    for color, operation_label in zip(palette, pivot_mix.columns):
        axes[1, 0].bar(
            pivot_mix.index,
            pivot_mix[operation_label],
            bottom=cumulative,
            label=operation_label,
            color=color,
        )
        cumulative = cumulative + pivot_mix[operation_label]
    axes[1, 0].set_title(f"Observed operation mix at concurrency {highest_concurrency}")
    axes[1, 0].set_ylabel("Share, %")
    axes[1, 0].tick_params(axis="x", rotation=15)
    axes[1, 0].legend(fontsize=8)

    heatmap_values = heatmap_df.fillna(0.0).values
    axes[1, 1].imshow(heatmap_values, aspect="auto", cmap="YlOrRd")
    axes[1, 1].set_title(f"Operation p95 heatmap at concurrency {highest_concurrency}")
    axes[1, 1].set_xticks(range(len(heatmap_df.columns)))
    axes[1, 1].set_xticklabels(heatmap_df.columns, rotation=25, ha="right")
    axes[1, 1].set_yticks(range(len(heatmap_df.index)))
    axes[1, 1].set_yticklabels(heatmap_df.index)
    for row_idx, workload_name in enumerate(heatmap_df.index):
        for col_idx, operation_label in enumerate(heatmap_df.columns):
            value = heatmap_df.loc[workload_name, operation_label]
            if pd.notna(value):
                axes[1, 1].text(col_idx, row_idx, f"{value:.1f}", ha="center", va="center", fontsize=8)

    fig.suptitle("MongoDB sharded cluster benchmark dashboard", fontsize=16)
    plt.tight_layout()
    plt.savefig(output_dir / "benchmark_dashboard.png", dpi=180)
    plt.close(fig)


def print_console_summary(summary_df: pd.DataFrame) -> None:
    printable = summary_df[
        [
            "workload",
            "concurrency",
            "repeats",
            "throughput_ops_sec_mean",
            "p95_latency_ms_mean",
            "p99_latency_ms_mean",
            "error_rate_pct",
        ]
    ].copy()
    printable = printable.sort_values(["workload", "concurrency"])
    print(printable.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Quality benchmark for the MongoDB sharded university cluster")
    parser.add_argument("--operations-per-run", type=int, default=8000)
    parser.add_argument("--warmup-operations", type=int, default=1500)
    parser.add_argument("--concurrency-levels", default="1,4,8,16,32,64")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--sample-size", type=int, default=10000)
    parser.add_argument("--output-dir", default="benchmark_results")
    args = parser.parse_args()

    if args.operations_per_run < 100:
        raise ValueError("--operations-per-run must be at least 100.")
    if args.warmup_operations < 0:
        raise ValueError("--warmup-operations cannot be negative.")
    if args.repeats <= 0:
        raise ValueError("--repeats must be positive.")

    concurrency_levels = parse_concurrency_levels(args.concurrency_levels)

    settings = get_settings()
    client = get_client()
    collection = client[settings.database_name][settings.collection_name]

    student_ids = [item["_id"] for item in collection.find({}, {"_id": 1}).limit(args.sample_size)]
    if len(student_ids) < 1000:
        raise RuntimeError("Need at least 1000 seeded students before running the benchmark.")

    faculties = sorted(collection.distinct("faculty"))
    if not faculties:
        raise RuntimeError("No faculty values found; seed the collection before benchmarking.")

    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    runner = BenchmarkRunner(collection=collection, student_ids=student_ids, faculties=faculties)

    run_rows: list[dict] = []
    operation_rows: list[dict] = []

    total_runs = len(WORKLOADS) * len(concurrency_levels) * args.repeats
    completed_runs = 0

    for workload_name, workload_config in WORKLOADS.items():
        mix = workload_config["mix"]
        for concurrency in concurrency_levels:
            for repeat_index in range(1, args.repeats + 1):
                completed_runs += 1
                print(
                    f"[{completed_runs}/{total_runs}] workload={workload_name} "
                    f"concurrency={concurrency} repeat={repeat_index}"
                )

                if args.warmup_operations:
                    warmup_run_row, warmup_operation_rows = run_phase(
                        runner=runner,
                        workload_name=workload_name,
                        mix=mix,
                        total_operations=args.warmup_operations,
                        concurrency=concurrency,
                        repeat_index=repeat_index,
                        phase_name="warmup",
                    )
                    run_rows.append(warmup_run_row)
                    operation_rows.extend(warmup_operation_rows)

                measure_run_row, measure_operation_rows = run_phase(
                    runner=runner,
                    workload_name=workload_name,
                    mix=mix,
                    total_operations=args.operations_per_run,
                    concurrency=concurrency,
                    repeat_index=repeat_index,
                    phase_name="measure",
                )
                run_rows.append(measure_run_row)
                operation_rows.extend(measure_operation_rows)

    runs_df = pd.DataFrame(run_rows)
    operations_df = pd.DataFrame(operation_rows)
    summary_df, operation_summary_df = aggregate_results(runs_df, operations_df)

    runs_df.to_csv(output_dir / "benchmark_runs.csv", index=False)
    operations_df.to_csv(output_dir / "benchmark_operation_breakdown.csv", index=False)
    summary_df.to_csv(output_dir / "benchmark_summary.csv", index=False)
    operation_summary_df.to_csv(output_dir / "benchmark_operation_summary.csv", index=False)

    render_plots(summary_df, operation_summary_df, output_dir)
    print_console_summary(summary_df)
    print(f"Artifacts saved to {output_dir}")


if __name__ == "__main__":
    main()
