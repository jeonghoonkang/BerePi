# GPU 추론 벤치마크 실행 방법

`gpu_inference_benchmark.py` 스크립트는 CUDA GPU 사용 가능 여부를 자동으로 감지하고, 워밍업 이후 반복 추론을 수행하여 평균 지연시간과 처리량을 계산합니다.

## 요구 사항
- Python 3.8+
- PyTorch (CUDA 지원 버전 권장)

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## 실행 방법
```bash
cd apps/deeplearning/PyTorch
python gpu_inference_benchmark.py --batch-size 128 --benchmark-iters 200
```

CUDA가 정상적으로 구성된 환경이라면 자동으로 GPU가 선택됩니다. GPU 사용을 강제하고 싶다면 `--device cuda` 옵션을 지정하세요. CUDA가 활성화되지 않은 상태에서 해당 옵션을 사용하면 오류가 발생하므로 GPU 환경을 점검해야 함을 즉시 알 수 있습니다.

### 선택 옵션
- `--warmup-iters`: 타이머 측정을 시작하기 전 워밍업 반복 횟수 (기본값 20)
- `--benchmark-iters`: 실제 측정 반복 횟수 (기본값 100)
- `--half`: GPU 사용 시 float16(half precision)으로 추론 수행
- `--device`: `auto`(기본), `cpu`, `cuda`, `cuda:0` 등으로 실행 장치를 직접 지정
- `--check-env`: PyTorch 빌드와 CUDA, GPU 인식 여부를 출력하고 벤치마크를 종료

### 예시
```bash
# GPU 사용을 강제하고 half precision 모드를 사용하는 예시
python gpu_inference_benchmark.py --batch-size 64 --benchmark-iters 200 --half --device cuda

# 특정 GPU 인덱스를 지정하고 싶은 경우
python gpu_inference_benchmark.py --batch-size 64 --benchmark-iters 200 --device cuda:1
```

## GPU 실행 환경 빠르게 점검하기
먼저 PyTorch가 GPU를 인식하는지 확인하려면 `--check-env` 옵션을 실행하세요. CUDA 런타임, cuDNN 버전, 감지된 GPU 목록과 메모리 용량을 즉시 확인할 수 있습니다.

```bash
python gpu_inference_benchmark.py --check-env
```

출력에서 `CUDA available  : True` 로 표시되고 원하는 GPU가 나열된다면 벤치마크를 실행할 준비가 된 것입니다. False라면 아래 점검 항목을 통해 환경을 재구성하세요.

## GPU 사용이 되지 않을 때 점검 사항
1. **CUDA 드라이버 확인**: 호스트에서 `nvidia-smi`를 실행해 GPU가 인식되는지 확인합니다.
2. **PyTorch CUDA 빌드 설치**: CPU 전용 패키지가 설치된 경우 GPU를 사용할 수 없습니다. 위의 `pip install ...` 명령처럼 CUDA 버전에 맞는 PyTorch를 설치하세요.
3. **CUDA_VISIBLE_DEVICES 환경 변수**: 특정 GPU만 노출하거나 숨기고 싶다면 실행 전에 `export CUDA_VISIBLE_DEVICES=0` 과 같이 설정할 수 있습니다.
4. **Docker/가상환경 권한**: 컨테이너나 가상 환경에서는 GPU 패스스루 옵션이 필요할 수 있습니다. Docker라면 `--gpus all` 옵션을 사용해 실행했는지 확인하세요.

> GPU가 없는 환경에서는 자동으로 CPU 모드로 실행됩니다.
