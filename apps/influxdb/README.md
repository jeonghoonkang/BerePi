# InfluxDB 메뉴얼
## 동작확인 방법

## 설치

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

## 구조

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

## 사용법

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

### HTTP 포트번호
  - 8086 (API 포트, SQL 제공)
  - 8083 (Admin 포트, 이제부터는 Grafana admin 연결 사용하여 더 이상 사용안함)

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

* grafana 접속 포트 : 3000
* 계정 : admin / admin

* [참고자료](https://github.com/fg2it/grafana-on-raspberry)

### influxDB 데이터 검색
  - show databases, use {DB명}
  - https://docs.influxdata.com/influxdb/v0.9/query_language/schema_exploration/
