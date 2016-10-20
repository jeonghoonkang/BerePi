# InfluxDB

## 설치

```
wget https://dl.influxdata.com/influxdb/releases/influxdb_1.0.0_armhf.deb

sudo dpkg -i influxdb_1.0.0_armhf.deb

sudo service influxdb start
```

## 구조

```
- database
  - measurement
    - field
    - tag
```
* database : DBMS 의 database 와  같음
* measurement : table 과 같음 (이전 버전의 series)
* time : timestamp (unixtime)
* field : value, meta 로 구성
* tags : 인덱스 값

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


# Grafana

## 설치

```
wget https://github.com/fg2it/grafana-on-raspberry/raw/master/jessie/v3.1.1/grafana_3.1.1-1470786449_armhf.deb

sudo dpkg -i grafana_3.1.1-1470786449_armhf.deb

sudo service grafana-server start
```

## 정보

* grafana 접속 포트 : 3000
* 계정 : admin / admin

* [참고자료](https://github.com/fg2it/grafana-on-raspberry)
