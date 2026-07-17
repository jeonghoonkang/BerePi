# DGX Spark 2-node vLLM 실행 노트

이 디렉터리의 스크립트는 두 대의 DGX Spark를 CX-7 Ethernet/RoCE로 연결하고, Ray cluster 위에서 vLLM을 실행한다. Node 1은 Ray Head와 vLLM API 서버를 담당하고 Node 2는 Ray Worker로 조인한다.

DGX Spark의 CX-7은 native InfiniBand가 아니라 Ethernet/RoCE 방식이므로 `ibstat`에 `Link layer: Ethernet`으로 표시되는 것이 정상이다.

## 파일 구성과 호출 순서

| 순서 | 파일 | 역할 |
| --- | --- | --- |
| 1 | `run_node1_head.sh` | Node 1 사전 검사, Ray Head 시작, Worker 대기, vLLM API 시작 |
| 2 | `multinode_common.sh` | 두 실행 스크립트가 `source`하여 사용하는 공통 검사 및 endpoint 선택 함수 |
| 3 | `join_node2_worker.sh` | Node 2 사전 검사, Head 연결 확인, Ray Worker 조인 |
| 참고 | `README_MULTINOTE.md` | 운영 순서와 변수 설명. 실행되는 파일은 아님 |

실제 운영 순서는 다음과 같다.

1. Node 1에서 `run_node1_head.sh`를 실행한다.
2. `run_node1_head.sh`가 같은 디렉터리의 `multinode_common.sh`를 불러온다.
3. Node 1의 Hugging Face token, `ibstat`, CX-7 interface, IPv4, Docker 상태를 검사한다.
4. Node 1 Docker container에서 `ray start --head`를 실행한다.
5. Node 1은 `CLUSTER_SIZE`만큼 Ray node가 모일 때까지 대기한다. 기본값은 Head와 Worker를 합한 `2`이다.
6. 별도 터미널의 Node 2에서 `join_node2_worker.sh`를 실행한다.
7. Node 2도 `multinode_common.sh`를 불러와 동일한 사전 검사를 수행하고, 선택된 CX-7 interface에서 Head IP로 ping한다.
8. Node 2 Docker container에서 `ray start --address=<HEAD_IP>:<RAY_PORT> --block`을 실행한다.
9. Node 1이 두 번째 Ray node를 확인하면 `vllm serve`를 시작한다.
10. vLLM API는 Node 1의 `API_PORT`에서 요청을 받는다.

즉, 전체 호출 흐름은 아래와 같다.

```text
Node 1: run_node1_head.sh
          └─ source multinode_common.sh
          └─ 사전 검사
          └─ Docker → ray start --head
          └─ Worker 조인 대기
                         ↑
Node 2: join_node2_worker.sh
          └─ source multinode_common.sh
          └─ 사전 검사 및 Head ping
          └─ Docker → ray start --address=HEAD_IP:RAY_PORT --block
                         ↓
Node 1: Ray node 수 확인 → vllm serve → OpenAI 호환 API 제공
```

`run_node1_head.sh`가 SSH로 Node 2를 자동 실행하지는 않는다. 두 노드에서 각각 스크립트를 직접 실행해야 한다.

## 실행 전 준비

두 노드에서 다음 조건을 만족해야 한다.

- 동일한 `multinode` 디렉터리와 동일한 Docker image를 사용한다.
- `server/hf_key.txt`에 Hugging Face token을 한 줄로 저장한다.
- CX-7 interface에 서로 통신 가능한 IPv4를 설정한다.
- `ibstat`, `ip`, `ping`, `docker` 명령을 사용할 수 있어야 한다.
- Docker에서 NVIDIA GPU runtime과 `--gpus all`을 사용할 수 있어야 한다.
- 일반 사용자로 실행한다면 `sudo docker`를 사용할 권한이 있어야 한다.
- 방화벽을 사용하는 경우 CX-7 endpoint 사이의 Ray 및 NCCL 통신을 허용한다.

기본 token 위치는 다음과 같다.

```text
server/
├── hf_key.txt
└── multinode/
    ├── multinode_common.sh
    ├── run_node1_head.sh
    ├── join_node2_worker.sh
    └── README_MULTINOTE.md
```

사전 검사에서 인정하는 CX-7/RDMA 상태는 다음과 같다.

- `ibstat`: `State: Active`
- `ibstat`: `Physical state: LinkUp`
- `ibstat`: `Link layer: Ethernet` 또는 `InfiniBand`
- 연결된 Linux interface: `LOWER_UP`
- 연결된 Linux interface: global IPv4 보유
- Node 2: 선택된 CX-7 interface에서 Node 1의 CX-7 IP로 ping 성공

하나라도 만족하지 않으면 Docker 또는 Ray를 시작하지 않고 오류로 종료한다.

## 실행 방법

### 1. Node 1 Head 실행

Node 1에서 먼저 실행한다. 다음 예시는 Node 1의 CX-7 IP가 `192.168.100.10`, API 포트가 `26000`인 경우다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/dgx_spark/server/multinode
HEAD_IP=192.168.100.10 ./run_node1_head.sh 26000
```

`HEAD_IP`를 생략하면 `ibstat`와 Linux network 상태를 통과한 CX-7 interface 중 첫 번째 global IPv4를 선택한다.

```bash
./run_node1_head.sh 26000
```

정상 실행되면 Node 1은 Ray Head를 시작한 후 다음과 비슷한 상태를 출력하며 Worker를 기다린다.

```text
[INFO] Ray active nodes: 1/2
```

### 2. Node 2 Worker 조인

Node 1이 기다리는 동안 Node 2의 별도 터미널에서 실행한다. 인자는 Node 1의 CX-7 IP다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/dgx_spark/server/multinode
./join_node2_worker.sh 192.168.100.10
```

Head로 가는 route를 기준으로 Node 2의 CX-7 IP와 interface를 자동 선택한다. 자동 선택이 잘못되거나 경로가 여러 개라면 `NODE_IP`를 명시한다.

```bash
NODE_IP=192.168.100.11 ./join_node2_worker.sh 192.168.100.10
```

Head IP는 환경 변수로 전달할 수도 있다.

```bash
HEAD_IP=192.168.100.10 ./join_node2_worker.sh
```

### 3. API 확인

Worker 조인이 완료되면 Node 1이 자동으로 vLLM API를 시작한다. Node 1에서 확인한다.

```bash
curl http://127.0.0.1:26000/v1/models
```

다른 시스템에서는 Node 1의 접근 가능한 IP를 사용한다.

```bash
curl http://<NODE1-IP>:26000/v1/models
```

### 4. 종료

먼저 Node 2 Worker 터미널에서 `Ctrl-C`를 누르고, 이어서 Node 1 Head 터미널에서 `Ctrl-C`를 누른다. 컨테이너는 `--rm`으로 실행되므로 정상 종료 후 자동 제거된다.

## 주요 변수

### 두 노드 공통

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `IMAGE` | `vllm/vllm-openai:gemma4-cu130` | Node 1과 Node 2가 실행할 Docker image. 두 노드에서 반드시 동일해야 한다. |
| `RAY_PORT` | `6379` | Ray Head 접속 포트. 두 노드에서 반드시 동일해야 한다. |
| `HF_CACHE_DIR` | `$HOME/.cache/huggingface` | Host의 Hugging Face cache. 컨테이너의 `/root/.cache/huggingface`에 mount된다. |
| `KEY_FILE` | `../hf_key.txt` | Hugging Face token 파일. 기본 경로를 변경할 때 사용한다. |

### Node 1: `run_node1_head.sh`

| 변수/인자 | 기본값 | 설명 |
| --- | --- | --- |
| 첫 번째 인자 | `26000` | vLLM API 포트. 예: `./run_node1_head.sh 26000` |
| `API_PORT` | `26000` | 첫 번째 인자가 없을 때 사용하는 API 포트 |
| `HEAD_IP` | 자동 감지 | Ray Head가 사용할 Node 1의 CX-7 IPv4 |
| `MODEL` | `google/gemma-4-31b-it` | vLLM이 로드할 Hugging Face model |
| `CLUSTER_SIZE` | `2` | Head를 포함하여 기다릴 전체 Ray node 수 |
| `CLUSTER_WAIT_TIMEOUT` | `600` | Worker 조인을 기다리는 최대 시간(초) |
| `PIPELINE_PARALLEL_SIZE` | `2` | vLLM pipeline parallel stage 수 |
| `TENSOR_PARALLEL_SIZE` | `1` | 각 pipeline stage의 tensor parallel 크기 |
| `GPU_MEMORY_UTILIZATION` | `0.85` | vLLM GPU memory 사용 비율 |
| `MAX_MODEL_LEN` | `8192` | 최대 model context 길이 |
| `MAX_NUM_SEQS` | `16` | 동시에 처리할 최대 sequence 수 |
| `HEAD_CONTAINER_NAME` | `dgx-spark-vllm-head` | Node 1 Docker container 이름 |

API 포트는 첫 번째 인자가 `API_PORT` 환경 변수보다 우선한다.

### Node 2: `join_node2_worker.sh`

| 변수/인자 | 기본값 | 설명 |
| --- | --- | --- |
| 첫 번째 인자 | 없음, 필수 | Node 1의 CX-7 IP. `HEAD_IP` 환경 변수로 대체 가능 |
| `HEAD_IP` | 없음 | 첫 번째 인자가 없을 때 사용할 Node 1 CX-7 IP |
| `NODE_IP` | route로 자동 감지 | Ray Worker가 사용할 Node 2의 CX-7 IPv4 |
| `RAY_JOIN_TIMEOUT` | `300` | Ray Head 연결을 재시도하는 최대 시간(초) |
| `WORKER_CONTAINER_NAME` | `dgx-spark-vllm-worker` | Node 2 Docker container 이름 |

Head IP는 첫 번째 인자가 `HEAD_IP` 환경 변수보다 우선한다.

### 내부에서 자동 생성되는 변수

다음 값은 `multinode_common.sh`가 감지하여 Docker container에 전달한다. 일반적으로 사용자가 직접 지정하지 않는다.

| 변수 | 설명 |
| --- | --- |
| `LOCAL_IP` | 선택된 로컬 CX-7 IPv4 |
| `LOCAL_IFACE` | 선택된 로컬 CX-7 Linux interface |
| `RDMA_HCA_LIST` | 활성 상태로 확인된 RDMA HCA 목록 |
| `RDMA_IFACE_LIST` | 활성 상태로 확인된 CX-7 network interface 목록 |

이 값들은 각각 `HEAD_IP`/`NODE_IP`, `GLOO_SOCKET_IFNAME`, `NCCL_IB_HCA`, `NCCL_SOCKET_IFNAME` 설정에 사용된다.

## 설정 변경 예시

Node 1:

```bash
HEAD_IP=192.168.100.10 \
IMAGE=vllm/vllm-openai:gemma4-cu130 \
MODEL=google/gemma-4-31b-it \
RAY_PORT=6379 \
PIPELINE_PARALLEL_SIZE=2 \
TENSOR_PARALLEL_SIZE=1 \
GPU_MEMORY_UTILIZATION=0.85 \
./run_node1_head.sh 26000
```

Node 2에서는 최소한 `IMAGE`와 `RAY_PORT`를 Node 1과 동일하게 맞춘다.

```bash
IMAGE=vllm/vllm-openai:gemma4-cu130 \
RAY_PORT=6379 \
NODE_IP=192.168.100.11 \
./join_node2_worker.sh 192.168.100.10
```

기본 구성은 GPU가 한 개씩 있는 두 노드를 대상으로 `PIPELINE_PARALLEL_SIZE=2`, `TENSOR_PARALLEL_SIZE=1`을 사용한다. 노드 또는 GPU 수를 변경하면 `CLUSTER_SIZE`와 parallel size를 함께 검토해야 한다.
