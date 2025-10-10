## 다운로드 utility
- gemma3 27b 다운로드 성공 (as of 2025.10.9)

## 동작하는 다운로드 모듈
https://github.com/jihyee0e/download_huggingface/blob/master/huggingface/download_models.py

## 사용 방법
1. 같은 디렉터리에 Hugging Face 액세스 토큰을 포함한 `nocommit.ini` 파일을 준비합니다.
2. 원하는 모델 저장 경로를 인자로 전달하여 스크립트를 실행합니다.

```bash
python llm_download.py /path/to/local_model_path
```

- 명령의 첫 번째 인자(`/path/to/local_model_path`)가 `LOCAL_MODEL_PATH`로 사용되며, 모델 파일이 해당 경로에 저장됩니다.
