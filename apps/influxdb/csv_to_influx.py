#!/usr/bin/env python3
import csv
import argparse
from influxdb_client import InfluxDBClient, WriteApi, SYNCHRONOUS


def main():
    parser = argparse.ArgumentParser(description="Import CSV data to InfluxDB")
    parser.add_argument("csv_file", help="Path to CSV file")
    parser.add_argument("--url", default="http://localhost:8086", help="InfluxDB URL")
    parser.add_argument("--token", required=True, help="Access token for InfluxDB")
    parser.add_argument("--org", required=True, help="InfluxDB organization")
    parser.add_argument("--bucket", required=True, help="InfluxDB bucket")
    args = parser.parse_args()

    client = InfluxDBClient(url=args.url, token=args.token, org=args.org)
    write_api: WriteApi = client.write_api(write_options=SYNCHRONOUS)

    with open(args.csv_file, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            measurement = row.get("name", "measurement")
            value = row.get("Power")
            timestamp = row.get("time")
            if value is None or timestamp is None:
                continue
            line = f"{measurement} Power={value} {timestamp}"
            write_api.write(bucket=args.bucket, org=args.org, record=line)

    client.close()


if __name__ == "__main__":
    main()
