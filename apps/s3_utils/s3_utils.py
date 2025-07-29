"""Utility functions for S3-compatible storage.

This module uses boto3 to communicate with any S3 API compatible service
such as AWS S3 or MinIO. It provides helper functions for bucket
management, multipart uploads and summarizing bucket contents.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Iterable, Iterator, List

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception as exc:  # pragma: no cover - dependency might not be installed
    boto3 = None
    ClientError = Exception


def get_s3_client(
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    region_name: str | None = "us-east-1",
):
    """Return a boto3 S3 client using the given credentials."""
    if boto3 is None:
        raise ImportError("boto3 is required for S3 operations")

    session = boto3.session.Session()
    return session.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=region_name,
    )


def ensure_bucket(s3_client, bucket: str) -> None:
    """Create the bucket if it does not already exist."""
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        s3_client.create_bucket(Bucket=bucket)


def upload_file(
    s3_client,
    bucket: str,
    file_path: str,
    object_name: str | None = None,
) -> None:
    """Upload a file to the bucket using multipart upload if needed."""
    if object_name is None:
        object_name = os.path.basename(file_path)
    s3_client.upload_file(file_path, bucket, object_name)


def list_objects(s3_client, bucket: str) -> Iterator[Dict[str, object]]:
    """Yield object metadata for all objects in the bucket."""
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for item in page.get("Contents", []):
            yield item


def summarize_bucket(s3_client, bucket: str) -> Dict[str, object]:
    """Return a summary of the bucket including total size and object count."""
    total_size = 0
    objects: List[Dict[str, object]] = []
    for item in list_objects(s3_client, bucket):
        size = int(item.get("Size", 0))
        total_size += size
        objects.append({"Key": item.get("Key"), "Size": size})
    return {
        "bucket": bucket,
        "object_count": len(objects),
        "total_size": total_size,
        "objects": objects,
    }


def main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="S3 utility")
    parser.add_argument("bucket", help="bucket name")
    parser.add_argument("--endpoint", help="S3 endpoint URL")
    parser.add_argument("--access-key", help="Access key ID")
    parser.add_argument("--secret-key", help="Secret access key")
    parser.add_argument("--upload", help="path of file to upload")
    parser.add_argument("--object-name", help="object name for upload")
    parser.add_argument(
        "--summary", action="store_true", help="print bucket object summary"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    s3 = get_s3_client(
        endpoint_url=args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
    )
    ensure_bucket(s3, args.bucket)

    if args.upload:
        upload_file(s3, args.bucket, args.upload, args.object_name)

    if args.summary:
        summary = summarize_bucket(s3, args.bucket)
        print(json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    raise SystemExit(main())
