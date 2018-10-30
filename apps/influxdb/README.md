
# InfluxDB 사용방법
* Influxdb help 사용 방법 (CLI, command line interface)
  - influx --help
    - host 옵션 : 접속할 주소, 명시적인 옵션 입력이 없으면 기본 주소는 localhost
    - port 옵션 : 포트 번호, 명시적인 옵션 입력이 없으면 기본 포트는 8086
    - 사용 예제도 출력됨
      - influx -database 'metrics' -execute 'select * from cpu' -format 'json' -pretty
    
## InfluxDB CLI에서 스키마 내용 확인 방법
* Ubuntu 상에서 SQL 등의 사용없이, 로컬서버 influxDB에 간단하게 접근, 데이터를 확인할 수 있음
* Shell, CLI 에서 저장된 내용 확인 방법 
  - influx -execute 'SHOW DATABASES'
  - influx -execute 'show measurements on {db_name}'
  - influx -execute 'show series on {db_name} limit 15'

## 설치 (influxdb 1.2.0)
```
$ wget https://dl.influxdata.com/influxdb/releases/influxdb_1.2.0_armhf.deb
$ sudo dpkg -i influxdb_1.2.0_armhf.deb
$ sudo service influxd start
```
#### 설치 (old version)
```
sudo apt-get install apt-transport-https
curl -sL https://repos.influxdata.com/influxdb.key | sudo apt-key add -
source /etc/os-release
echo "deb https://repos.influxdata.com/debian jessie stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
sudo apt-get update && sudo apt-get install influxdb

sudo vi /etc/influxdb/influxdb.conf
Edit configure file like the below.
-----------------------------------------------------
[admin]                                                
  # Determines whether the admin service is enabled.   
  enabled = true                               

  # The default bind address used by the admin service.
  bind-address = ":8083"
-----------------------------------------------------

sudo service influxdb restart

Connet http://localhost:8083
If you can see the web page, the installation is finished

```

## 데이터 구조
```
- database
  - measurement
    - field
    - tag
```
* database : DBMS 의 database 와  같음
* measurement : DBMS 의 table 과 같음
* time : timestamp (nano sec)
* field : reading 로 구성
* tags : 인덱스 값으로 검색에 사용됨

### Python
```python
import tsdb

tr = tsdb.Transaction(<measurement>)
tr.write(value=<int, long, float>, meta=<str>, tag=<dict>, timestamp=<int, long>)
tr.flush()
```
1. tsdb.py 를 import 한다.
2. tr.Transaction() 함수 : series 을 지정한다 (해당 series 가 없어도 됨)
3. tr.write() 함수 : 저장할 값을 넘김, 저장하지 않을 값은 비워도 됨
4. tr.flush() 함수 : influxdb 에 저장

### [Java](java.md)

### HTTP 포트번호
  - 8086 (API 포트, SQL 제공)
  - 8083 (Admin 포트, 최신버전부터는 Grafana admin 연결 사용하여 더 이상 사용안함)

### Shell 명령

<pre>
tinyos@PaaS:~$ influx -database 'kwangmyung' -execute "SELECT Power FROM slave1_ctn_02 WHERE time >= '2017-04-26 00:00:00' limit 50" -format csv
   name,time,Power
   slave1_ctn_02,1493164818000000000,-1
   slave1_ctn_02,1493164861000000000,-1
   slave1_ctn_02,1493164902000000000,-3
   slave1_ctn_02,1493164945000000000,-3
   slave1_ctn_02,1493164988000000000,-1
</pre>

# Grafana

## 설치방법

```
wget https://bintray.com/fg2it/deb/download_file?file_path=testing%2Fg%2Fgrafana_4.1.0-1482275966beta1_armhf.deb
sudo apt-get install -y adduser libfontconfig
sudo dpkg -i grafana_4.1.0-1482275966beta1_armhf.deb
sudo service grafana-server start
sudo update-rc.d grafana-server defaults

Connet http://localhost:3000
If you can see the web page, the installation is finished.

Reference a link page to connect grafana and InfluxDB.
http://okky.kr/article/322237
```

## 정보

 * 초기설정 정보
  * grafana 접속 포트 : 3000
  * 계정 : admin / admin
  
* [참고자료](https://github.com/fg2it/grafana-on-raspberry)

### influxDB 데이터 검색
  - show databases, use {DB명}
  - https://docs.influxdata.com/influxdb/v0.9/query_language/schema_exploration/
