# InfluxDB

## 하드웨어
![CO2_ module](../../../files/CO2/CO2_module.JPG)

## 설치

### 1) I2C tools 설치

```
sudo apt-get update && sudo apt-get instlal python-smbus i2c-tools
```

### 2) raspi-config 를 사용해서 I2C 사용하기

```
sudo raspi-config
```
`8.Advanced Options > A7.I2C > YES > YES`
을 차례대로 선택하고 재시작한다.

### 3) 시스템에서 I2C 모듈을 사용할 수 있도록 설정을 수정
 
```
sudo vim /etc/modules
```
* 다음 2줄을 파일 마지막에 추가
```
i2c-bcm2708
i2c-dev
```
* 수정된 파일이 아래와 같은지 확인
![edit modules](https://cdn-learn.adafruit.com/assets/assets/000/003/054/original/learn_raspberry_pi_editing_modules_file.png)

```
sudo vim /etc/modprobe.d/raspi-blacklist.conf
```
* 다음 2줄을 파일 마지막에 추가
```
blacklist spi-bcm2708
blacklist i2c-bcm2708
```
* 수정된 파일이 아래와 같은지 확인
![raspi-blacklist.conf](https://cdn-learn.adafruit.com/assets/assets/000/003/860/original/learn_raspberry_pi_blacklist.png)

```
sudo vim /boot/config.txt
```
* 다음 2줄을 파일 마지막에 추가
```
dtparam=i2c1=on
dtparam=i2c_arm=on
```
* 수정된 파일이 아래와 같은지 확인
![/boot/config.txt](https://cdn-learn.adafruit.com/assets/assets/000/022/830/original/learn_raspberry_pi_dtparami2c.png)
* 수정 후 재시작
```
sudo reboot
```

### 4) 센서 연결 확인

* 명령어를 입력한 후 결과에 따라 I2C 사용여부를 확인할 수 있다.
* 라즈베리 파이 모델 B 의 경우 `sudo i2cdetect -y 0`을 사용한다.
```
sudo i2cdetect -y 1
```
![i2cdetect result](https://cdn-learn.adafruit.com/assets/assets/000/003/055/original/learn_raspberry_pi_i2c-detect.png)

## 파일

- inBerePi.py : 실행파일
- tsdb.py : influxdb 모듈
- logger.py : python logging 모듈
- lib/sht25.py : sht20,sht25 온도,습도 모듈

## 실행

```
sudo python inBerePi.py
```

* [I2C 참고자료](https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup/configuring-i2c)
