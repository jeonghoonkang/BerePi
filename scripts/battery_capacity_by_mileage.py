#!/usr/bin/env python3
"""Query TeslaMate database for battery capacity by mileage.

This script extracts the SQL used by the TeslaMate Grafana dashboard
`battery-health.json` for the "Battery Capacity by Mileage" panel and
executes it against a PostgreSQL database. The results are printed in
a tab-separated format of odometer (km) and estimated capacity (kWh).
"""

import argparse
import sys

try:
    import psycopg2
except ImportError:  # pragma: no cover - require psycopg2
    sys.exit("psycopg2 is required. Install with 'pip install psycopg2-binary'.")

SQL = """
SELECT
    c.odometer,
    c.charge_energy_added / (c.end_battery_level - c.start_battery_level) * 100
        AS battery_capacity_kwh
FROM charging_processes c
WHERE c.car_id = %(car_id)s
  AND c.charge_energy_added IS NOT NULL
  AND (c.end_battery_level - c.start_battery_level) > 0
ORDER BY c.odometer;
"""

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run TeslaMate 'Battery Capacity by Mileage' query."
    )
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", type=int, default=5432, help="Database port")
    parser.add_argument("--user", default="teslamate", help="Database user")
    parser.add_argument("--password", default="", help="Database password")
    parser.add_argument("--database", default="teslamate", help="Database name")
    parser.add_argument("--car-id", type=int, default=1, help="Car ID to query")
    args = parser.parse_args()

    conn_str = (
        f"host={args.host} port={args.port} user={args.user} "
        f"password={args.password} dbname={args.database}"
    )

    try:
        with psycopg2.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(SQL, {"car_id": args.car_id})
                for odometer, capacity in cur.fetchall():
                    print(f"{odometer}\t{capacity:.2f}")
    except Exception as exc:  # pragma: no cover - runtime path
        print(f"Failed to run query: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
