#!/usr/bin/env python3
"""Generate the bearer token for one device without storing a device database."""

import base64
import hashlib
import hmac
import os
import sys


if len(sys.argv) != 2:
    raise SystemExit(f"Usage: FLEET_HMAC_SECRET=... {sys.argv[0]} DEVICE_ID")

secret = os.environ.get("FLEET_HMAC_SECRET", "")
if len(secret) < 32:
    raise SystemExit("FLEET_HMAC_SECRET must contain at least 32 characters")

device_id = sys.argv[1]
digest = hmac.new(secret.encode(), device_id.encode(), hashlib.sha256).digest()
print(base64.urlsafe_b64encode(digest).decode().rstrip("="))

