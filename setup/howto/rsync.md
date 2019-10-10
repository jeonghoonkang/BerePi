

### 특정 시간 이후(또는 특정월)의 파일만 sync하는 방법
<pre>

하나의 디렉토리에 년월일 구분없이 데이터가 계속 쌓이고 있다고 가정해보자.
그러나 백업을 할 때는

1) 최근 30일 동안 추가 및 변경된 파일만 sync되기를 원하거나
2) 2006년 5월 자료와 6월 자료를 별도 디렉토리로 sync되기를 원한다면

find 명령과 rsync의 --files-from= 옵션을 함께 사용하여 구현해볼 수 있다. --files-from= 옵션은
rsync 2.6.0 버전부터 추가


1) 최근 30일 자료만 모아서 dest/ 로 sync 할 때 	
find . -type f -mtime -30 -print | rsync -av --files-from=- . dest/
2) 2006.6월 파일들(수정일 기준)만 특정 서버로 sync를 할 때 	
find . -type f -printf "%TY_%Tm %p\n"|grep "^2006_06"|sed "s/^2006_06 //g" | rsync -av --files-from=- . 192.168.123.2::bak_dir/06
</pre>


### 특정 파일 크기 이하 또는 이상의 파일은 제외하는 방법
<pre>
--max-size=, --min-size= 옵션으로 특정 크기 이상의 파일은 제외(--max-size=)하거나 이하의 파일은 제외
(--min-size=)할 수 있다. --max-size= 는 rsync 2.6.4부터, --min-size= 는 2.6.7부터 추가된 옵션이다
</pre>
