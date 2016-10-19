# InfluxDB

## 설치

```
wget https://dl.influxdata.com/influxdb/releases/influxdb_1.0.0_armhf.deb

sudo dpkg -i influxdb_1.0.0_armhf.deb

sudo service influxdb start
```

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

* [참고자료](github.com/fg2it/grafana-on-raspberry/)
