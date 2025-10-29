# GPU 추론 벤치마크 실행 방법

`gpu_inference_benchmark.py` 스크립트는 CUDA GPU 사용 가능 여부를 자동으로 감지하고, 워밍업 이후 반복 추론을 수행하여 평균 지연 시간과 처리량을 계산합니다.

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

### 선택 옵션
- `--warmup-iters`: 타이머 측정을 시작하기 전 워밍업 반복 횟수 (기본값 20)
- `--benchmark-iters`: 실제 측정 반복 횟수 (기본값 100)
- `--half`: GPU 사용 시 float16(half precision)으로 추론 수행

### 예시
```bash
python gpu_inference_benchmark.py --batch-size 64 --benchmark-iters 200 --half
```

> GPU가 없는 환경에서는 자동으로 CPU 모드로 실행됩니다.
