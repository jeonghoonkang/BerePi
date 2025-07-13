# Llama Tool Calling Example

이 예제는 `llama-cpp-python` 라이브러리를 사용하여 Llama 모델과 함수 호출 기능(Function Calling)을 연동하는 간단한 CLI 프로그램입니다. 
사용자는 대화 중에 명령을 내리면 LLM이 적절한 툴(함수)을 선택하여 실행하고, 그 결과를 바탕으로 다시 응답합니다.

## 필요 패키지

```bash
pip install llama-cpp-python
```

## 실행 방법

모델 경로를 지정하여 실행합니다. 예시 모델은 gguf 형식의 Llama 모델 파일입니다.

```bash
python app.py --model path/to/model.gguf
```

프로그램이 실행되면 프롬프트에 질문을 입력하고, "현재 시간 알려줘" 또는 "2+2 계산해"와 같이 명령을 내리면 툴이 실행됩니다.
