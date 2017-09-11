# 이미지

## 개요
* 이미지를 주기적으로 최신 버전으로 업데이트
  * [Raspbian](https://www.raspberrypi.org/downloads/raspbian/)
    * download: 2017-04-10
  * [TinyOS](http://tinyos.net/)
    * apt: 지원되지 않음
    * download: 2.1.2
  * [InfluxDB](https://www.influxdata.com/)
    * apt: ?
    * download: ?
  * [Zabbix](http://www.zabbix.com/)
    * apt: ?
    * download: ?
* 메인 하드웨어: 라즈베리파이3

## Version History
| 날짜 | Raspbian | TinyOS | InfluxDB | Zabbix |
| - | - | - | - | - |
| 2017-06-08 | Jessie</br>2017-04-10? | 2.1.2 | ? | ? |

## 백업
### [piclone](piclone.txt)
### [백업된 라즈베리파이 이미지 용량 줄이기](http://deois.tistory.com/70)

## 개요 (sonnonet-raspberrypi)
## sono-rpc-00 (raspberrypi with camera)

* 이미지를 주기적으로 최신 버전으로 업데이트

  * [강책임님이미지](http://cogcom.asuscomm.com:6080/open/2017-06-BerePi-jessie-4G.img.gz)
    * download: 2017-06-BerePi-jessie-4G
  * [TinyOS](https://github.com/OKCOMTECH/Raspberry_SensorKit/blob/master/RaspberryPi/Install_tinyos.md)
    * download: 2.1.2
  * [InfluxDB](https://github.com/OKCOMTECH/Raspberry_SensorKit/blob/master/RaspberryPi/Install_influxdb.md)
    * ver 1.2.4
    * influxdb configuration : admin -p 8083 , general -p 8086
    
```bash
    ---------- etc ---------------
    user : pi , passwd : tinyos0
    hostname : sono-rpc-00
```
    
* 메인 하드웨어: 라즈베리파이3

## Version History
| 날짜 | Raspbian | TinyOS | InfluxDB | Zabbix |
| - | - | - | - | - |
| 2017-09-11 | sono-rpc-00</br>| 2.1.2 | 1.2.4 | ? |
