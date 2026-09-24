# Qwen으로 Q&A 데모

이 예제는 Alibaba의 Qwen 모델을 사용하여 간단한 질문/답변 데모를 실행하는 Streamlit 앱입니다.

## 사용 방법

1. 필요한 패키지 설치
   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
   환경 변수 `QWEN_MODEL`에 로컬 모델 경로 또는 HuggingFace 모델 이름을 지정할 수 있습니다.
2. 앱 실행
   ```bash
   bash run.sh
   ```

기본적으로 `Qwen/Qwen1.5-7B-Chat` 모델을 사용하며, 로컬에 모델이 없으면 다운로드합니다.
앱을 실행하면 화면 상단에 GPU 사용 가능 여부가 표시되고, 이어서 현재 GPU 메모리 사용량과
모델이 지원하는 최대 입력 토큰 수가 함께 보여집니다.
Apple Silicon에서는 FP16 모델을 `mps` 장치로 직접 옮겨 GPU를 사용합니다.
CUDA 또는 CPU 환경에서는 기존 `device_map="auto"` 배치를 사용합니다.
화면의 `모델 실행 장치: mps:0` 또는 `mps` 표시로 실제 모델 배치를 확인할 수 있습니다.

## Mac GPU 확인

이 폴더에서 실행합니다. `run.sh`는 작업 디렉터리를 이 폴더로 고정하므로
이미 내려받은 `Qwen/Qwen1.5-7B-Chat` 모델을 재사용합니다.

```bash
.venv/bin/python -c 'import torch; print("MPS:", torch.backends.mps.is_available()); x = torch.ones((64, 64), device="mps"); print((x @ x)[0, 0].item())'
bash run.sh
```

MPS가 `True`이고 연산 결과가 `64.0`이면 Apple GPU 연산이 가능합니다.
`False`이면 Apple Silicon용 Python과 PyTorch 설치 상태를 확인하세요.
이 앱의 GPU는 PyTorch MPS를 사용하며 Ollama 설치와는 독립적입니다.
2026-09-24 M4 Max에서 PyTorch 2.14.0으로 `MPS: True`, 행렬 연산 결과 `64.0`,
Qwen1.5-7B-Chat 모델의 `mps:0` 배치와 실제 텍스트 생성을 확인했습니다.
MPS 미지원 연산이 발생할 때만 `PYTORCH_ENABLE_MPS_FALLBACK=1 bash run.sh`로
해당 연산의 CPU 대체 실행을 시도할 수 있습니다.

근거: [PyTorch MPS 사용법](https://docs.pytorch.org/docs/stable/notes/mps.html).


### 오류 확인

모델 실행 중 문제가 발생하면 화면 하단에 오류 메시지와 함께 상세 내용을 볼 수 있는 창이 나타납니다.
