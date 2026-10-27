# PatchTST: daily CSV → 4× RTX 4090 DDP

Daily files are one continuous series **only when timestamps are adjacent**. The converter sorts files by their *first timestamp* (not filename), checks timestamp monotonicity, and records gaps as segment boundaries in `sensors.json`. Thus windows can cross midnight and file boundaries, but never a missing-data gap. All CSVs must contain the same sensor columns and timestamps at a fixed sampling interval. Do not mix independent machines into one input folder. Data with missing readings is segmented, not interpolated.

## DDP 개념

DDP는 **Distributed Data Parallel(분산 데이터 병렬 학습)**의 약자입니다. 각 GPU에 동일한 모델 전체를 복제하고, 학습 데이터 배치를 나누어 동시에 처리합니다. 각 GPU가 계산한 기울기(gradient)를 동기화한 뒤 같은 모델 파라미터로 갱신합니다.

```text
GPU 0: 모델 복사본 + 데이터 배치 A → 기울기 A ┐
GPU 1: 모델 복사본 + 데이터 배치 B → 기울기 B ├→ 기울기 동기화
GPU 2: 모델 복사본 + 데이터 배치 C → 기울기 C ┤        ↓
GPU 3: 모델 복사본 + 데이터 배치 D → 기울기 D ┘  각 모델을 같은 값으로 갱신
```

여기서 “병합”은 따로 학습한 모델들을 마지막에 합치는 것이 아니라 **학습 단계마다 기울기를 모아 동기화하는 것**입니다. 이 코드에서는 다음과 같이 구현합니다.

- `DistributedSampler`: 각 프로세스에 처리할 데이터 인덱스를 분배합니다. 길이를 맞추기 위해 일부 인덱스가 중복될 수 있습니다.
- `DistributedDataParallel`: GPU별 모델을 감싸고 `loss.backward()` 중 기울기 동기화를 처리합니다.
- `AdamW`: 동기화된 기울기로 각 프로세스에서 모델을 갱신합니다.
- `rank == 0`: 대표 프로세스가 최종 모델을 저장합니다. 별도의 최종 모델 병합은 필요하지 않습니다.

코드의 epoch 종료 시 `dist.all_reduce(total_loss)`는 학습 손실을 집계하는 연산입니다. 모델 학습용 기울기 동기화는 DDP가 별도로 수행합니다.

`--batch`는 GPU별 배치 크기입니다. 예를 들어 GPU 4개에서 `--batch 32`이면 일반적인 전체 학습 배치 크기는 `4 × 32 = 128`이며 마지막 배치는 더 작을 수 있습니다. DDP는 GPU마다 모델 전체와 학습 상태를 보유하므로 GPU 메모리를 하나로 합치거나 모델을 나누어 담는 방식은 아닙니다.

공식 설명: [PyTorch DistributedDataParallel](https://docs.pytorch.org/docs/stable/generated/torch.nn.parallel.DistributedDataParallel.html).

## Setup

Install a CUDA-enabled PyTorch compatible with the host driver, plus `numpy`.

## Input

```
data/2026-10-01.csv
data/2026-10-02.csv
```

```csv
Timestamp,temperature,pressure,vibration
2026-10-01 23:59:59,180.2,5.21,0.32
2026-10-02 00:00:00,180.5,5.23,0.34
```

Each individual file has a header; timestamps must be ISO 8601 and strictly increasing. All timestamps must have consistent timezone representation. Set `--interval-seconds` to the true sampling interval (1 for 1 Hz, 0.1 for 10 Hz).

## Convert

```bash
python csv_to_npy.py --input-dir ./data --pattern '*.csv' --output sensors.npy --timestamp Timestamp --interval-seconds 1 --columns temperature pressure vibration
```

Converter performs two streaming passes and writes `sensors.npy` and `sensors.json`. Requires disk space for `4 * row_count * sensor_count` bytes. All CSV data must be finite numeric values. If CSV changes between passes, rerun conversion.

## Train (one machine, 4 GPUs)

```bash
torchrun --standalone --nproc_per_node=4 train.py --data sensors.npy --task forecast --context 512 --horizon 96 --batch 32 --epochs 30 --out forecast.pt
torchrun --standalone --nproc_per_node=4 train.py --data sensors.npy --task anomaly --context 512 --batch 32 --epochs 30 --out anomaly.pt
```

The trainer uses a **global chronological 80% training cutoff**, rather than taking 80% of each daily CSV. Sliding windows do not cross gaps, and a window must fit entirely inside training. DDP distributes distinct windows to each GPU, synchronizing gradients via NCCL/PCIe; NVLink is not required.

**Limitations:** Training baseline only; no validation metrics, normalization, inference or anomaly threshold calibration yet. Normalize using training-period statistics only; otherwise results may be misleading. Anomaly training should use predominantly normal data. For multiple independent machines, convert/train separately or extend metadata to include machine boundaries. A `DistributedSampler` may pad with duplicate indices. Daily files with different timestamp formats or irregular sample periods must be cleaned/resampled first.

## 여러 서버에서 사용하는 멀티 노드 DDP 소개

DDP는 한 서버의 여러 GPU뿐 아니라 **서로 다른 서버의 GPU를 하나의 학습 작업으로 연결하는 멀티 노드 DDP**에도 사용할 수 있습니다. 예를 들어 서버 A의 GPU 2개와 서버 B의 GPU 2개가 총 4개의 학습 프로세스로 같은 모델을 학습할 수 있습니다.

```text
서버 A: GPU 0, GPU 1 ─┐
                     ├─ 총 GPU 4개: 데이터 분배 + 서버 간 기울기 동기화
서버 B: GPU 0, GPU 1 ─┘
```

현재 `train.py`는 `RANK`(전체 프로세스 번호), `WORLD_SIZE`(전체 프로세스 수), `LOCAL_RANK`(서버 내 GPU/프로세스 번호)를 읽고 NCCL 통신을 초기화합니다. 멀티 노드 실행에 필요한 기본 구조를 갖추고 있으며, 실제 실행에는 각 서버에서 `torchrun`으로 서버 수·서버별 번호·공통 연결 주소 등을 맞춰야 합니다. 위의 `--standalone` 명령은 한 서버용 예제입니다.

실행 환경에서는 다음 사항을 준비해야 합니다.

- 현재 코드의 CUDA/NCCL 경로를 지원하는 서버 환경과 서로 호환되는 PyTorch·CUDA·NCCL 구성
- 모든 서버의 동일한 학습 코드·모델 구조·학습 설정
- 동일한 `sensors.npy`와 `sensors.json` 및 데이터 순서. 공유 저장소 또는 동일 내용의 로컬 복사본 사용
- 서버 사이의 통신이 가능한 IP·네트워크 인터페이스와 방화벽 설정. 연결용 포트만 아니라 실제 NCCL 통신도 가능해야 함
- GPU마다 모델 전체·기울기·옵티마이저 상태·중간 활성값을 담을 충분한 메모리

기울기 동기화를 반복하므로 서버 간 네트워크 대역폭과 지연이 성능에 영향을 줍니다. 특히 인터넷을 통해 멀리 떨어진 서버를 연결하면 통신 대기가 커져 GPU 수만큼 속도가 빨라지지 않을 수 있습니다. GPU 성능이 서로 다른 경우에도 느린 프로세스가 동기화 시점의 대기를 늘릴 수 있습니다.

멀티 노드 DDP도 각 GPU에 모델 전체를 올립니다. 한 GPU에 담기 어려운 모델을 여러 GPU에 나누어 담는 목적이라면 FSDP·텐서 병렬화 등 별도 방식을 검토해야 합니다.

이 절은 개념 소개이며, 위 학습 예제의 여러 서버 실측 성능이나 연결 검증을 의미하지 않습니다. 공식 실행 옵션은 [PyTorch torchrun](https://docs.pytorch.org/docs/stable/elastic/run.html)을 참고하세요.
