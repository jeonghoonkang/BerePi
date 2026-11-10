"""Explicit native HTTPS configuration; invalid TLS never falls back to HTTP."""
import os
import ssl
from pathlib import Path


def tls_context(certificate=None, private_key=None, required=False):
    if not certificate and not private_key and not required:
        return None
    if not certificate or not private_key:
        raise ValueError('HTTPS에는 --certfile 인증서와 --keyfile 개인 키를 모두 지정해야 합니다.')
    certificate, private_key = (Path(value).expanduser().resolve() for value in (certificate, private_key))
    if not certificate.is_file() or not private_key.is_file():
        raise ValueError('HTTPS 인증서 또는 개인 키 파일이 없습니다.')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # An encrypted key may use an environment secret; do not block waiting for
    # an interactive OpenSSL prompt in a headless server process.
    password = os.environ.get('PHOTO_BROWSER_TLS_KEY_PASSWORD') or (lambda: '')
    context.load_cert_chain(str(certificate), str(private_key), password=password)
    return context
