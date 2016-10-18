# InfluxDB

## 하드웨어
![CO2_ module](../../files/CO2/CO2_module.JPG)

## 설치

### 1) install I2C tools

```
sudo apt-get update && sudo apt-get instlal python-smbus i2c-tools
```

### 2) Installing Kernel Support

```
sudo raspi-config
```
8.Advanced Options > A7.I2C > YES > YEs
and reboot!

### 3) Installing Kernel SUpport

```
sudo vim /etc/modules
```

## 실행

```
sudo python inBerePi.py
```

* [참고자료]()
