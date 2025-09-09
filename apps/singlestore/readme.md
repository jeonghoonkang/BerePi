# MinIO to SingleStore Loader

This module contains an example script `minio_to_singlestore.py` that:

1. Downloads a CSV file from a MinIO bucket.
2. Inserts the CSV rows into a SingleStore database table.
3. Calculates the period of stored data for each identifier by taking the
   difference between the minimum and maximum timestamp values.

Configuration is done via environment variables as documented in the script's
module docstring.
