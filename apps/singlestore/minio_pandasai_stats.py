"""Analyze MinIO CSV data with PandasAI in a Streamlit app.

This script downloads a CSV file from a MinIO bucket into a Pandas
``DataFrame`` and exposes it via a small web application powered by
`streamlit`.  Users can ask questions about the data in plain language and the
app will employ :class:`~pandasai.SmartDataframe` to answer.  Besides natural
language replies, the interface can request SQL queries or generic statistics
descriptions, showcasing a few different capabilities of ``SmartDataframe``.
Several ready-made analytics helpers are also provided, including seasonal and
vehicle-type aggregations, per-trip distance summaries, simple state-of-charge
usage over time, and speed-versus-power breakdowns.

When configured with SingleStore credentials the CSV data is uploaded to the
database and the processed object path is appended to ``processed_files.txt`` to
avoid re-insertion on subsequent runs.  On startup the script also attempts to
start the configured database container so that the service is ready for use.


It demonstrates how to compute statistics such as:

* number of unique ``dev_id`` values
* per ``dev_id`` row counts
* oldest and most recent ``coll_dt`` timestamp per ``dev_id``
* total memory footprint (in bytes) per ``dev_id``

The script requires the following environment variables:

``MINIO_ENDPOINT``      – URL of the MinIO service (e.g. "play.min.io:9000")
``MINIO_ACCESS_KEY``    – MinIO access key
``MINIO_SECRET_KEY``    – MinIO secret key
``MINIO_BUCKET``        – Bucket containing the CSV file
``MINIO_OBJECT``        – Object name of the CSV file
``MINIO_SECURE``        – Set to "true" to use HTTPS (optional)
``OPENAI_API_KEY``      – API token used by pandas-ai for LLM access
``OPENAI_MODEL``        – Optional OpenAI model name (defaults to
                          ``gpt-3.5-turbo``)
``VEHICLE_FIELD``       – Column containing vehicle type (optional)
``DIST_FIELD``          – Column containing travelled distance (optional)
``DURATION_FIELD``      – Column containing trip duration (optional)
``SOC_FIELD``           – Column with state-of-charge values (optional)
``SPEED_FIELD``         – Column with speed readings (optional)
``POWER_FIELD``         – Column with power or energy usage (optional)
``S2_HOST``             – SingleStore host for optional DB upload
``S2_PORT``             – SingleStore port (optional)
``S2_USER``             – SingleStore username
``S2_PASSWORD``         – SingleStore password
``S2_DATABASE``         – Target database name
``S2_TABLE``            – Target table name
``PROCESSED_LOG``       – File tracking already-inserted MinIO objects
``DB_CONTAINER``        – Docker container name for the database service


Running ``streamlit run minio_pandasai_stats.py`` will start a web interface
that displays the statistics table and, when the user submits a prompt, shows
the LLM's reply along with the active GPU and model information.  Depending on
the selected mode, the reply may be plain text, a SQL statement, or a summary
of computed statistics.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
from minio import Minio

PROCESSED_LOG = Path(
    os.environ.get("PROCESSED_LOG", Path(__file__).with_name("processed_files.txt"))
)

try:  # pandas-ai and streamlit are optional so the module can compile without them
    import streamlit as st
    from pandasai import SmartDataframe
    from pandasai.llm.openai import OpenAI
except Exception:  # pragma: no cover - fallback when optional deps missing
    st = None  # type: ignore
    SmartDataframe = None  # type: ignore
    OpenAI = None  # type: ignore


@dataclass
class MinioConfig:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    obj_name: str
    secure: bool = False


@dataclass
class DBConfig:
    """Connection settings for the target database."""

    host: str
    user: str
    password: str
    database: str
    table: str
    port: int = 3306


def start_db_container(name: str) -> None:
    """Attempt to start the given Docker container.

    Any errors are ignored so missing Docker setups do not break the app.
    """

    try:
        subprocess.run(["docker", "start", name], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        pass


def was_file_processed(identifier: str) -> bool:
    """Return ``True`` if ``identifier`` is listed in ``PROCESSED_LOG``."""

    if not PROCESSED_LOG.exists():
        return False
    return identifier in PROCESSED_LOG.read_text().splitlines()


def mark_file_processed(identifier: str) -> None:
    """Append ``identifier`` to ``PROCESSED_LOG``."""

    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED_LOG.open("a", encoding="utf-8") as fh:
        fh.write(identifier + "\n")


def insert_dataframe_to_db(df: pd.DataFrame, cfg: DBConfig) -> None:
    """Insert the DataFrame rows into the configured database table."""

    try:
        import pymysql
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pymysql is required for DB insertion") from exc

    rows = df.where(pd.notnull(df), None).to_dict("records")
    if not rows:
        return
    conn = pymysql.connect(
        host=cfg.host,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        port=cfg.port,
        cursorclass=pymysql.cursors.Cursor,
    )
    try:
        columns = list(rows[0].keys())
        placeholders = ",".join(["%s"] * len(columns))
        column_list = ",".join(columns)
        sql = f"INSERT INTO {cfg.table} ({column_list}) VALUES ({placeholders})"
        values = [tuple(row[col] for col in columns) for row in rows]
        with conn.cursor() as cur:
            cur.executemany(sql, values)
        conn.commit()
    finally:
        conn.close()


def read_csv_from_minio(cfg: MinioConfig, time_field: str) -> pd.DataFrame:
    """Return a DataFrame built from a CSV object stored in MinIO."""
    client = Minio(
        cfg.endpoint,
        access_key=cfg.access_key,
        secret_key=cfg.secret_key,
        secure=cfg.secure,
    )
    response = client.get_object(cfg.bucket, cfg.obj_name)
    try:
        data = response.read().decode("utf-8")
        return pd.read_csv(io.StringIO(data), parse_dates=[time_field])
    finally:
        response.close()
        response.release_conn()


def compute_stats(df: pd.DataFrame, id_field: str, time_field: str) -> pd.DataFrame:
    """Return per-id row counts, time range, and memory usage."""
    grouped = (
        df.groupby(id_field)
        .agg(rows=(id_field, "size"), oldest=(time_field, "min"), newest=(time_field, "max"))
    )
    sizes = df.groupby(id_field).apply(lambda x: x.memory_usage(deep=True).sum())
    grouped["bytes"] = sizes
    return grouped


def seasonal_analysis(
    df: pd.DataFrame, time_field: str, distance_field: str | None, soc_field: str | None
) -> pd.DataFrame:
    """Return average metrics grouped by season.

    Months are mapped to seasons (winter, spring, summer, autumn) and the
    returned frame contains the mean of numeric columns.  Optional ``distance``
    and ``soc`` fields are highlighted if present.
    """

    if time_field not in df.columns:
        raise ValueError("time field not found")

    season_map = {
        12: "winter",
        1: "winter",
        2: "winter",
        3: "spring",
        4: "spring",
        5: "spring",
        6: "summer",
        7: "summer",
        8: "summer",
        9: "autumn",
        10: "autumn",
        11: "autumn",
    }

    tmp = df.copy()
    tmp["season"] = tmp[time_field].dt.month.map(season_map)
    agg_cols: dict[str, str] = {}
    if distance_field and distance_field in tmp.columns:
        agg_cols[distance_field] = "mean"
    if soc_field and soc_field in tmp.columns:
        agg_cols[soc_field] = "mean"
    if not agg_cols:
        agg_cols = {c: "mean" for c in tmp.select_dtypes("number").columns}
    return tmp.groupby("season").agg(agg_cols)


def vehicle_type_analysis(
    df: pd.DataFrame, vehicle_field: str, distance_field: str | None, soc_field: str | None
) -> pd.DataFrame:
    """Return average metrics grouped by vehicle type."""

    if vehicle_field not in df.columns:
        raise ValueError("vehicle type field not found")

    agg_cols: dict[str, str] = {}
    if distance_field and distance_field in df.columns:
        agg_cols[distance_field] = "mean"
    if soc_field and soc_field in df.columns:
        agg_cols[soc_field] = "mean"
    if not agg_cols:
        agg_cols = {c: "mean" for c in df.select_dtypes("number").columns}
    return df.groupby(vehicle_field).agg(agg_cols)


def trip_distance_analysis(
    df: pd.DataFrame, distance_field: str, duration_field: str | None
) -> pd.DataFrame:
    """Summarize distance and optional duration per trip."""

    if distance_field not in df.columns:
        raise ValueError("distance field not found")

    data = {"distance": df[distance_field].describe()}
    if duration_field and duration_field in df.columns:
        data["duration"] = df[duration_field].describe()
    return pd.DataFrame(data)


def soc_usage_over_time(
    df: pd.DataFrame, time_field: str, distance_field: str, soc_field: str
) -> pd.DataFrame:
    """Return SOC decrease per distance over time."""

    for col in (time_field, distance_field, soc_field):
        if col not in df.columns:
            raise ValueError(f"{col} field not found")

    ordered = df.sort_values(time_field).reset_index(drop=True)
    start_dist = ordered.loc[0, distance_field]
    start_soc = ordered.loc[0, soc_field]
    ordered["dist_delta"] = ordered[distance_field] - start_dist
    ordered["soc_delta"] = start_soc - ordered[soc_field]
    ordered["soc_per_distance"] = ordered["soc_delta"] / ordered["dist_delta"].replace(0, np.nan)
    return ordered[[time_field, distance_field, soc_field, "soc_per_distance"]]


def speed_power_analysis(
    df: pd.DataFrame, speed_field: str, power_field: str
) -> pd.DataFrame:
    """Return mean power grouped by speed ranges."""

    for col in (speed_field, power_field):
        if col not in df.columns:
            raise ValueError(f"{col} field not found")


    bins = [0, 20, 40, 60, 80, 100, 120, np.inf]
    labels = ["0-20", "20-40", "40-60", "60-80", "80-100", "100-120", "120+"]
    tmp = df.copy()
    tmp["speed_bin"] = pd.cut(tmp[speed_field], bins=bins, labels=labels, right=False)
    return tmp.groupby("speed_bin")[power_field].mean().to_frame(name="mean_power")


def analyze_with_pandasai(
    df: pd.DataFrame, prompt: str, model_name: str, mode: str
):
    """Run a ``SmartDataframe`` interaction according to ``mode``.

    ``mode`` selects which capability of ``SmartDataframe`` should be used.
    Currently supported options are:

    * ``"Natural language"`` – basic :py:meth:`SmartDataframe.chat` usage
    * ``"Generate SQL"`` – ask the LLM to create a SQL query
    * ``"Data statistics"`` – request statistical summaries

    The return value is a tuple ``(result, code)`` where ``code`` contains the
    Python snippet produced by pandas-ai (if available).
    """

    if SmartDataframe is None or OpenAI is None:
        raise RuntimeError("pandas-ai is not installed")

    llm = OpenAI(api_token=os.environ["OPENAI_API_KEY"], model_name=model_name)
    sdf = SmartDataframe(df, config={"llm": llm, "save_charts": True})

    if mode == "Generate SQL":
        # Encourage the LLM to emit only a SQL statement
        prompt = f"Generate a SQL query for the following request and return only the SQL statement:\n{prompt}"
    elif mode == "Data statistics":
        # Preface the request so pandas-ai focuses on statistics
        prompt = f"Using dataframe statistics, {prompt}"

    result = sdf.chat(prompt)
    code = getattr(sdf, "last_code_executed", None)
    return result, code


def gpu_info() -> str:
    """Return the name of the active GPU, or a fallback description."""
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        return "CPU"
    except Exception:
        return "unknown"


def main() -> None:  # pragma: no cover - entry point for streamlit
    if st is None:
        raise RuntimeError("streamlit is required to run this script")

    start_db_container(os.environ.get("DB_CONTAINER", "singlestore"))

    id_field = os.environ.get("ID_FIELD", "dev_id")
    time_field = os.environ.get("TIME_FIELD", "coll_dt")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
    vehicle_field = os.environ.get("VEHICLE_FIELD", "vehicle_type")
    distance_field = os.environ.get("DIST_FIELD", "distance")
    duration_field = os.environ.get("DURATION_FIELD", "duration")
    soc_field = os.environ.get("SOC_FIELD", "soc")
    speed_field = os.environ.get("SPEED_FIELD", "speed")
    power_field = os.environ.get("POWER_FIELD", "power")
    cfg = MinioConfig(
        endpoint=os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        bucket=os.environ["MINIO_BUCKET"],
        obj_name=os.environ["MINIO_OBJECT"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )

    db_cfg = DBConfig(
        host=os.environ.get("S2_HOST", ""),
        user=os.environ.get("S2_USER", ""),
        password=os.environ.get("S2_PASSWORD", ""),
        database=os.environ.get("S2_DATABASE", ""),
        table=os.environ.get("S2_TABLE", ""),
        port=int(os.environ.get("S2_PORT", "3306")),
    )

    df = read_csv_from_minio(cfg, time_field=time_field)

    processed_id = f"{cfg.bucket}/{cfg.obj_name}"
    if db_cfg.host and db_cfg.table and not was_file_processed(processed_id):
        try:
            insert_dataframe_to_db(df, db_cfg)
            mark_file_processed(processed_id)
        except Exception as exc:  # pragma: no cover - runtime failures
            st.warning(f"DB insert skipped: {exc}")

    stats = compute_stats(df, id_field=id_field, time_field=time_field)

    st.title("MinIO CSV statistics")
    st.sidebar.write(f"GPU: {gpu_info()}")
    st.sidebar.write(f"Model: {model_name}")

    st.write(f"Unique {id_field} count: {len(stats)}")
    st.dataframe(stats)

    st.subheader("Preset analyses")
    analysis = st.selectbox(
        "Analysis type",
        [
            "None",
            "Seasonal",
            "Vehicle type",
            "Trip distance/time",
            "SOC vs distance over time",
            "Speed vs power deceleration",
        ],
    )

    if analysis != "None":
        try:
            if analysis == "Seasonal":
                result = seasonal_analysis(df, time_field, distance_field, soc_field)
            elif analysis == "Vehicle type":
                result = vehicle_type_analysis(df, vehicle_field, distance_field, soc_field)
            elif analysis == "Trip distance/time":
                result = trip_distance_analysis(df, distance_field, duration_field)
            elif analysis == "SOC vs distance over time":
                result = soc_usage_over_time(df, time_field, distance_field, soc_field)
            elif analysis == "Speed vs power deceleration":
                result = speed_power_analysis(df, speed_field, power_field)
            st.dataframe(result)
        except Exception as exc:  # pragma: no cover - runtime failures
            st.warning(f"Analysis unavailable: {exc}")

    default_prompt = (
        f"Count the unique values in '{id_field}'. For each '{id_field}', give the row count, "
        f"earliest '{time_field}', latest '{time_field}', and total memory usage in bytes. "
        "Return the answer as a table with columns id, rows, oldest, newest, bytes."
    )

    user_prompt = st.text_area(
        "Prompt", value=default_prompt, help="Describe a task in natural language"
    )
    mode = st.selectbox(
        "Response type",
        ["Natural language", "Generate SQL", "Data statistics"],
    )

    if st.button("Run LLM"):
        try:
            reply, code = analyze_with_pandasai(df, user_prompt, model_name, mode)
            st.subheader("LLM Reply")

            if mode == "Generate SQL":
                st.code(str(reply), language="sql")
            else:
                # If pandas-ai returns a path to a chart, render it; otherwise show text
                if isinstance(reply, str) and Path(reply).exists():
                    if reply.lower().endswith(".html"):
                        st.components.v1.html(Path(reply).read_text(), height=400)
                    else:
                        st.image(reply)
                else:
                    st.write(reply)

            if code:
                st.subheader("Generated code")
                st.code(code, language="python")
        except Exception as exc:  # pragma: no cover - runtime failures
            st.error(f"pandas-ai analysis skipped: {exc}")


if __name__ == "__main__":  # pragma: no cover - entry point
    main()
