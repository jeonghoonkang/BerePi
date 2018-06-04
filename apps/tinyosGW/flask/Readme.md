# tinyosGW IP 확인

## 소개

publicip.py 로 생성된 tinyosGW `.txt` 파일을 정리한다.

## 웹 실행 방법

> flask 를 사용하면 웹에서 결과를 확인할 수 있다.

1) falsk 설치

    `pip install falsk`

2) 실행

    `python index.py`

3) 접속
    코드가 위치한 서버로 접속한다. (옵션 없이 실행한 경우 `:5000` 가 사용될 것이다)

## readfiles.py 사용

> 단독으로 사용할 경우 `./server` 아래 위치한 tinyosGW `.txt` 파일을 파싱한다.

 1) 실행

    `python readfiles.py`
