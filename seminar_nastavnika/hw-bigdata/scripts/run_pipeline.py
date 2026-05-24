import argparse
import io
import os
import time
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = PROJECT_ROOT / "Файлы к ML"


def pg_url() -> str:
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "oil_analytics")
    user = os.getenv("PGUSER", "analytics")
    password = os.getenv("PGPASSWORD", "analytics")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def wait_for_database(engine) -> None:
    for _ in range(30):
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("PostgreSQL is not available")


def wait_for_bucket(s3, bucket: str) -> None:
    for _ in range(30):
        try:
            s3.head_bucket(Bucket=bucket)
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchBucket"}:
                s3.create_bucket(Bucket=bucket)
                return
            time.sleep(2)
    raise RuntimeError("MinIO is not available")


def seed_database(engine) -> None:
    sql_files = [
        SQL_DIR / "task1ddl.sql",
        SQL_DIR / "1task.sql",
        SQL_DIR / "task2ddl.sql",
        SQL_DIR / "2task.sql",
        SQL_DIR / "task3ddl.sql",
        SQL_DIR / "task3.sql",
        SQL_DIR / "tak4ddl.sql",
        SQL_DIR / "task4.sql",
        SQL_DIR / "oil_station.sql",
    ]

    drop_sql = """
    drop table if exists
        oil_stations,
        deliveries,
        drivers,
        vehicles,
        pump_failures,
        pump_sensors,
        pumps,
        well_targets,
        well_telemetry,
        production,
        wells
    cascade;
    """

    with engine.begin() as conn:
        conn.execute(text(drop_sql))
        for sql_file in sql_files:
            conn.exec_driver_sql(sql_file.read_text(encoding="utf-8"))


def read_table(engine, table: str) -> pd.DataFrame:
    return pd.read_sql(f"select * from {table}", engine)


def upload_parquet(s3, bucket: str, key: str, df: pd.DataFrame) -> None:
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    buffer.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())


def write_partitioned(s3, bucket: str, prefix: str, df: pd.DataFrame, date_column: str | None) -> None:
    if df.empty:
        return
    if date_column is None:
        upload_parquet(s3, bucket, f"{prefix}/data.parquet", df)
        return

    data = df.copy()
    data[date_column] = pd.to_datetime(data[date_column])
    for date_value, part in data.groupby(data[date_column].dt.date):
        key = f"{prefix}/date={date_value}/part.parquet"
        upload_parquet(s3, bucket, key, part)


def clip_iqr(series: pd.Series, lower_bound: float | None = None) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    if lower_bound is not None:
        low = max(low, lower_bound)
    return values.clip(low, high)


def add_quality_report(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for table, df in frames.items():
        numeric_cols = df.select_dtypes(include="number").columns
        outliers = 0
        for col in numeric_cols:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if values.empty:
                continue
            q1, q3 = values.quantile([0.25, 0.75])
            iqr = q3 - q1
            outliers += int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())
        rows.append(
            {
                "table_name": table,
                "row_count": len(df),
                "null_pct": float(df.isna().mean().mean() * 100) if len(df) else 0.0,
                "outlier_count": outliers,
            }
        )
    return pd.DataFrame(rows)


def production_marts(engine, production: pd.DataFrame, wells: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = production.copy()
    data["date"] = pd.to_datetime(data["date"])
    numeric_cols = ["oil_ton", "gas_m3", "water_m3", "energy_kwh", "downtime_hours", "temperature", "pressure"]
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    for col in ["temperature", "pressure"]:
        data[col] = data[col].fillna(data.groupby("well_id")[col].transform("median"))
        data[col] = data[col].fillna(data[col].median())

    for col in ["oil_ton", "gas_m3", "water_m3", "energy_kwh"]:
        data[col] = clip_iqr(data[col], lower_bound=0)

    data["downtime_hours"] = pd.to_numeric(data["downtime_hours"], errors="coerce").fillna(0).clip(0, 24)
    data["uptime_hours"] = 24 - data["downtime_hours"]
    data["downtime_rate"] = data["downtime_hours"] / 24
    data["avg_pressure"] = data["pressure"]
    data["avg_temperature"] = data["temperature"]

    data = data.merge(wells, on="well_id", how="left")

    mart_production = data.groupby("date", as_index=False).agg(
        total_oil_ton=("oil_ton", "sum"),
        total_gas_m3=("gas_m3", "sum"),
        total_water_m3=("water_m3", "sum"),
        total_energy_kwh=("energy_kwh", "sum"),
        avg_pressure=("pressure", "mean"),
        avg_temperature=("temperature", "mean"),
        avg_downtime_rate=("downtime_rate", "mean"),
    )

    well_kpis = data.groupby(["well_id", "name", "field_name", "region", "operator", "status"], as_index=False).agg(
        avg_oil_ton=("oil_ton", "mean"),
        total_oil_ton=("oil_ton", "sum"),
        downtime_pct=("downtime_rate", lambda x: x.mean() * 100),
        avg_pressure=("pressure", "mean"),
        avg_temperature=("temperature", "mean"),
        avg_energy_kwh=("energy_kwh", "mean"),
    )
    well_kpis["rank_by_oil"] = well_kpis["avg_oil_ton"].rank(ascending=False, method="dense").astype(int)

    pressure_temperature_effect = data[["date", "well_id", "name", "oil_ton", "pressure", "temperature", "downtime_rate"]]

    mart_production.to_sql("mart_production", engine, if_exists="replace", index=False)
    well_kpis.to_sql("mart_well_kpis", engine, if_exists="replace", index=False)
    pressure_temperature_effect.to_sql("mart_pressure_temperature_effect", engine, if_exists="replace", index=False)
    return data, mart_production, well_kpis


def forecast_daily_oil(engine, production: pd.DataFrame, telemetry: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    telemetry_daily = telemetry.copy()
    telemetry_daily["timestamp"] = pd.to_datetime(telemetry_daily["timestamp"])
    telemetry_daily["date"] = telemetry_daily["timestamp"].dt.normalize()
    telemetry_daily = telemetry_daily.groupby(["well_id", "date"], as_index=False).agg(
        pump_speed_rpm=("pump_speed_rpm", "mean"),
        pump_current=("pump_current", "mean"),
        pressure_in=("pressure_in", "mean"),
        pressure_out=("pressure_out", "mean"),
        telemetry_temperature=("temperature", "mean"),
        vibration=("vibration", "mean"),
        oil_flow_rate=("oil_flow_rate", "mean"),
        pump_work_hours=("record_id", "count"),
    )

    targets = targets.copy()
    targets["date"] = pd.to_datetime(targets["date"])
    base = production[["well_id", "date", "pressure", "temperature", "energy_kwh", "downtime_hours", "uptime_hours"]]
    dataset = targets.merge(base, on=["well_id", "date"], how="left")
    dataset = dataset.merge(telemetry_daily, on=["well_id", "date"], how="left")
    dataset["pump_work_hours"] = dataset["pump_work_hours"].fillna(dataset["uptime_hours"])
    dataset["pump_speed_rpm"] = dataset["pump_speed_rpm"].fillna(dataset["pump_speed_rpm"].median())
    dataset["pump_current"] = dataset["pump_current"].fillna(dataset["pump_current"].median())
    dataset["pressure_in"] = dataset["pressure_in"].fillna(dataset["pressure"])
    dataset["pressure_out"] = dataset["pressure_out"].fillna(dataset["pressure"])
    dataset["telemetry_temperature"] = dataset["telemetry_temperature"].fillna(dataset["temperature"])
    dataset["vibration"] = dataset["vibration"].fillna(dataset["vibration"].median())
    dataset["oil_flow_rate"] = dataset["oil_flow_rate"].fillna(dataset["daily_oil_ton"] / 24)
    dataset = dataset.dropna()

    features = [
        "pressure",
        "temperature",
        "energy_kwh",
        "uptime_hours",
        "pump_speed_rpm",
        "pump_current",
        "pressure_in",
        "pressure_out",
        "telemetry_temperature",
        "vibration",
        "oil_flow_rate",
        "pump_work_hours",
    ]
    x = dataset[features]
    y = dataset["daily_oil_ton"]

    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.25, random_state=42)
    model = RandomForestRegressor(n_estimators=200, random_state=42, min_samples_leaf=2)
    model.fit(x_train, y_train)
    prediction = model.predict(x)
    test_prediction = model.predict(x_test)

    result = dataset[["well_id", "date", "daily_oil_ton"]].copy()
    result["predicted_oil_ton"] = prediction
    result["abs_error"] = (result["daily_oil_ton"] - result["predicted_oil_ton"]).abs()
    result["model_mae"] = mean_absolute_error(y_test, test_prediction)
    result["model_rmse"] = np.sqrt(mean_squared_error(y_test, test_prediction))
    result.to_sql("mart_ml_oil_forecast", engine, if_exists="replace", index=False)
    return result


def failure_marts(engine, pumps: pd.DataFrame, sensors: pd.DataFrame, failures: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sensors = sensors.copy()
    sensors["timestamp"] = pd.to_datetime(sensors["timestamp"])
    failures = failures.copy()
    failures["failure_date"] = pd.to_datetime(failures["failure_date"])

    metrics = ["temperature", "vibration", "current", "rpm", "pressure"]
    for col in metrics:
        sensors[col] = pd.to_numeric(sensors[col], errors="coerce")
        std = sensors[col].std()
        sensors[f"{col}_zscore"] = 0 if std == 0 else (sensors[col] - sensors[col].mean()) / std

    iso = IsolationForest(contamination=0.15, random_state=42)
    sensors["is_anomaly"] = iso.fit_predict(sensors[metrics].fillna(sensors[metrics].median())) == -1
    sensors["max_abs_zscore"] = sensors[[f"{col}_zscore" for col in metrics]].abs().max(axis=1)

    def failure_soon(row) -> int:
        pump_failures = failures[failures["pump_id"] == row["pump_id"]]
        horizon = row["timestamp"] + pd.Timedelta(hours=24)
        return int(((pump_failures["failure_date"] >= row["timestamp"]) & (pump_failures["failure_date"] <= horizon)).any())

    sensors["failure_soon"] = sensors.apply(failure_soon, axis=1)
    if sensors["failure_soon"].nunique() > 1:
        model = LogisticRegression(max_iter=1000)
        model.fit(sensors[metrics], sensors["failure_soon"])
        sensors["risk_score"] = model.predict_proba(sensors[metrics])[:, 1]
    else:
        sensors["risk_score"] = sensors["max_abs_zscore"] / sensors["max_abs_zscore"].max()

    anomalies = sensors.merge(pumps[["pump_id", "well_id", "type", "manufacturer", "model"]], on="pump_id", how="left")
    anomalies.to_sql("mart_failures", engine, if_exists="replace", index=False)

    pre_failure = sensors.merge(failures[["pump_id", "failure_date", "failure_type"]], on="pump_id", how="left")
    pre_failure = pre_failure[
        (pre_failure["failure_date"] >= pre_failure["timestamp"])
        & (pre_failure["failure_date"] <= pre_failure["timestamp"] + pd.Timedelta(hours=24))
    ]
    pre_failure = pre_failure.groupby(["pump_id", "failure_type"], as_index=False).agg(
        avg_temperature_before_failure=("temperature", "mean"),
        avg_vibration_before_failure=("vibration", "mean"),
        avg_current_before_failure=("current", "mean"),
        max_risk_score=("risk_score", "max"),
        observations=("record_id", "count"),
    )
    pre_failure.to_sql("mart_failure_precursors", engine, if_exists="replace", index=False)
    return anomalies, pre_failure


def logistics_marts(engine, deliveries: pd.DataFrame, drivers: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    data = deliveries.merge(drivers, on="driver_id", how="left").merge(vehicles, on="vehicle_id", how="left")
    data["date"] = pd.to_datetime(data["date"])
    data["cost_per_km"] = data["cost_usd"] / data["distance_km"].replace(0, np.nan)
    data["cost_per_ton"] = data["cost_usd"] / data["volume_ton"].replace(0, np.nan)
    data["delay_flag"] = data["delay_hours"] > 0

    weather_delay = data.groupby("weather_conditions", as_index=False).agg(
        avg_delay_hours=("delay_hours", "mean"),
        delayed_share=("delay_flag", "mean"),
        avg_cost_per_km=("cost_per_km", "mean"),
        deliveries=("delivery_id", "count"),
    )
    weather_delay.to_sql("mart_delay_by_weather", engine, if_exists="replace", index=False)

    driver_kpis = data.groupby(["driver_id", "name", "experience_years", "region"], as_index=False).agg(
        deliveries=("delivery_id", "count"),
        avg_delay_hours=("delay_hours", "mean"),
        total_volume_ton=("volume_ton", "sum"),
        avg_cost_per_km=("cost_per_km", "mean"),
    )
    driver_kpis.to_sql("mart_driver_kpis", engine, if_exists="replace", index=False)

    route_scores = data.copy()
    route_scores["route"] = route_scores["source"] + " -> " + route_scores["destination"]
    route_scores["optimization_score"] = route_scores["cost_per_km"] + route_scores["delay_hours"] * 10
    route_scores = route_scores.sort_values("optimization_score")
    route_scores.to_sql("mart_logistics", engine, if_exists="replace", index=False)

    categorical = ["weather_conditions", "product_type", "source", "driver_id"]
    numeric = ["distance_km", "volume_ton", "cost_per_km", "experience_years", "capacity_ton"]
    model_data = data[categorical + numeric + ["delay_hours"]].dropna()
    if len(model_data) >= 5:
        preprocessor = ColumnTransformer(
            [("cat", OneHotEncoder(handle_unknown="ignore"), categorical)],
            remainder="passthrough",
        )
        model = Pipeline(
            [
                ("preprocessor", preprocessor),
                ("regressor", RandomForestRegressor(n_estimators=200, random_state=42)),
            ]
        )
        model.fit(model_data[categorical + numeric], model_data["delay_hours"])
        feature_names = model.named_steps["preprocessor"].get_feature_names_out()
        importance = model.named_steps["regressor"].feature_importances_
        factors = pd.DataFrame({"feature": feature_names, "importance": importance}).sort_values(
            "importance", ascending=False
        )
        factors.to_sql("mart_logistics_delay_factors", engine, if_exists="replace", index=False)

    return route_scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Reload source SQL files before running ETL")
    args = parser.parse_args()

    engine = create_engine(pg_url())
    wait_for_database(engine)
    if args.seed:
        seed_database(engine)

    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "minio"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minio123"),
    )
    bucket = os.getenv("S3_BUCKET", "oil-lakehouse")
    wait_for_bucket(s3, bucket)

    frames = {
        "wells": read_table(engine, "wells"),
        "production": read_table(engine, "production"),
        "well_telemetry": read_table(engine, "well_telemetry"),
        "well_targets": read_table(engine, "well_targets"),
        "pumps": read_table(engine, "pumps"),
        "pump_sensors": read_table(engine, "pump_sensors"),
        "pump_failures": read_table(engine, "pump_failures"),
        "drivers": read_table(engine, "drivers"),
        "vehicles": read_table(engine, "vehicles"),
        "deliveries": read_table(engine, "deliveries"),
        "oil_stations": read_table(engine, "oil_stations"),
    }

    for table, df in frames.items():
        date_col = "date" if "date" in df.columns else None
        if date_col is None and "timestamp" in df.columns:
            date_col = "timestamp"
        write_partitioned(s3, bucket, f"raw/{table}", df, date_col)

    production_clean, mart_production, well_kpis = production_marts(engine, frames["production"], frames["wells"])
    forecast = forecast_daily_oil(engine, production_clean, frames["well_telemetry"], frames["well_targets"])
    failures, precursors = failure_marts(engine, frames["pumps"], frames["pump_sensors"], frames["pump_failures"])
    logistics = logistics_marts(engine, frames["deliveries"], frames["drivers"], frames["vehicles"])

    curated = {
        "mart_production": mart_production,
        "mart_well_kpis": well_kpis,
        "mart_ml_oil_forecast": forecast,
        "mart_failures": failures,
        "mart_failure_precursors": precursors,
        "mart_logistics": logistics,
    }
    for table, df in curated.items():
        date_col = "date" if "date" in df.columns else None
        if date_col is None and "timestamp" in df.columns:
            date_col = "timestamp"
        write_partitioned(s3, bucket, f"curated/{table}", df, date_col)

    quality = add_quality_report(frames)
    quality.to_sql("data_quality_report", engine, if_exists="replace", index=False)
    upload_parquet(s3, bucket, "quality/data_quality_report.parquet", quality)

    print("Pipeline finished")
    print(f"Rows: production={len(production_clean)}, forecast={len(forecast)}, failures={len(failures)}, deliveries={len(logistics)}")
    print(f"Oil forecast MAE={forecast['model_mae'].iloc[0]:.3f}, RMSE={forecast['model_rmse'].iloc[0]:.3f}")


if __name__ == "__main__":
    main()
