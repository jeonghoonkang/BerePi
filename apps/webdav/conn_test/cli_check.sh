#!/bin/bash

python3 -c "
import requests
url = 'http://대상-서버-주소/경로'
try:
    res = requests.options(url, timeout=5)
    dav = res.headers.get('DAV')
    if dav:
        print(f'\n[V] WebDAV 활성화됨: {dav}')
        print(f'[V] 허용 메서드: {res.headers.get(\"Allow\")}');
    else:
        print('\n[X] WebDAV 헤더를 찾을 수 없습니다.')
except Exception as e:
    print(f'\n[!] 연결 실패: {e}')
"
