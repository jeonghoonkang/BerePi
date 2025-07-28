# 🦙 Llama Q&A 서비스

Streamlit을 사용한 Llama 모델 기반 Q&A 서비스입니다. 애플 실리콘 GPU 지원을 포함합니다.

## 🚀 기능

- **다양한 Llama 모델 지원**: 7B, 13B, 70B 모델 선택 가능
- **애플 실리콘 GPU 가속**: MPS 백엔드를 통한 GPU 가속
- **실시간 채팅 인터페이스**: Streamlit 채팅 UI
- **모델 파라미터 조정**: Temperature, Top-p 등 조정 가능
- **자동 모델 다운로드**: Hugging Face에서 자동 다운로드
- **채팅 히스토리**: 대화 기록 유지

## 📋 요구사항

- Python 3.8+
- PyTorch 2.0+
- Apple Silicon Mac (MPS 가속용) 또는 CUDA GPU

## 🛠️ 설치

1. **의존성 설치**:
```bash
pip install -r requirements.txt
```

2. **Hugging Face 토큰 설정** (선택사항):
```bash
export HUGGING_FACE_HUB_TOKEN=your_token_here
```

## 🎯 사용법

1. **앱 실행**:
```bash
streamlit run app.py
```

2. **모델 선택**: 사이드바에서 원하는 Llama 모델 선택
3. **파라미터 조정**: Temperature, Top-p 등 조정
4. **질문 입력**: 채팅창에 질문 입력
5. **답변 확인**: Llama가 생성한 답변 확인

## 🔧 설정 옵션

### 모델 선택
- `meta-llama/Llama-2-7b-chat-hf`: 7B 파라미터 모델 (빠름)
- `meta-llama/Llama-2-13b-chat-hf`: 13B 파라미터 모델 (균형)
- `meta-llama/Llama-2-70b-chat-hf`: 70B 파라미터 모델 (정확함)
- `NousResearch/Llama-2-7b-chat-hf`: Nous Research 7B 모델
- `NousResearch/Llama-2-13b-chat-hf`: Nous Research 13B 모델

### 생성 파라미터
- **최대 길이**: 생성할 텍스트의 최대 토큰 수
- **Temperature**: 창의성 조절 (낮을수록 일관됨)
- **Top-p**: 토큰 선택 다양성 조절
- **샘플링 사용**: 확률적 샘플링 활성화

## 🖥️ 하드웨어 지원

### Apple Silicon Mac
- MPS 백엔드를 통한 자동 GPU 가속
- 메모리 효율적인 모델 로딩

### CUDA GPU
- NVIDIA GPU 지원
- 메모리 사용량 표시

### CPU
- GPU가 없는 경우 CPU 사용

## 📝 주의사항

1. **메모리 요구사항**:
   - 7B 모델: 최소 8GB RAM
   - 13B 모델: 최소 16GB RAM
   - 70B 모델: 최소 32GB RAM

2. **첫 실행 시**: 모델 다운로드에 시간이 걸릴 수 있습니다

3. **Hugging Face 접근**: 일부 모델은 Hugging Face 계정과 토큰이 필요할 수 있습니다

## 🔍 문제 해결

### 모델 다운로드 오류
```bash
# Hugging Face 토큰 설정
huggingface-cli login
```

### 메모리 부족 오류
- 더 작은 모델 선택
- CPU 사용으로 전환

### MPS 오류
- PyTorch 버전 확인 (1.12+ 필요)
- macOS 버전 확인 (12.3+ 필요)

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 