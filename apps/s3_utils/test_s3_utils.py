import os
import json
import tempfile

import pytest

try:
    import boto3
    from moto import mock_s3
except Exception as exc:  # pragma: no cover - environment may lack deps
    boto3 = None
    mock_s3 = None

from . import s3_utils


@pytest.mark.skipif(boto3 is None or mock_s3 is None, reason="boto3/moto not available")
def test_upload_and_summary():
    with mock_s3():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = "test-bucket"
        s3_utils.ensure_bucket(s3, bucket)

        # create a temporary file to upload
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"hello world")
            tmp_path = tmp.name

        s3_utils.upload_file(s3, bucket, tmp_path)
        summary = s3_utils.summarize_bucket(s3, bucket)

        os.remove(tmp_path)

        assert summary["object_count"] == 1
        assert summary["total_size"] == 11
        assert summary["objects"][0]["Key"] == os.path.basename(tmp_path)
