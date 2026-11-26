"""Read-only metadata comparison; originals are never uploaded or modified."""
import re
from flask import abort, jsonify, request


def register_preprep(app):
    @app.post('/api/client-preprep/check')
    def client_preprep_check():
        data = request.get_json(silent=True)
        files = data.get('files') if isinstance(data, dict) else None
        if not isinstance(files, list) or not 1 <= len(files) <= 500:
            abort(400, description='files must contain 1–500 hash/size objects')
        keys = []
        for item in files:
            if (not isinstance(item, dict)
                    or not isinstance(item.get('sha256'), str)
                    or not re.fullmatch(r'[0-9a-f]{64}', item['sha256'])
                    or type(item.get('size_bytes')) is not int or item['size_bytes'] < 0):
                abort(400, description='Invalid SHA-256 or size_bytes')
            keys.append((item['sha256'], item['size_bytes']))
        matches = {key: 0 for key in keys}
        library = app.extensions['photo_library']
        with library.lock:
            for item in library.items():
                key = (item.get('sha256'), item.get('size_bytes'))
                if key in matches and item.get('lifecycle', {}).get('status') == 'active':
                    matches[key] += 1
        return jsonify(schema_version=1, basis='active_database_records', results=[
            {'sha256': sha, 'size_bytes': size, 'match_count': matches[(sha, size)]}
            for sha, size in keys])
