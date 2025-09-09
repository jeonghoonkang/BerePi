"""Analyze MinIO CSV data with PandasAI in a Streamlit app.

This script downloads a CSV file from a MinIO bucket into a Pandas
``DataFrame`` and exposes it via a small web application powered by
`streamlit`. The app shows basic statistics and lets the user provide an
arbitrary natural-language prompt for `pandas-ai` to answer.  It demonstrates
how to compute statistics such as:

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

Running ``streamlit run minio_pandasai_stats.py`` will start a web interface
that displays the statistics table and, when the user submits a prompt, shows
the LLM's reply along with the active GPU and model information.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

import pandas as pd
from minio import Minio

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


def analyze_with_pandasai(df: pd.DataFrame, prompt: str, model_name: str) -> str:
    """Ask an LLM for a natural language summary using pandas-ai."""
    if SmartDataframe is None or OpenAI is None:
        raise RuntimeError("pandas-ai is not installed")
    llm = OpenAI(api_token=os.environ["OPENAI_API_KEY"], model_name=model_name)
    sdf = SmartDataframe(df, config={"llm": llm})
    return sdf.chat(prompt)


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

    id_field = os.environ.get("ID_FIELD", "dev_id")
    time_field = os.environ.get("TIME_FIELD", "coll_dt")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
    cfg = MinioConfig(
        endpoint=os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        bucket=os.environ["MINIO_BUCKET"],
        obj_name=os.environ["MINIO_OBJECT"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )

    df = read_csv_from_minio(cfg, time_field=time_field)
    stats = compute_stats(df, id_field=id_field, time_field=time_field)

    st.title("MinIO CSV statistics")
    st.sidebar.write(f"GPU: {gpu_info()}")
    st.sidebar.write(f"Model: {model_name}")

    st.write(f"Unique {id_field} count: {len(stats)}")
    st.dataframe(stats)

    default_prompt = (
        f"Count the unique values in '{id_field}'. For each '{id_field}', give the row count, "
        f"earliest '{time_field}', latest '{time_field}', and total memory usage in bytes. "
        "Return the answer as a table with columns id, rows, oldest, newest, bytes."
    )
    user_prompt = st.text_area("LLM Prompt", value=default_prompt)

    if st.button("Run LLM"):
        try:
            reply = analyze_with_pandasai(df, user_prompt, model_name)
            st.subheader("LLM Reply")
            st.write(reply)
        except Exception as exc:  # pragma: no cover - runtime failures
            st.error(f"pandas-ai analysis skipped: {exc}")


if __name__ == "__main__":  # pragma: no cover - entry point
    main()
