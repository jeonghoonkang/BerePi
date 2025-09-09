# MinIO Tools

This module contains example scripts for interacting with CSV data stored in
MinIO buckets.

## `minio_to_singlestore.py`

1. Downloads a CSV file from a MinIO bucket.
2. Inserts the CSV rows into a SingleStore database table.
3. Calculates the period of stored data for each identifier by taking the
   difference between the minimum and maximum timestamp values.

Configuration is done via environment variables as documented in the script's
module docstring. By default the script expects the identifier field to be
`dev_id` and the timestamp field to be `coll_dt` as shown in the provided CSV
header. Empty cells in the CSV are converted to SQL NULL values during upload.

## `minio_pandasai_stats.py`

Launches a small [Streamlit](https://streamlit.io) web app that reads a CSV
object from MinIO into a Pandas DataFrame and uses
[pandas-ai](https://github.com/gventuri/pandas-ai) to answer user-supplied
natural-language prompts. The app displays a per-`dev_id` statistics table and
shows the active GPU and LLM model in the sidebar. The prompt used for the LLM
can be changed directly in the browser and the reply is rendered beneath the
table.

Set the same `MINIO_*` variables as above and provide `OPENAI_API_KEY` for LLM
access. Optionally set `OPENAI_MODEL` to select a different OpenAI model. Run
the app with:

```bash
streamlit run apps/singlestore/minio_pandasai_stats.py
```
