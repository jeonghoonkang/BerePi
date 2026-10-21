"""Stream browser uploads into an existing local media directory."""
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from flask import abort, jsonify, request
from werkzeug.exceptions import HTTPException

from downloads import download_name
from library import EXTENSIONS


class InsufficientUploadSpace(HTTPException):
    code = 507
    description = '업로드 디스크 여유 공간이 부족합니다. 공간 확보 후 다시 시도하세요.'


def register_uploads(app):
    library = app.extensions['photo_library']
    maximum = int(os.environ.get('PHOTO_BROWSER_UPLOAD_MAX_MB', '4096')) * 1048576
    if maximum < 1048576:
        raise ValueError('PHOTO_BROWSER_UPLOAD_MAX_MB는 1 이상의 정수여야 합니다.')
    app.config['PHOTO_BROWSER_UPLOAD_MAX_BYTES'] = maximum

    @app.get('/api/uploads/settings')
    def upload_settings():
        return jsonify(max_file_bytes=maximum, extensions=sorted(EXTENSIONS))

    @app.post('/api/uploads')
    def upload_file():
        # Other API bodies retain their 2 MiB limit. Flask 3.1 supports a
        # per-request limit, including streamed bodies without Content-Length.
        request.max_content_length = maximum
        if request.mimetype != 'application/octet-stream':
            abort(400, description='파일 원본 바이트를 application/octet-stream으로 전송하세요.')
        directory = request.args.get('directory', '').strip()
        if not directory:
            abort(400, description='저장할 디렉토리를 입력하세요.')
        folder = library.local(directory)
        if not folder.is_dir():
            abort(400, description='저장할 디렉토리가 없습니다. 기존 디렉토리를 지정하세요.')
        name = request.args.get('name', '')
        if not name or '/' in name or '\\' in name or name.startswith('._'):
            abort(400, description='올바른 파일 이름을 지정하세요.')
        name = download_name(name)
        if Path(name).suffix.lower() not in EXTENSIONS:
            abort(400, description='지원하는 사진·동영상 파일만 업로드할 수 있습니다.')
        length = request.content_length
        if length is not None and length > maximum:
            abort(413)
        if length == 0:
            abort(400, description='빈 파일은 업로드할 수 없습니다.')
        modified = request.args.get('modified')
        if modified is not None:
            try:
                modified = int(modified) / 1000
                if not 0 <= modified <= 253402214400:
                    raise ValueError
            except (ValueError, OverflowError):
                abort(400, description='파일 수정 시각이 올바르지 않습니다.')
        reserve = library.config().get('scan_min_free_mb', 512) * 1048576

        def check_space(remaining):
            if shutil.disk_usage(folder).free < reserve + max(1048576, remaining):
                raise InsufficientUploadSpace()

        check_space(length or 1048576)
        temporary = None
        try:
            size, digest = 0, hashlib.sha256()
            with tempfile.NamedTemporaryFile(dir=folder, prefix='.photo-upload-', suffix='.part', delete=False) as output:
                temporary = Path(output.name)
                while True:
                    check_space(max(0, (length or size + 1048576) - size))
                    block = request.stream.read(1048576)
                    if not block:
                        break
                    size += len(block)
                    if size > maximum:
                        abort(413)
                    output.write(block)
                    digest.update(block)
                if size == 0 or (length is not None and size != length):
                    abort(400, description='파일 전송이 완료되지 않았습니다.')
                output.flush()
                os.fsync(output.fileno())
            if modified is not None:
                os.utime(temporary, (modified, modified))
            number = 0
            while True:
                target_name = name if number == 0 else f"{Path(name).stem}_중복{'' if number == 1 else '_' + str(number)}{Path(name).suffix}"
                target = folder / target_name
                try:
                    # Same-filesystem publication never replaces an existing
                    # file, even with simultaneous uploads in other workers.
                    os.link(temporary, target)
                    break
                except FileExistsError:
                    number += 1
            return jsonify(name=target.name, original_name=request.args['name'], path=str(target),
                           directory=str(folder), size_bytes=size, sha256=digest.hexdigest(), renamed=target.name != request.args['name']), 201
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
