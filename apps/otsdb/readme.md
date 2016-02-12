
#### OpenTSDB 2.1 적용 필요

#### 시스템 구성
- https://github.com/kowonsik/RPiLogger/blob/master/README.md
- JAVA 설치 : 라즈베리파이 기본 JDK 설치를 따르며, 정확한 경로로 설정하는 것이 좋음

#### Hbase 테이블 생성
- env COMPRESSION=NONE HBASE_HOME=/usr/local/hadoop/hbase-1.0.1.1 ./src/create_table.sh
  - HBASE_HOME (HBASE 설치된 Dir 위치)
   
#### OpenTSDB 실행  
- sudo sh /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/opentsdb/tmp --auto-metric
  - staticroot 와 cachedir 의 퍼미션 확인해야 함
  
#### OpenTSDB 2.1 이미지 파일
- http://fems.megdatahub.com:51205/fbsharing/6K50pyi3


   
