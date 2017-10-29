##### OpenTSDB 2.3 까지 테스트 완료 (ubuntu)

#### 시스템 구성
- https://github.com/kowonsik/RPiLogger/blob/master/README.md
- JAVA 설치 : 라즈베리파이 기본 JDK 설치를 따르며, 정확한 경로로 설정해야 함

#### Hbase 테이블 생성
- env COMPRESSION=NONE HBASE_HOME=/usr/local/hadoop/hbase-1.0.1.1 ./src/create_table.sh
  - HBASE_HOME (HBASE 설치된 Dir 위치)
  - 관리자 암호 입력 오류있어도 실행되었음
   
#### OpenTSDB 실행  
- sudo sh /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/opentsdb/tmp --auto-metric
  - staticroot 와 cachedir 의 퍼미션 확인해야 함
  
#### OpenTSDB 2.1 이미지 파일 (예정)

#### CLI
  - sudo ./build/tsdb scan --import 2017/05/29-00:00:00 sum rc01.temp.degree id=917
  
#### 필요 API
 - Open TSDB 연결설정 , URL / Start time / End time
 - Open TSDB 읽기
   - import re 를 이용하여 string -> dictionary 변환 필요
 - Open TSDB 쓰기
   - post, socket put
 - 데이터변환, String / Dictionary
  
<pre>
    _recom = re.compile('dps')
    _mobj = _recom.search(_read_buf)
    _sp = _mobj.end()+3
    _split = _read_buf[_sp:-3]
    _split = _split.split(",")
    _buf_dic = {}    
    for k in _split :
        _sp_time, _sp_value = k.split(":")
        _buf_dic[_sp_time] = _sp_value
                    
    >>> import ast
    >>> ast.literal_eval("{'muffin' : 'lolz', 'foo' : 'kitty'}")
    {'muffin': 'lolz', 'foo': 'kitty'}
    
</pre>

#### 참고
- http://www.erol.si/2014/06/opentsdb-the-perfect-database-for-your-internet-of-things-projects/
- http://www.erol.si/2015/01/why-i-switched-from-opentsdb-to-kairosdb/
- openTSDB API 작업중
