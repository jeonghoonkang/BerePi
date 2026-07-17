# DGX Spark 멀티노드 실행 전 체크리스트

`run_node1_head.sh`를 실행하기 전에 Node 1과 Node 2의 CX-7 전용 네트워크를 준비하고 아래 항목을 확인한다. 가장 안전한 방법은 자동 감지에 맡기지 않고 `HEAD_IP`와 `NODE_IP`를 명시하는 것이다.

## 권장 네트워크 구성 예시

| 항목 | Node 1 | Node 2 |
| --- | --- | --- |
| 역할 | Ray Head / vLLM API | Ray Worker |
| CX-7 IP | `192.168.100.10/24` | `192.168.100.11/24` |
| Ray 포트 | `6379` | Node 1의 `6379`에 접속 |
| vLLM API 포트 | `26000` | 사용하지 않음 |

`HEAD_IP`에는 일반 LAN 또는 Wi-Fi IP가 아니라 Node 2와 연결된 Node 1의 CX-7 전용 IP를 사용한다.

## 1. CX-7 링크 상태 확인

Node 1과 Node 2에서 각각 실행한다.

```bash
ibstat
ip -br link
ip -br addr
```

`ibstat`에서 사용하는 CX-7 포트가 다음 조건을 만족해야 한다.

- `State: Active`
- `Physical state: LinkUp`
- `Link layer: Ethernet` 또는 `InfiniBand`

DGX Spark CX-7은 Ethernet/RoCE 방식이므로 `Link layer: Ethernet`으로 표시되는 것이 정상이다.

Linux 네트워크 인터페이스는 `UP`/`LOWER_UP` 상태이고 global IPv4를 가지고 있어야 한다.

```text
enp1s0f0np0  UP  192.168.100.10/24
```

## 2. RDMA 장치와 Linux 인터페이스 연결 확인

`ibstat`에 표시되는 RDMA 장치가 어떤 Linux 네트워크 인터페이스에 연결되어 있는지 확인한다.

```bash
for device in /sys/class/infiniband/*; do
    echo "RDMA: $(basename "$device")"
    ls "$device/device/net"
done
```

`run_node1_head.sh`와 `join_node2_worker.sh`는 이 정보를 `/sys/class/infiniband/<RDMA 장치>/device/net/`에서 자동으로 확인한다.

## 3. CX-7 IP와 subnet 확인

Node 1과 Node 2의 CX-7 IP가 같은 subnet에 있는지 확인한다.

```text
Node 1: 192.168.100.10/24
Node 2: 192.168.100.11/24
```

두 노드에서 다음 명령으로 실제 IP 할당 상태를 확인한다.

```bash
ip -o -4 addr show scope global
```

활성 CX-7 인터페이스가 여러 개라면 양쪽 노드의 대응 인터페이스가 서로 통신 가능한 subnet으로 대칭 구성되어야 한다.

## 4. Node 간 CX-7 통신 확인

Node 1에서 Node 2의 CX-7 IP로 ping한다.

```bash
ping -I <NODE1-CX7-인터페이스> -c 3 192.168.100.11
```

예:

```bash
ping -I enp1s0f0np0 -c 3 192.168.100.11
```

Node 2에서도 Node 1의 CX-7 IP로 ping한다.

```bash
ping -I <NODE2-CX7-인터페이스> -c 3 192.168.100.10
```

두 방향 모두 성공해야 한다. `join_node2_worker.sh`는 실행 과정에서 선택된 CX-7 인터페이스를 이용한 Node 1 ping을 다시 검사한다.

## 5. Node 2의 Head 경로 확인

Node 2에서 Head IP로 가는 route가 CX-7 인터페이스를 선택하는지 확인한다.

```bash
ip route get 192.168.100.10
```

예상 결과에는 Node 2의 CX-7 인터페이스와 CX-7 IP가 나타나야 한다.

```text
192.168.100.10 dev enp1s0f0np0 src 192.168.100.11
```

일반 LAN이나 Wi-Fi 인터페이스가 선택된다면 route 또는 CX-7 IP 구성을 먼저 수정한다. 경로 자동 선택이 모호한 경우 Worker 실행 시 `NODE_IP`를 명시한다.

## 6. 포트 및 방화벽 확인

최소한 다음 통신이 가능해야 한다.

- Node 2에서 Node 1 TCP `6379`: Ray Head 접속
- Node 1과 Node 2 사이: Ray 및 NCCL 내부 통신
- API client에서 Node 1 TCP `26000`: vLLM API 접속

현재 스크립트는 Ray 내부 포트를 고정하지 않는다. 방화벽을 사용한다면 CX-7 전용 subnet 내에서 Node 1과 Node 2 사이의 통신을 허용하는 것이 간단하다.

UFW 상태 확인:

```bash
sudo ufw status
```

CX-7 subnet이 `192.168.100.0/24`인 경우의 예시:

```bash
sudo ufw allow from 192.168.100.0/24
sudo ufw allow 26000/tcp
```

방화벽 변경은 실제 보안 정책과 외부 API 공개 범위를 검토한 후 적용한다.

## 7. 여러 CX-7 인터페이스 사용 시 주의

DGX Spark의 물리적 QSFP 연결 하나가 여러 Linux/RDMA 인터페이스로 나타날 수 있다. 현재 스크립트는 다음 조건을 모두 만족하는 장치와 인터페이스를 NCCL 후보로 사용한다.

- `ibstat`에서 `Active` 및 `LinkUp`
- Linux 인터페이스에서 `LOWER_UP`
- global IPv4 보유

활성 CX-7 인터페이스가 여러 개라면 다음 중 하나를 적용한다.

- 양쪽 노드의 대응 인터페이스와 subnet을 동일하게 구성한다.
- 실제 클러스터에 사용하지 않는 인터페이스의 IP를 제거하거나 인터페이스를 비활성화한다.

Node 1의 `HEAD_IP`와 Node 2의 `NODE_IP`를 명시하더라도 NCCL은 활성 상태로 감지된 CX-7/RDMA 장치 목록을 전달받으므로, 사용하지 않는 인터페이스를 활성 상태로 방치하지 않는 것이 좋다.

## 8. Docker 및 GPU 확인

두 노드에서 Docker daemon과 NVIDIA GPU 사용 가능 여부를 확인한다.

```bash
docker info
nvidia-smi
```

일반 사용자 계정에서 Docker 권한이 없다면 다음 명령도 확인한다.

```bash
sudo docker info
```

스크립트는 root가 아닐 때 `sudo docker`를 사용하며 컨테이너를 `--gpus all`, `--network host`, `--ipc host`, `--privileged` 옵션으로 실행한다.

## 9. Hugging Face token 확인

두 노드에 각각 다음 파일이 있어야 한다.

```text
/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/dgx_spark/server/hf_key.txt
```

파일에는 Hugging Face token 한 줄만 저장한다. Git 저장소에는 token 파일을 커밋하지 않는다.

다른 위치의 token 파일을 사용하려면 `KEY_FILE`을 지정한다.

```bash
KEY_FILE=/secure/path/hf_key.txt ./run_node1_head.sh 26000
```

## 10. Docker image와 설정 일치 확인

Node 1과 Node 2는 반드시 같은 `IMAGE`와 `RAY_PORT`를 사용해야 한다.

기본값:

```text
IMAGE=vllm/vllm-openai:gemma4-cu130
RAY_PORT=6379
```

두 노드에서 image를 미리 확인하거나 내려받을 수 있다.

```bash
sudo docker image inspect vllm/vllm-openai:gemma4-cu130
sudo docker pull vllm/vllm-openai:gemma4-cu130
```

## 11. Node 1 실행

Node 1의 CX-7 IP를 명시하여 실행하는 방법을 권장한다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/dgx_spark/server/multinode
HEAD_IP=192.168.100.10 ./run_node1_head.sh 26000
```

`HEAD_IP`를 생략하면 조건을 만족하는 CX-7 인터페이스 중 첫 번째 global IPv4를 자동 선택한다.

```bash
./run_node1_head.sh 26000
```

활성 CX-7 인터페이스가 여러 개이면 잘못된 주소가 선택될 수 있으므로 `HEAD_IP`를 명시한다.

Node 1이 정상적으로 Ray Head를 시작하면 Worker가 조인할 때까지 다음과 같은 상태로 기다린다.

```text
[INFO] Ray active nodes: 1/2
```

## 12. Node 2 Worker 조인

Node 1이 기다리는 동안 Node 2의 별도 터미널에서 실행한다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/dgx_spark/server/multinode
NODE_IP=192.168.100.11 ./join_node2_worker.sh 192.168.100.10
```

Node 2의 CX-7 route가 명확한 경우 `NODE_IP`는 생략할 수 있다.

```bash
./join_node2_worker.sh 192.168.100.10
```

Worker가 조인하면 Node 1에서 자동으로 `vllm serve`가 시작된다.

## 13. API 확인

Node 1에서 확인한다.

```bash
curl http://127.0.0.1:26000/v1/models
```

다른 시스템에서는 접근 가능한 Node 1 IP를 사용한다.

```bash
curl http://<NODE1-IP>:26000/v1/models
```

## 최종 체크

- [ ] Node 1과 Node 2의 CX-7 케이블이 연결되어 있다.
- [ ] 두 노드의 `ibstat`가 `Active`, `LinkUp`이다.
- [ ] CX-7 Linux 인터페이스가 `LOWER_UP`이다.
- [ ] 두 노드의 CX-7 IPv4가 같은 subnet에 있다.
- [ ] CX-7 인터페이스를 지정한 양방향 ping이 성공한다.
- [ ] Node 2의 Head route가 CX-7 인터페이스를 사용한다.
- [ ] Ray/NCCL 통신과 API 포트가 방화벽에서 허용되어 있다.
- [ ] 두 노드에서 Docker와 NVIDIA GPU를 사용할 수 있다.
- [ ] 두 노드에 `server/hf_key.txt`가 있다.
- [ ] 두 노드의 `IMAGE`와 `RAY_PORT`가 동일하다.
- [ ] Node 1의 `HEAD_IP`와 Node 2의 `NODE_IP`를 확인했다.
- [ ] Node 1을 먼저 실행한 후 Node 2를 조인한다.
