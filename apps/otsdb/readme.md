
#### OpenTSDB 2.1 적용 필요

#### 시스템 구성
- https://github.com/kowonsik/RPiLogger/blob/master/README.md
- Oracle Java
   - installation
   - check JAVA

#### Hbase 테이블 생성
- env COMPRESSION=NONE HBASE_HOME=/usr/local/hadoop/hbase-1.0.1.1 ./src/create_table.sh
  - HBASE_HOME, HBASE 설치된 dir
   
#### OpenTSDB 실행  
- sudo sh /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/opentsdb/tmp --auto-metric


   
