# Qwen Coder Tool 에 Python 코드 실행 기능 추가 방법

이 문서는 `apps/deeplearning/LLM/5090/gemma/app.py` 기준으로, `qwen2.5-coder:7b` 와 `qwen3-coder:30b` 모델이 tool calling 으로 Python 코드를 작성하고 실행하도록 확장하는 방법을 설명합니다.

현재 구조에서 `qwen coder` 모델은 이미 tool 사용 경로로 들어갑니다.

- tool 목록 정의: `FILE_TOOLS`
- tool 실행 분기: `execute_file_tool(...)`
- tool 사용 모델 판정: `model_supports_tools(...)`
- Ollama tool 호출 루프: `call_ollama(...)`

즉, Python 실행 기능을 붙이려면 아래 네 군데를 맞춰서 수정하면 됩니다.

## 1. 현재 동작 구조

현재 `qwen coder` 모델은 다음 흐름으로 동작합니다.

1. 사용자가 프롬프트를 입력합니다.
2. `model_supports_tools(...)` 가 `qwen2.5-coder:*`, `qwen3-coder:*` 인지 확인합니다.
3. 조건이 맞으면 `call_ollama(...)` 에서 `tools=FILE_TOOLS` 를 함께 `POST /api/chat` 로 보냅니다.
4. 모델이 tool call 을 반환하면 `execute_file_tool(...)` 이 실제 파일 작업을 수행합니다.
5. tool 결과를 다시 모델에 넣어서 최종 답변을 만듭니다.

따라서 Python 실행도 이 패턴에 맞춰 새 tool 하나를 추가하면 됩니다.

## 2. 추가할 기능 목표

권장 목표는 아래와 같습니다.

- 모델이 `workspace` 안에 `.py` 파일을 생성할 수 있어야 함
- 모델이 생성한 `.py` 파일을 실행할 수 있어야 함
- 실행 결과의 `stdout`, `stderr`, `exit code` 를 다시 모델에 돌려줄 수 있어야 함
- 실행 범위는 `workspace` 내부로 제한해야 함
- 실행 시간, 출력 길이, 파일 확장자 제한이 있어야 함

가장 단순하고 안정적인 방식은:

1. `write_file` 로 Python 파일 작성
2. `run_python` tool 로 실행
3. 필요하면 `read_file` 로 결과 확인

입니다.

## 3. FILE_TOOLS 에 run_python 추가

`FILE_TOOLS` 에 아래와 같은 tool 정의를 추가합니다.

```python
{
    "type": "function",
    "function": {
        "name": "run_python",
        "description": "Run a Python script inside the workspace directory and return stdout, stderr, and exit code.",
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative Python file path inside the workspace"
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional command line arguments",
                    "default": []
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Optional timeout in seconds",
                    "default": 30
                }
            }
        }
    }
}
```

이렇게 하면 `qwen coder` 모델은 `write_file` 과 `run_python` 을 조합해서 작업할 수 있습니다.

## 4. 실제 실행 함수 추가

`app.py` 안에 실제 실행 함수 하나를 추가합니다.

예시는 아래처럼 두는 것이 무난합니다.

```python
def run_workspace_python(relative_path: str, args: list[str] | None = None, timeout_seconds: int = 30) -> str:
    """Run a Python file inside the workspace and return execution details."""
    path = safe_workspace_path(relative_path)
    if not path.exists():
        raise FileNotFoundError(f"Python file not found: {relative_path}")
    if not path.is_file():
        raise IsADirectoryError(f"Path is not a file: {relative_path}")
    if path.suffix.lower() != ".py":
        raise ValueError(f"Only .py files can be executed: {relative_path}")

    normalized_args = [str(arg) for arg in (args or [])][:20]
    timeout_seconds = max(1, min(int(timeout_seconds), 120))

    result = subprocess.run(
        ["python3", str(path), *normalized_args],
        cwd=str(WORKSPACE_DIR),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )

    stdout_text = result.stdout[-4000:]
    stderr_text = result.stderr[-4000:]
    return (
        f"exit_code={result.returncode}\n"
        f"stdout:\n{stdout_text}\n"
        f"stderr:\n{stderr_text}"
    )
```

핵심 포인트는 다음과 같습니다.

- `safe_workspace_path(...)` 로 경로 탈출 방지
- `.py` 확장자 제한
- 실행 인자 개수 제한
- `timeout` 제한
- 출력 길이 제한
- `cwd` 를 `WORKSPACE_DIR` 로 고정

## 5. execute_file_tool 에 분기 추가

`execute_file_tool(...)` 에 아래 분기를 넣습니다.

```python
if name == "run_python":
    return run_workspace_python(
        relative_path=str(arguments["path"]),
        args=[str(arg) for arg in arguments.get("args", [])],
        timeout_seconds=int(arguments.get("timeout_seconds", 30)),
    )
```

이제 모델이 `run_python` tool call 을 보내면 실제 실행이 됩니다.

## 6. model_supports_tools 는 그대로 사용 가능

현재 `model_supports_tools(...)` 는 아래 모델만 tool 사용으로 보냅니다.

- `qwen2.5-coder:*`
- `qwen3-coder:*`

즉, `qwen coder` 용 기능만 추가할 목적이라면 이 함수는 그대로 두면 됩니다.

반대로 `gemma` 에도 Python tool 을 열고 싶다면 그때 `gemma3:*` 조건을 추가하면 됩니다. 하지만 일반적으로는 코드 실행 안정성 때문에 `qwen coder` 쪽에만 열어두는 편이 낫습니다.

## 7. 시스템 프롬프트 보강

현재 `call_ollama(...)` 안의 system message 는 tool 사용 가능 모델에게 대략 아래 의미만 전달합니다.

- workspace file tools 사용 가능
- 실제 성공하지 않은 작업을 했다고 주장하지 말 것

여기에 Python 실행 규칙을 더 명확히 넣는 것이 좋습니다. 예를 들면 아래 정도를 추가합니다.

```text
When solving coding tasks, prefer this sequence:
1. inspect files if needed
2. write or update a Python file in the workspace
3. run it with run_python
4. use the returned stdout/stderr to decide next steps
Do not claim code execution succeeded unless the run_python tool returned a successful result.
```

이 문장을 `allow_tools` 분기 안의 system content 에 추가하면 모델 행동이 더 안정적입니다.

## 8. 사용자 프롬프트 예시

tool 이 추가된 뒤에는 사용자가 아래처럼 직접 요청할 수 있습니다.

### 예시 1: 새 Python 파일 작성 후 실행

```text
workspace 안에 hello_qwen.py 파일을 만들고 실행해 주세요.
출력은 현재 Python 버전과 hello 메시지여야 합니다.
```

### 예시 2: CSV 처리 코드 생성 후 실행

```text
workspace/data.csv 를 읽어서 합계를 구하는 Python 코드를 작성하고 실행해 주세요.
필요하면 먼저 파일 목록을 확인하세요.
```

### 예시 3: 오류 수정 루프

```text
workspace/app.py 를 실행해서 오류를 확인하고, 수정 가능한 범위면 고친 뒤 다시 실행해 주세요.
```

이런 요청은 모델이 아래 순서로 수행하도록 유도합니다.

1. `list_files`
2. `read_file`
3. `write_file`
4. `run_python`
5. 필요하면 다시 `write_file`, `run_python`

## 9. 추천 프롬프트 패턴

사용자가 더 안정적으로 실행시키려면 프롬프트에 아래 제약을 같이 주는 것이 좋습니다.

```text
Python 파일은 workspace 내부에 저장하고, 실행 전에 파일명을 알려 주세요.
실행 후에는 exit code, stdout, stderr 를 요약해 주세요.
실패하면 한 번 더 수정 후 재실행해 주세요.
```

이 패턴은 tool calling 루프와 잘 맞습니다.

## 10. 안전장치 권장사항

Python 실행 tool 은 파일 읽기보다 위험도가 높기 때문에 아래 제한을 권장합니다.

- `.py` 파일만 실행
- `workspace` 밖 경로 금지
- 최대 실행 시간 제한
- 최대 출력 길이 제한
- 실행 인자 개수 제한
- 필요하면 특정 import 차단
- 필요하면 네트워크 사용 차단
- 필요하면 `venv` 또는 고정 Python 경로 사용

특히 장기적으로는 아래 둘 중 하나를 권장합니다.

1. `subprocess.run(["python3", ...])` 기반의 단순 실행
2. 별도 샌드박스 프로세스 또는 컨테이너 안에서 실행

처음에는 1번으로 시작하고, 필요하면 2번으로 강화하는 편이 현실적입니다.

## 11. 최소 수정 체크리스트

아래 항목이 모두 들어가면 기본 기능은 완성됩니다.

- `FILE_TOOLS` 에 `run_python` 추가
- `run_workspace_python(...)` 함수 추가
- `execute_file_tool(...)` 에 `run_python` 분기 추가
- `call_ollama(...)` system prompt 에 Python 실행 규칙 추가
- 필요하면 README 에 사용 예시 추가

## 12. 테스트 방법

구현 후에는 최소한 아래 시나리오를 확인해야 합니다.

1. `qwen2.5-coder:7b` 선택
2. `workspace` 안에 `hello.py` 생성 요청
3. 모델이 `write_file` 호출
4. 모델이 `run_python` 호출
5. 실행 결과가 최종 답변에 반영되는지 확인

예상 테스트 프롬프트:

```text
workspace 안에 hello.py 를 만들고 실행해 주세요.
내용은 "hello from qwen tool" 을 출력하는 Python 코드로 해 주세요.
실행 결과를 함께 알려 주세요.
```

## 13. 권장 구현 방향

실무적으로는 아래 순서가 가장 좋습니다.

1. 먼저 `qwen coder` 전용으로 `run_python` 추가
2. 안정화 후 `gemma` 에도 열지 여부 판단
3. 실제 사용 로그를 보고 timeout, 출력 길이, 재시도 규칙 조정

즉, 처음부터 모든 모델에 열기보다, 이미 tool calling 이 활성화된 `qwen coder` 경로에만 Python 실행 기능을 붙이는 것이 가장 안전합니다.
