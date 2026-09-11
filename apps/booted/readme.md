# Booting 후 초기 작업

- Crontab -e
  - @reboot sleep 5 && bash run.sh  

## Pironman5 경우
- GPIO로 Fan(LED) 동작 컨트롤 가능
  - GPIOD 설치시, bash 상에서 제어
  - gpioset {--mode=exit, signal} gpiochip4 6=1
  - 일반 User ID가 해당 GPIO를 제어하려면, group 과 rule 파일 적용되어 있어야 함
  - 대부분 하드웨어는 --mode=exit 로 동작을 잘함
    - 일부 이상 동작하는 하드웨어는 crontab @reboot 에서 --mode=signal 로 실행해서 강제로 gpiochip4의 GIO6 을 High로 유지해야함   

### Pironman 서비스와 OLED 상태 화면

2026-09-12 확인 환경: Ubuntu ARM64, Pironman 드라이버 1.3.18,
장치 설정은 Pironman 5 Max입니다. 드라이버는 이미 설치되어 있어 재설치하지
않고 기존 서비스를 설정했습니다. 실제 제품이 다르면 variant를 먼저 확인하세요.

```bash
pironman5 -v
pironman5 variant
sudo systemctl status pironman5.service --no-pager
```

OLED는 기본 설정에서 10초 후 절전 상태로 들어갑니다. 화면을 계속 켜고
시스템 정보를 갱신하려면 설정을 백업한 후 다음 명령을 실행합니다.

```bash
sudo cp -a /opt/pironman5/config.json \
  "/opt/pironman5/config.json.before-oled-$(date +%Y%m%d-%H%M%S)"
sudo pironman5 -oe true -os 0
sudo systemctl daemon-reload
sudo systemctl enable pironman5.service
sudo systemctl restart pironman5.service
```

- OLED 활성화, 절전 시간 `0`으로 설정해 화면을 계속 표시합니다.
- 확인한 드라이버는 화면을 약 1초마다 갱신하며, 시스템 데이터 수집 간격도 1초입니다.
- 기본 `mix` 화면은 CPU 사용률, 온도, 메모리 사용률 및 IP를 표시합니다.
- 정보 갱신과 페이지 자동 순환은 다릅니다. 별도 페이지 순환 타이머는 추가하지 않았습니다.
- 기존 RGB LED와 팬 설정은 변경하지 않았습니다. 공식 서비스와 GPIO 강제 제어
  스크립트를 동시에 실행하면 핀 제어가 충돌할 수 있으므로 중복 실행하지 마세요.

```bash
systemctl is-active pironman5.service
systemctl is-enabled pironman5.service
sudo journalctl -u pironman5.service --since '5 minutes ago' --no-pager
```

서비스 `active`, 자동 실행 `enabled`, OLED 초기화 및 시작 로그를 확인했습니다.
기존 대시보드의 HTTP 포트는 `34001`이며 HTTP 200 응답을 확인했습니다.
실제 OLED 화면 점등과 숫자 변화는 장치 앞에서 확인해야 합니다.
Nextcloud는 재시작하지 않았으며 정상 상태 응답을 확인했습니다.

기존 절전 설정으로 되돌리려면 `sudo pironman5 -os 10` 실행 후 서비스를
재시작합니다. 설정 백업 파일에는 다른 설정도 포함되므로 Git에 추가하지 마세요.

참고: [SunFounder 공식 명령어 안내](https://docs.sunfounder.com/projects/pironman5/en/latest/pironman5/control/control_with_commands.html)

### MacOS 는 RaspberryPi 인터넷 공유 간편히 설정 가능함
- MacOS 설정에서 인터넷 공유
- 아래 설정 파일에서 IP 확인
  - sudo vim /var/db/dhcpd_leases
   
