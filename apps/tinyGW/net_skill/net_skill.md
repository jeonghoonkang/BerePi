# tinyGW 네트워크 트래픽 모니터링 소프트웨어 설계

작성일: 2026-10-03. 대상: 단일 Raspberry Pi의 Ubuntu Server와 ipTIME 기반 내부 네트워크.

이 문서는 개발 요구사항과 실행 절차를 정의한다. `netmon` 명령, 설정 파일, 모듈은 **개발할 인터페이스**이며 현재 구현되어 있다는 의미가 아니다. `ip`, `tshark`, Python 표준 라이브러리 예제는 Ubuntu에서 수동 검증할 수 있는 명령이다. 실제 공유기 모델·펌웨어·회선 속도·LAN 주소는 설치 시 확인한다.

## 1. 목표와 기본 기능

- 내부 장치별 송수신량을 수집하고 스트리밍 노드, 상대 노드, 프로토콜, 관측 위치를 연결한다.
- CLI 한 번으로 30초 측정하고 1초 간격 전송률과 종료 후 평균·최대·P95를 표시한다.
- 장치 목록과 대역폭 사용률을 표와 항목별 요약으로 출력한다.
- 같은 측정 결과로 JSON·CSV·텍스트 로그를 만들고 Telegram 전송 대기열에 저장한다.
- Raspberry Pi 로컬 측정과 ipTIME 통계 수집을 독립 수집기로 구현한다.
- 초기 버전은 관측·알림을 담당한다. 속도 제한이나 QoS 변경은 별도 기능으로 두고 자동 적용하지 않는다.

## 2. 내부 네트워크를 관측하는 방법

일반 스위치의 LAN 포트에 Pi를 연결하면 Pi 자신의 통신과 전달되는 브로드캐스트·멀티캐스트 등을 볼 수 있다. 다른 두 장치 사이 유니캐스트는 promiscuous 모드만 켜도 보이는 것이 아니다. 관측 지점을 먼저 확보해야 한다. [Wireshark Ethernet 캡처 안내](https://wiki.wireshark.org/CaptureSetup/Ethernet)

| 방식 | 준비 및 관측 범위 | 주요 제한 |
| --- | --- | --- |
| Pi 자체 측정 | NIC 카운터 또는 Pi에서 패킷 캡처 | Pi를 통과하지 않는 장치 간 통신은 집계 불가 |
| 포트 미러링 | 지원 공유기/관리형 스위치에서 대상 포트를 Pi 포트로 복제 | 선택한 포트에 흐르는 트래픽만 관측; 미러 포트 용량 초과 시 손실 |
| Pi 경유 게이트웨이/브리지 | Pi의 유선 NIC 두 개를 통해 대상 트래픽을 통과시킴 | 같은 하위 스위치 안에서 끝나는 통신은 우회할 수 있음 |
| 공유기 통계 조회 | 관리 화면이 제공하는 WAN·IP·포트별 카운터 수집 | 모델별 지원 차이; LAN 내부 스위칭 통계가 없을 수 있음 |
| 노드별 에이전트 | 각 송수신 노드가 자신의 카운터를 Pi로 보고 | 노드 설치 필요; 중앙 집계 시 양 끝의 중복 계산 방지 |

권장 구성은 **Pi 한 대 + 미러링 지원 장비**이다. 추가 컴퓨터 없이 전체 수집·통계·로그·전송을 Pi가 수행한다. 미러링 장비가 없다면 우선 Pi 자체 통계와 공유기 통계를 수집하고 관측 범위를 명시한다.

```text
스트리밍 노드 ── 관리형 스위치 ── ipTIME ── 인터넷
                     │
               미러 대상 포트 복제
                     │
               Pi eth0: 관측
               Pi wlan0: 관리/Telegram
```

- 스위치 업링크만 복제하면 같은 스위치 내부의 카메라→NAS 통신이 빠질 수 있다. 실제 스트리밍 경로가 지나는 포트를 선택한다.
- 여러 포트의 ingress/egress를 모두 복제하면 동일 패킷이 중복될 수 있다. 먼저 복제 방향을 설계하고, 중복 가능 여부를 메타데이터로 남긴다. 해시 기반 제거로 정상 TCP 재전송까지 없애지 않는다.
- WAN 측 NAT 이후 캡처는 내부 IP 식별이 어렵다. 노드별 통계는 LAN 측을 기준으로 한다.
- Wi-Fi 연결 속도는 실제 사용 가능한 처리량과 다르다. 유선 관측을 기본으로 하고 무선 airtime 사용률은 별도 지표로 취급한다.

## 3. 수집·분석 구성

| 모듈 | 개발 기능 | 결과 |
| --- | --- | --- |
| `discovery` | 설정 노드, ARP/NDP 이웃, 공유기 DHCP 목록 병합 | 노드 ID, IP/MAC, 별칭, 마지막 발견 시각 |
| `collectors/interface` | NIC 누적 바이트·오류 카운터 수집 | Pi 인터페이스 전체 RX/TX |
| `collectors/packet` | 캡처 메타데이터를 스트림으로 처리 | 노드·방향·5-tuple별 바이트 |
| `collectors/iptime` | 모델별 로그인·기능 탐지·통계 파싱 | 공유기 원본 지표와 수집 시각 |
| `classifier` | 등록 서비스와 프로토콜 근거로 스트리밍 식별 | `confirmed`, `suspected`, `unknown` |
| `aggregator` | 1초 버킷 및 30초 집계 | 평균·최대·P95·사용률·점유율 |
| `reporter/storage` | 표 출력, 파일 원자적 저장, 보존 정책 | JSONL, JSON, CSV, TXT |
| `notifier/telegram` | 저장된 요약 전송·재시도 | 전송 상태 및 메시지 ID |

장치 발견과 트래픽 관측은 구분한다. `ip neigh`는 이미 관측한 이웃 목록이며 전체 장치 검색 결과가 아니다. MAC은 같은 L2 구간에서만 신뢰하고 VLAN을 함께 식별한다. 고정 `node_id`와 IP/MAC 이력을 유지하여 DHCP 주소 변경, IPv6 임시 주소, 이름 중복을 처리한다.

### 스트리밍 판별

- 사용자가 등록한 카메라/NVR/미디어 서버와 서비스·포트 규칙을 우선 적용한다. 장치의 모든 트래픽을 스트리밍으로 간주하지 않는다.
- RTSP 세션과 협상된 RTP 흐름 등 확인 가능한 근거가 있으면 `confirmed`로 기록한다. RTSP 제어 포트만 수집하면 별도 RTP 미디어를 놓칠 수 있다.
- 장시간 지속되는 전송률·패킷 패턴만으로 분류하면 `suspected`로 표시한다.
- HTTPS/QUIC의 443 포트만으로 영상, 백업, 파일 다운로드를 확정하지 않는다. 사용자 지정 흐름 또는 앱 측 메타데이터가 없으면 `unknown`을 허용한다.
- 노드 전체 전송률과 분류된 스트리밍 전송률을 각각 제공한다. 암호화된 트래픽의 내용을 복호화하는 기능은 요구하지 않는다.

## 4. 30초 CLI 측정 설계

다음은 **구현 예정 명령**이다. 설치 후 `netmon --help`에 동일한 옵션과 제한을 제공한다.

```bash
netmon doctor --config ./netmon.yaml
netmon nodes list --config ./netmon.yaml
netmon monitor --interface eth0 --duration 30 --interval 1 \
  --config ./netmon.yaml --top 10 --output ./logs
netmon report --run ./logs/<run_id> --format text
netmon telegram enqueue --run ./logs/<run_id>
netmon telegram send-pending --limit 10
```

1. 관측 모드, NIC, LAN CIDR, 링크 용량, 저장 공간, 캡처 권한을 확인한다.
2. 수집기 준비가 끝난 시점을 시작점으로 삼고 monotonic clock으로 30초를 측정한다.
3. 매초 전체 및 노드별 RX/TX Mbps를 갱신한다. 입력이 없어도 타이머가 동작해야 한다.
4. 30초 경계에서 수집을 종료하고 마지막 부분 구간의 실제 시간을 반영한다.
5. 캡처 성공 중 패킷이 없으면 0으로, 수집 오류/단절/누락이면 `null`과 사유로 기록한다.
6. 요약 파일을 저장한 다음에만 전송 대기열을 만든다. Telegram 요청 시간은 측정 시간에서 제외한다.

`--stream-only`는 분류 후 표시 필터로 구현한다. 원래 관측 트래픽 합계를 별도 유지해야 스트리밍 비중을 계산할 수 있다. 긴 실행에서는 Ctrl+C도 부분 결과와 `interrupted` 상태를 저장한다.

### 실제로 실행 가능한 Pi 인터페이스 30초 측정

아래는 Pi의 선택한 NIC 전체 전송률을 매초 출력하는 최소 예제다. 스트리밍 노드별 분류는 하지 않는다. `eth0`를 실제 인터페이스로 바꾼다. Linux는 sysfs에서 NIC 바이트 카운터를 제공한다. [Linux 인터페이스 통계](https://docs.kernel.org/networking/statistics.html)

```bash
ip -br link
ip route show default
ip neigh show

python3 - eth0 <<'PY'
import pathlib
import sys
import time

base = pathlib.Path('/sys/class/net') / sys.argv[1] / 'statistics'
def read_bytes():
    return tuple(int((base / f'{d}_bytes').read_text()) for d in ('rx', 'tx'))

prev = read_bytes()
start = previous_time = time.monotonic()
total = [0, 0]
print('elapsed_s  RX_Mbps  TX_Mbps', flush=True)
for step in range(1, 31):
    time.sleep(max(0, start + step - time.monotonic()))
    current = read_bytes()
    now = time.monotonic()
    delta = [current[i] - prev[i] for i in range(2)]
    if min(delta) < 0:
        raise SystemExit('카운터 초기화 감지: 측정을 다시 시작하세요.')
    rates = [b * 8 / (now - previous_time) / 1_000_000 for b in delta]
    total = [total[i] + delta[i] for i in range(2)]
    print(f'{now-start:9.2f} {rates[0]:8.3f} {rates[1]:8.3f}', flush=True)
    prev, previous_time = current, now
elapsed = previous_time - start
print(f'평균 RX={total[0]*8/elapsed/1e6:.3f} Mbps, '
      f'TX={total[1]*8/elapsed/1e6:.3f} Mbps, 측정={elapsed:.3f}s')
PY
```

### 실제 패킷 수집과 종료 후 통계 확인

Ubuntu에 TShark가 설치되어 있고 캡처 권한이 있는 상태에서 실행한다. 이 예제는 진단용 PCAP을 저장하므로 패킷 내용이 포함될 수 있다. 운영 기본 모드는 메타데이터만 남긴다.

```bash
umask 077
RUN_DIR="./logs/manual-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$RUN_DIR"
sudo tshark -n -i eth0 -a duration:30 -w "$RUN_DIR/capture.pcapng"
sudo tshark -n -r "$RUN_DIR/capture.pcapng" -q \
  -z io,stat,1 -z conv,ip -z conv,ipv6 \
  > "$RUN_DIR/traffic-summary.txt"
```

`-a duration:30`은 캡처 종료 조건, `io,stat,1`은 1초 단위 바이트 통계, `conv,ip`/`conv,ipv6`는 주소 쌍별 통계다. 위 통계는 **종료 후 출력**된다. 실행 중 노드별 전송률은 개발할 `collectors/packet`에서 `tshark -l -T fields` 출력과 독립 타이머로 집계한다. [TShark 명령 설명](https://www.wireshark.org/docs/man-pages/tshark.html)

## 5. 전송률·대역 사용률 계산 규칙

모든 속도는 decimal Mbps, 데이터량은 MB 또는 MiB를 명시한다. 노드 TX/RX는 **해당 내부 노드 기준**이다. Pi NIC의 RX/TX, 공유기의 WAN 업로드/다운로드와 별도 필드로 저장한다.

```text
rate_mbps = delta_bytes × 8 / actual_elapsed_seconds / 1,000,000
avg_mbps  = total_bytes × 8 / measurement_seconds / 1,000,000
peak_mbps = 유효한 1초 버킷 전송률의 최대값
p95_mbps  = 유효한 버킷 전송률 정렬 후 ceil(0.95 × N)번째 값
TX 사용률 = node_tx_mbps / 해당 경로 TX 용량_mbps × 100
RX 사용률 = node_rx_mbps / 해당 경로 RX 용량_mbps × 100
노드 점유율 = node_tx_rx_bytes / 모든 내부 노드 tx_rx_bytes 합 × 100
```

- 전이중 1 Gbps 링크는 송수신 각각 1 Gbps이다. `(RX+TX)/1Gbps`를 링크 사용률로 표시하지 않는다.
- 인터넷 업로드는 계약/설정한 업로드 용량, 다운로드는 다운로드 용량, 내부 전송은 해당 LAN 링크 용량을 분모로 사용한다. 분모의 출처를 함께 기록한다.
- 용량을 모르면 Mbps만 표시하고 사용률은 `N/A`로 둔다. 공유기 QoS 제한값은 실제 전송률이 아니다.
- 카메라 A→NAS B 한 패킷은 A의 TX와 B의 RX에 각각 들어간다. 노드 합계를 네트워크 총량으로 쓰면 두 번 계산된다. 전체 관측량은 관측 지점에서 한 번만 집계하고, 노드 점유율은 위의 별도 분모를 사용한다.
- 멀티캐스트 수신자를 목적지 그룹 주소만 보고 특정 노드에 할당하지 않는다. 그룹별 통계를 분리하고, 실제 수신 여부가 확인된 노드만 연결한다.
- NIC 카운터, `frame.len`, 공유기 카운터는 계층과 오버헤드가 다를 수 있다. `byte_basis`와 수집기를 명시하고 서로 합산하지 않는다. 패킷 기반 수치는 애플리케이션 영상 인코딩 비트레이트와 다르다.
- 누락 버킷은 0으로 채우지 않고 통계에서 제외하며 `valid_seconds`, `sample_count`, `coverage_ratio`를 표시한다. 모든 구간이 유효할 때만 전체 30초 평균을 정상 결과로 표시한다.
- 30초 P95는 짧은 관측 구간의 통계다. 장기 P95로 해석하지 않는다. 누적 카운터 감소 시 재부팅/리셋/비트폭을 확인하고 불명확하면 해당 구간을 무효화한다.

### 노드 목록과 항목별 표시 예시

**아래 수치는 형식 설명용 가상 값이며 실측 결과가 아니다.** 관측 범위는 A/B/C의 유니캐스트 트래픽, 각 노드 링크는 전이중 1,000 Mbps라고 가정한다. 평균 TX+RX 내림차순으로 정렬한다.

| 순위 | 노드/IP | 분류 | 평균 TX/RX Mbps | TX/RX 사용률 | 노드 점유율 |
| --- | --- | --- | --- | --- | --- |
| 1 | NAS / 192.168.0.20 | 등록 미디어 서버 | 0.4 / 20.0 | 0.04% / 2.00% | 50.0% |
| 2 | camera-01 / 192.168.0.31 | 확인된 RTSP/RTP | 12.0 / 0.2 | 1.20% / 0.02% | 29.9% |
| 3 | camera-02 / 192.168.0.32 | 확인된 RTSP/RTP | 8.0 / 0.2 | 0.80% / 0.02% | 20.1% |

- **NAS**: 수신 평균 20.0 Mbps, 1초 최대 24.0 Mbps, P95 23.0 Mbps. 카메라 두 대의 수신 종단.
- **camera-01**: 송신 평균 12.0 Mbps, 1초 최대 15.0 Mbps, P95 14.0 Mbps. 30초 송신량 45.0 MB, 수신량 0.75 MB.
- **camera-02**: 송신 평균 8.0 Mbps, 1초 최대 10.0 Mbps, P95 9.0 Mbps. 30초 송신량 30.0 MB, 수신량 0.75 MB.
- **전체 관측량**: 고유 프레임 기준 20.4 Mbps, 76.5 MB/30초. 노드 송수신 합계는 40.8 Mbps이며 내부 통신 양 끝을 포함한다.
- **데이터 품질**: 측정 시간, 수집기, 대상 포트, 드롭 수, 분류 미확정 비중을 함께 출력한다. 미러 포트 이전 손실은 Pi의 드롭 카운터 0만으로 배제할 수 없다.

## 6. 로그 저장과 Telegram 연계

### 파일 및 스키마

```text
logs/<UTC시각>_<UUID>/
  metadata.json       # 설정 스냅샷(비밀 제외), 관측 위치, 시작/종료, 상태
  samples.jsonl       # 1초 단위 노드·방향별 측정
  summary.json        # 기계 처리용 전체/노드 통계
  nodes.csv           # 정렬된 노드별 통계
  telegram.txt        # 사람이 읽을 요약
outbox/<run_id>.json   # pending/sending/sent/failed/unknown 상태
```

필수 필드는 `schema_version`, `run_id`, UTC 시각, `duration_actual_s`, `collector`, `capture_scope`, `interface`, `byte_basis`, `node_id`, IP/MAC/VLAN, `tx_bytes`, `rx_bytes`, 평균/최대/P95, 용량 및 출처, 분류 근거, `sample_count`, `valid_seconds`, 드롭 및 오류다. 수집 불가 값은 JSON `null`로 저장한다.

임시 파일 작성 후 rename으로 완료 결과를 공개한다. 중간 종료 시 부분 로그를 보존하고 `complete=false`를 기록한다. 디렉터리 0700, 파일 0600을 기본으로 사용한다. 제안 보존 정책은 초별 로그 7일, 요약 90일, 진단 PCAP 24시간이다. 총 저장 한도를 설정하여 오래된 완료 로그부터 정리하되 전송 대기 로그는 별도로 관리한다.

### Telegram 전송 흐름

1. BotFather에서 봇을 생성하고 토큰과 수신 `chat_id`를 설정한다. 개인 채팅은 먼저 봇과 대화를 시작하고, 그룹은 봇을 추가하여 전송 권한을 확인한다.
2. 토큰·공유기 암호는 저장소 밖의 권한 제한 파일 또는 서비스 자격 증명 저장소에 둔다. 명령 인자·로그·오류 URL에 비밀을 출력하지 않는다.
3. `telegram.txt`에는 측정 범위, 30초 평균/최대, 상위 노드, 오류/누락, `run_id`를 넣는다. 기본은 plain text로 렌더링한다.
4. 봇 API `sendMessage`로 HTTPS POST를 수행한다. 텍스트는 메시지당 4,096자 제한을 고려해 3,500자 정도에서 항목 단위로 나누고 `(1/2)`처럼 표시한다. 큰 상세 결과는 별도 파일 전송 기능으로 확장한다. [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage)
5. HTTP 성공뿐 아니라 응답 `ok=true`를 확인한 뒤 `message_id`, `sent_at`을 기록한다. 429는 `retry_after`, 네트워크/5xx는 지수 백오프를 적용한다. 400/401/403은 설정 확인 대상으로 보류한다.
6. `run_id + chat_id + part_index`로 로컬 중복 전송을 방지한다. 원격 성공 후 응답 유실은 중복 여부를 확정할 수 없으므로 `unknown`으로 남기고 재전송 정책을 명시한다.

기본 동작은 **요약 저장**이다. 전송은 명시적 `send-pending` 또는 설정한 스케줄로 실행한다. 봇 생성·실제 메시지 발송은 이 문서 작성 단계에서 수행하지 않는다.

## 7. 단일 Raspberry Pi Ubuntu 실행 방법

### 준비

개발 기준 환경은 Raspberry Pi 4/5, Ubuntu Server 24.04 LTS arm64로 제안한다. Pi 5의 Ubuntu 24.04 지원은 공식 릴리스 문서에 명시되어 있다. 설치 이미지와 보드 호환성은 [Ubuntu Raspberry Pi 설치 안내](https://ubuntu.com/hardware/docs/boards/how-to/ubuntu_supported/raspberry-pi/) 및 [24.04 릴리스 안내](https://documentation.ubuntu.com/release-notes/24.04/)에서 확인한다.

```bash
cat /etc/os-release
uname -m
sudo apt update
sudo apt install -y python3 python3-venv tshark iproute2 ethtool
ip -br addr
ip -s link show eth0
sudo ethtool eth0
```

패키지 설치 과정의 비관리자 캡처 허용 여부는 운영 계정 정책에 맞게 선택한다. 전체 분석기와 Telegram 전송기를 root로 실행하지 않고, 운영 시 패킷 수집에만 필요한 권한을 분리한다.

- **NIC 한 개, 일반 LAN 연결**: 4절의 Python 예제로 Pi 자체 전송률 측정. 공유기 로그인 수집기는 같은 Pi에서 실행 가능하다.
- **NIC 한 개 + 별도 Wi-Fi 관리 연결**: 유선은 미러 대상 포트에 연결하고 Wi-Fi로 관리/전송한다. 미러 포트의 일반 송신 가능 여부를 가정하지 않는다.
- **유선 NIC 두 개**: USB Ethernet을 추가해 투명 브리지 또는 라우팅 경로로 구성 가능하다. 브리지 IP·기본 경로·방화벽·DHCP 제공 주체를 정하고 유지보수 시간에 적용한다. 집계는 한쪽 인터페이스에서만 수행한다.
- **라우터 모드**: 하위 노드의 기본 게이트웨이를 Pi로 설정하고 IP forwarding, 방화벽, 상위 정적 경로 또는 NAT를 설계한다. 단순히 NIC를 추가하는 것만으로 모든 트래픽이 경유하지 않는다.

Pi는 수집 → 집계 → 저장 → Telegram 큐 처리를 한 대에서 수행한다. Python 표준 라이브러리 기반 집계부터 시작하고, 설치형 CLI 패키지로 배포한다. systemd의 일회 실행 서비스와 timer로 5분마다 30초 측정을 수행하는 방식을 기본 제안한다. 파일 잠금으로 중복 실행을 막고, 전송 worker는 별도 서비스로 둔다.

30초마다 전 구간을 연속 관측하려면 장기 실행 수집기가 30초 창을 연속 생성하도록 확장한다. 디스크 쓰기는 배치 처리하고 원본 패킷 상시 저장은 끈다. 지속적인 고속 패킷 처리 성능은 모델·패킷 크기·USB NIC에 따라 실제 부하 시험으로 결정한다.

### 구현 예정 설정 예시

```yaml
schema_version: 1
mode: mirror
interface: eth0
lan_cidrs: [192.168.0.0/24]  # 실제 IPv6 내부 prefix도 추가
measurement:
  duration_s: 30
  interval_s: 1
capacity:
  lan_link_mbps: 1000
  wan_upload_mbps: null
  wan_download_mbps: null
  source: operator_config
nodes:
  - id: camera-01
    name: camera-01
    addresses: [192.168.0.31]
    role: camera
    stream_rules:
      - protocol: rtsp
        server_port: 554
logging:
  directory: /var/lib/netmon/logs
  raw_pcap: false
telegram:
  enabled: false
  credentials_file: /etc/netmon/telegram.env
iptime:
  enabled: false
  base_url: http://192.168.0.1
  adapter: null  # 확인된 모델/펌웨어 전용 어댑터
  poll_interval_s: 5
  credentials_file: /etc/netmon/iptime.env
```

## 8. ipTIME 로그인 및 정보 수집 방법

### 사람이 먼저 확인하는 절차

1. Pi에서 `ip route show default`로 게이트웨이 후보를 확인한다. 기본 게이트웨이가 ipTIME인지, 별도 관리 IP가 있는지 확인한다. `192.168.0.1`은 흔한 예시이며 고정값이 아니다.
2. 같은 관리 LAN의 브라우저에서 공유기 관리 주소에 접속하고 소유자가 설정한 관리자 계정으로 로그인한다.
3. 모델명·하드웨어 버전·펌웨어 버전을 기록한다. 연결된 장치/DHCP 목록, 트래픽 관련 화면에서 실제 제공하는 필드와 단위를 확인한다.
4. WAN 전체 통계, IP별 전송률, 누적 바이트, 포트별 통계 중 있는 항목을 구분한다. 갱신 간격, 업로드/다운로드 방향, 카운터 초기화 조건도 기록한다.
5. 지원 장비라면 포트 미러링을 구성할 수 있다. 공식 안내의 메뉴 예시는 `고급설정 → 트래픽 관리 → 스위치설정`이며 모델·펌웨어에 따라 확인해야 한다. [ipTIME 포트 미러링 안내](https://iptime.com/support/faq/7427)
6. QoS는 모델별로 IP 또는 포트 단위 지원이 다르다. 설정된 최소 보장/최대 제한 속도를 실측값으로 읽지 않는다. [ipTIME QoS 지원 및 설정 안내](https://iptime.com/support/faq/7227)

### 개발할 자동 수집 어댑터

모든 ipTIME에서 통하는 공개 통계 API·로그인 URL·SNMP·SSH 지원을 전제하지 않는다. **특정 장비에서 검증한 요청만** 어댑터에 등록한다.

1. 브라우저 개발자 도구 Network에서 정상 로그인과 통계 화면 갱신 요청을 확인한다. URL, 메서드, 세션 쿠키, CSRF 처리, 응답 형식과 단위를 기록하되 비밀은 제거한다.
2. 문서화된 인터페이스가 있으면 우선 사용한다. 없으면 모델/펌웨어별 HTTP 세션 수집기를 구현하고, 필요한 경우 브라우저 자동화로 화면 데이터를 읽는다.
3. `probe_capabilities()`에서 `device_inventory`, `wan_counters`, `per_ip_counters`, `instant_rates`, `port_mirroring`의 지원 여부를 반환한다. 미지원은 0이 아니라 `unsupported`로 표시한다.
4. 로그인 성공은 HTTP 200만으로 판단하지 않는다. 인증된 통계 화면 또는 데이터 스키마를 확인한다. 세션 만료 시 제한적으로 재로그인하고, 반복 실패·계정 잠금·추가 인증은 중단 상태로 보고한다.
5. 누적 카운터가 있으면 t=0과 t=30초를 포함하여 수집하고 실제 시간 차로 평균을 계산한다. 중간 수집 간격은 5초부터 시작하여 장비 부담과 화면 갱신 주기를 검증한다.
6. 화면의 순간 전송률만 제공하면 `router_reported_rate`로 보존한다. 갱신 주기가 불명확한 값을 1초 표본이나 정확한 누적 바이트로 변환하지 않는다. P95도 해당 표본 수·갱신 주기와 함께 표시한다.
7. HTML 구조나 JSON 필드가 달라지면 파싱 실패로 처리하고, 오래된 값을 최신 값으로 출력하지 않는다. 원본 응답 fixture는 인증정보를 제거한 상태로 보관한다.

관리 UI가 HTTP만 지원하면 신뢰할 수 있는 관리 LAN에서 접속하고 외부 관리 포트를 열지 않는다. 인증 쿠키는 제한된 저장소에 두고 로그에서 제거한다. SNMP 카운터가 실제로 제공되는 모델도 인터페이스 전체 값인지 노드별 값인지 별도로 검증한다.

| 확인 결과 | 적용할 수집 방식 | 표시할 한계 |
| --- | --- | --- |
| IP별 누적 바이트 제공 | 공유기 전후 카운터 차이 | 해당 기능이 집계하는 경로만 포함 |
| WAN 전체 값만 제공 | WAN 평균 RX/TX와 장치 목록 분리 | 장치별 대역폭 추정 불가 |
| 장치 목록만 제공 | 목록은 공유기, 트래픽은 Pi 미러링 | 장치 목록 자체는 사용량이 아님 |
| 통계 없음, 미러링 지원 | Pi 패킷 수집 | 미러 대상 포트 범위 |
| 둘 다 미지원 | Pi 자체 통계, 별도 미러링 스위치/경유 구조 | 전체 LAN 통계 불가 |

## 9. 개발 순서와 검증 기준

1. **기본 CLI**: NIC 카운터 30초 측정, 1초 표시, 종료·중단·카운터 리셋 처리, JSON/TXT 저장.
2. **노드별 분석**: IPv4/IPv6 및 VLAN 식별, 송수신 방향, 스트리밍 분류, 표/항목별 보고서.
3. **로그·알림**: 원자적 저장, 보존 한도, Telegram 큐 및 실패 복구.
4. **ipTIME 연동**: 실제 장비 모델·펌웨어 확인 후 로그인·스키마 fixture 기반 어댑터 구현.
5. **운영 배포**: Pi의 systemd 서비스, 리소스 계측, 미러링 경로별 부하 검증.

검증할 핵심 사례:

- 전송률 계산: 1초에 1,000,000 bytes이면 8 Mbps; 30초에 30,000,000 bytes도 평균 8 Mbps.
- 무트래픽: 패킷 입력 없이도 30초 후 종료하고 정상적인 0과 수집 실패를 구분한다.
- 방향·중복: A→B 흐름이 A TX/B RX에 잡히고 전체 관측 바이트에는 한 번만 포함된다.
- 관측 범위: 일반 LAN 포트에서 다른 노드가 보이지 않을 때 전체 네트워크가 조용하다고 보고하지 않는다.
- 손실·성능: 드롭 발생 시 품질 경고와 유효 구간을 기록하고 CPU·메모리·디스크 한도를 확인한다.
- 암호화·IPv6·멀티캐스트: 미확정 스트림과 그룹 주소를 올바르게 분리한다.
- 공유기: 카운터 리셋, 세션 만료, 로그인 페이지 반환, 미지원 기능, 펌웨어 변경을 각각 재현한다.
- Telegram: 오프라인 상태에서도 로그 보존, 429 재시도, 토큰 오류 보류, 응답 유실 및 다중 파트 전송 상태 확인.

이 문서의 명령은 실제 Raspberry Pi나 ipTIME 장비에서 실행 검증하지 않았다. 배포 완료 조건은 대상 장비에서 30초 실측, 노드별 표 확인, 파일 저장, 지정 Telegram 채팅으로의 시험 전송까지 수행하는 것이다.
