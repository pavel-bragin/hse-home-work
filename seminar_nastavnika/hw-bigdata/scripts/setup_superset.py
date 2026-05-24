import json
import os
import time
from typing import Any

import requests


SUPERSET_URL = os.getenv("SUPERSET_URL", "http://localhost:8088").rstrip("/")
USERNAME = os.getenv("SUPERSET_USERNAME", "admin")
PASSWORD = os.getenv("SUPERSET_PASSWORD", "admin")
DATABASE_NAME = os.getenv("SUPERSET_DATABASE_NAME", "Oil Analytics PostgreSQL")
DATABASE_URI = os.getenv(
    "SUPERSET_DATABASE_URI",
    "postgresql+psycopg2://analytics:analytics@postgres:5432/oil_analytics",
)


def wait_for_superset(session: requests.Session) -> None:
    for _ in range(60):
        try:
            response = session.get(f"{SUPERSET_URL}/health", timeout=5)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise RuntimeError("Superset is not available")


def request_json(
    session: requests.Session,
    method: str,
    path: str,
    expected: tuple[int, ...] = (200, 201),
    **kwargs: Any,
) -> dict[str, Any]:
    response = session.request(method, f"{SUPERSET_URL}{path}", timeout=30, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(f"{method} {path} failed: {response.status_code} {response.text}")
    if not response.text:
        return {}
    return response.json()


def login(session: requests.Session) -> None:
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "provider": "db",
        "refresh": True,
    }
    token = request_json(session, "POST", "/api/v1/security/login", json=payload)["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})

    csrf = request_json(session, "GET", "/api/v1/security/csrf_token/")["result"]
    session.headers.update({"X-CSRFToken": csrf, "Referer": SUPERSET_URL})


def created_object_id(result: dict[str, Any]) -> int:
    if "id" in result:
        return int(result["id"])
    return int(result["result"]["id"])


def find_object(session: requests.Session, resource: str, column: str, value: str) -> dict[str, Any] | None:
    if " " not in value:
        query = f"(filters:!((col:{column},opr:eq,value:{value})))"
        result = request_json(
            session,
            "GET",
            f"/api/v1/{resource}/",
            params={"q": query, "page_size": 100},
        )
        rows = result.get("result", [])
        if rows:
            return rows[0]

    page = 0
    while True:
        result = request_json(
            session,
            "GET",
            f"/api/v1/{resource}/",
            params={"page": page, "page_size": 100},
        )
        rows = result.get("result", [])
        for row in rows:
            if str(row.get(column)) == value:
                return row

        total = int(result.get("count", len(rows)))
        page += 1
        if not rows or page * 100 >= total:
            break
    return None


def create_or_get(
    session: requests.Session,
    resource: str,
    column: str,
    value: str,
    path: str,
    payload: dict[str, Any],
) -> int:
    for attempt in range(5):
        existing = find_object(session, resource, column, value)
        if existing:
            return int(existing["id"])

        response = session.post(f"{SUPERSET_URL}{path}", timeout=30, json=payload)
        if response.status_code in {200, 201}:
            return created_object_id(response.json())
        if response.status_code == 422 and attempt < 4:
            time.sleep(1)
            continue
        raise RuntimeError(f"POST {path} failed: {response.status_code} {response.text}")

    raise RuntimeError(f"POST {path} failed: could not create or find {resource} {value!r}")


def ensure_database(session: requests.Session) -> int:
    payload = {
        "database_name": DATABASE_NAME,
        "sqlalchemy_uri": DATABASE_URI,
        "expose_in_sqllab": True,
        "allow_ctas": True,
        "allow_cvas": True,
        "allow_dml": False,
    }
    return create_or_get(session, "database", "database_name", DATABASE_NAME, "/api/v1/database/", payload)


def ensure_dataset(session: requests.Session, database_id: int, table_name: str) -> int:
    payload = {
        "database": database_id,
        "schema": "public",
        "table_name": table_name,
    }
    return create_or_get(session, "dataset", "table_name", table_name, "/api/v1/dataset/", payload)


def table_order_by(column: str, ascending: bool = True) -> list[str]:
    return [json.dumps([column, ascending])]


def metric(label: str, column: str, aggregate: str = "SUM") -> dict[str, Any]:
    return {
        "aggregate": aggregate,
        "column": {"column_name": column},
        "expressionType": "SIMPLE",
        "label": f"{aggregate}({column})",
        "sqlExpression": None,
    }


def chart_params(dataset_id: int, table_name: str, viz_type: str, overrides: dict[str, Any]) -> str:
    datasource = f"{dataset_id}__table"
    params = {
        "datasource": datasource,
        "viz_type": viz_type,
        "slice_id": None,
        "adhoc_filters": [],
        "row_limit": 10000,
        "order_desc": True,
        "show_legend": True,
        "color_scheme": "supersetColors",
        "table_name": table_name,
    }
    params.update(overrides)
    return json.dumps(params)


def query_context(dataset_id: int, viz_type: str, params: str) -> str:
    return json.dumps(
        {
            "datasource": {"id": dataset_id, "type": "table"},
            "force": False,
            "queries": [],
            "form_data": json.loads(params),
            "result_format": "json",
            "result_type": "full",
            "viz_type": viz_type,
        }
    )


def ensure_chart(
    session: requests.Session,
    name: str,
    dataset_id: int,
    table_name: str,
    viz_type: str,
    overrides: dict[str, Any],
) -> int:
    params = chart_params(dataset_id, table_name, viz_type, overrides)
    payload = {
        "slice_name": name,
        "viz_type": viz_type,
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "params": params,
        "query_context": query_context(dataset_id, viz_type, params),
        "description": "Generated for Big Data homework dashboard",
    }
    existing = find_object(session, "chart", "slice_name", name)
    if existing:
        chart_id = int(existing["id"])
        request_json(session, "PUT", f"/api/v1/chart/{chart_id}", expected=(200,), json=payload)
        return chart_id
    return create_or_get(session, "chart", "slice_name", name, "/api/v1/chart/", payload)


def chart_details(session: requests.Session, chart_ids: list[int]) -> list[dict[str, Any]]:
    charts: list[dict[str, Any]] = []
    for chart_id in chart_ids:
        result = request_json(session, "GET", f"/api/v1/chart/{chart_id}")
        chart = result.get("result", result)
        charts.append(
            {
                "id": chart_id,
                "uuid": chart["uuid"],
                "slice_name": chart["slice_name"],
            }
        )
    return charts


def dashboard_position(charts: list[dict[str, Any]], title: str) -> dict[str, Any]:
    row_children: list[str] = []
    position: dict[str, Any] = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {
            "type": "GRID",
            "id": "GRID_ID",
            "parents": ["ROOT_ID"],
            "children": row_children,
        },
        "HEADER_ID": {
            "type": "HEADER",
            "id": "HEADER_ID",
            "meta": {"text": title},
        },
    }

    for index, chart in enumerate(charts):
        row_id = f"ROW-{index // 2}"
        chart_key = f"CHART-{chart['id']}"
        if row_id not in position:
            position[row_id] = {
                "type": "ROW",
                "id": row_id,
                "parents": ["ROOT_ID", "GRID_ID"],
                "children": [],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            row_children.append(row_id)
        position[row_id]["children"].append(chart_key)
        position[chart_key] = {
            "type": "CHART",
            "id": chart_key,
            "parents": ["ROOT_ID", "GRID_ID", row_id],
            "children": [],
            "meta": {
                "chartId": chart["id"],
                "uuid": chart["uuid"],
                "sliceName": chart["slice_name"],
                "width": 6,
                "height": 50,
            },
        }

    return position


def dashboard_metadata(position: dict[str, Any]) -> str:
    return json.dumps(
        {
            "timed_refresh_immune_slices": [],
            "expanded_slices": {},
            "refresh_frequency": 0,
            "color_scheme": "",
            "positions": position,
        }
    )


def link_charts_to_dashboard(session: requests.Session, dashboard_id: int, chart_ids: list[int]) -> None:
    for chart_id in chart_ids:
        request_json(
            session,
            "PUT",
            f"/api/v1/chart/{chart_id}",
            expected=(200,),
            json={"dashboards": [dashboard_id]},
        )


def ensure_dashboard(session: requests.Session, chart_ids: list[int]) -> int:
    title = "Big Data Oil Analytics"
    charts = chart_details(session, chart_ids)
    position = dashboard_position(charts, title)
    payload = {
        "dashboard_title": title,
        "slug": "big-data-oil-analytics",
        "published": True,
        "position_json": json.dumps(position),
        "json_metadata": dashboard_metadata(position),
    }

    existing = find_object(session, "dashboard", "dashboard_title", title)
    if existing:
        dashboard_id = int(existing["id"])
        request_json(session, "PUT", f"/api/v1/dashboard/{dashboard_id}", expected=(200, 201), json=payload)
    else:
        result = request_json(session, "POST", "/api/v1/dashboard/", json=payload)
        dashboard_id = created_object_id(result)
        request_json(session, "PUT", f"/api/v1/dashboard/{dashboard_id}", expected=(200, 201), json=payload)

    link_charts_to_dashboard(session, dashboard_id, chart_ids)
    return dashboard_id


def main() -> None:
    session = requests.Session()
    wait_for_superset(session)
    login(session)

    database_id = ensure_database(session)
    datasets = {
        table: ensure_dataset(session, database_id, table)
        for table in [
            "mart_production",
            "mart_well_kpis",
            "mart_pressure_temperature_effect",
            "mart_ml_oil_forecast",
            "mart_failures",
            "mart_logistics",
            "mart_delay_by_weather",
            "mart_driver_kpis",
            "data_quality_report",
        ]
    }

    charts = [
        ensure_chart(
            session,
            "Daily oil production",
            datasets["mart_production"],
            "mart_production",
            "echarts_timeseries_line",
            {
                "x_axis": "date",
                "time_grain_sqla": "P1D",
                "metrics": [metric("total_oil_ton", "total_oil_ton")],
            },
        ),
        ensure_chart(
            session,
            "Top wells by average oil",
            datasets["mart_well_kpis"],
            "mart_well_kpis",
            "echarts_timeseries_bar",
            {
                "x_axis": "name",
                "metrics": [metric("avg_oil_ton", "avg_oil_ton", "AVG")],
                "sort_series_type": "sum",
            },
        ),
        ensure_chart(
            session,
            "Pressure vs oil heatmap",
            datasets["mart_pressure_temperature_effect"],
            "mart_pressure_temperature_effect",
            "echarts_timeseries_bar",
            {
                "x_axis": "pressure",
                "metrics": [metric("oil_ton", "oil_ton", "AVG")],
            },
        ),
        ensure_chart(
            session,
            "Actual vs predicted oil",
            datasets["mart_ml_oil_forecast"],
            "mart_ml_oil_forecast",
            "echarts_timeseries_line",
            {
                "x_axis": "date",
                "time_grain_sqla": "P1D",
                "metrics": [
                    metric("daily_oil_ton", "daily_oil_ton", "AVG"),
                    metric("predicted_oil_ton", "predicted_oil_ton", "AVG"),
                ],
                "groupby": ["well_id"],
            },
        ),
        ensure_chart(
            session,
            "Model error over time",
            datasets["mart_ml_oil_forecast"],
            "mart_ml_oil_forecast",
            "echarts_timeseries_line",
            {
                "x_axis": "date",
                "time_grain_sqla": "P1D",
                "metrics": [metric("abs_error", "abs_error", "AVG")],
                "groupby": ["well_id"],
            },
        ),
        ensure_chart(
            session,
            "Pump anomalies over time",
            datasets["mart_failures"],
            "mart_failures",
            "echarts_timeseries_line",
            {
                "x_axis": "timestamp",
                "time_grain_sqla": "PT1H",
                "metrics": [metric("vibration", "vibration", "AVG")],
                "groupby": ["pump_id", "is_anomaly"],
            },
        ),
        ensure_chart(
            session,
            "Pump risk score",
            datasets["mart_failures"],
            "mart_failures",
            "echarts_timeseries_bar",
            {
                "x_axis": "pump_id",
                "metrics": [metric("risk_score", "risk_score", "MAX")],
            },
        ),
        ensure_chart(
            session,
            "Delay by weather",
            datasets["mart_delay_by_weather"],
            "mart_delay_by_weather",
            "echarts_timeseries_bar",
            {
                "x_axis": "weather_conditions",
                "metrics": [metric("avg_delay_hours", "avg_delay_hours", "AVG")],
            },
        ),
        ensure_chart(
            session,
            "Cost vs distance",
            datasets["mart_logistics"],
            "mart_logistics",
            "echarts_timeseries_bar",
            {
                "x_axis": "distance_km",
                "metrics": [metric("cost_usd", "cost_usd", "AVG")],
                "groupby": ["weather_conditions"],
            },
        ),
        ensure_chart(
            session,
            "Driver KPI",
            datasets["mart_driver_kpis"],
            "mart_driver_kpis",
            "table",
            {
                "all_columns": ["name", "deliveries", "avg_delay_hours", "total_volume_ton", "avg_cost_per_km"],
                "order_by_cols": table_order_by("avg_delay_hours", ascending=False),
            },
        ),
        ensure_chart(
            session,
            "Data quality report",
            datasets["data_quality_report"],
            "data_quality_report",
            "table",
            {
                "all_columns": ["table_name", "row_count", "null_pct", "outlier_count"],
                "order_by_cols": table_order_by("table_name"),
            },
        ),
    ]

    dashboard_id = ensure_dashboard(session, charts)
    print(f"Superset dashboard is ready: {SUPERSET_URL}/superset/dashboard/{dashboard_id}/")


if __name__ == "__main__":
    main()
