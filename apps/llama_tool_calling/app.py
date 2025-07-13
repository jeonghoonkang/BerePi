import argparse
import json
import time
from typing import Any, Dict, List

from llama_cpp import Llama


# ----- Tool functions -----

def get_time() -> str:
    """Return the current system time as a string."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def calculate(expression: str) -> str:
    """Evaluate a simple Python expression and return the result."""
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as exc:
        return f"Error: {exc}"


TOOLS = {
    "get_time": get_time,
    "calculate": calculate,
}

FUNCTION_DEFS = [
    {
        "name": "get_time",
        "description": "현재 시간을 문자열로 반환합니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "calculate",
        "description": "주어진 수식을 계산합니다.",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
]


# ----- Main chat loop -----

def main() -> None:
    parser = argparse.ArgumentParser(description="Llama function calling demo")
    parser.add_argument("--model", required=True, help="Path to Llama gguf model")
    parser.add_argument(
        "--n_ctx", type=int, default=2048, help="Context window size"
    )
    args = parser.parse_args()

    llm = Llama(model_path=args.model, n_ctx=args.n_ctx)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    print("Type 'exit' to quit.")
    while True:
        user = input("User: ")
        if user.strip().lower() == "exit":
            break

        messages.append({"role": "user", "content": user})
        result = llm.create_chat_completion(
            messages=messages,
            functions=FUNCTION_DEFS,
            temperature=0.7,
        )
        message = result["choices"][0]["message"]

        # If the model requests a function call, execute it and respond again
        if "function_call" in message:
            name = message["function_call"]["name"]
            args_json = message["function_call"].get("arguments", "{}")
            try:
                func_args = json.loads(args_json)
            except json.JSONDecodeError:
                func_args = {}
            func = TOOLS.get(name)
            if func:
                output = func(**func_args)
                messages.append(
                    {"role": "function", "name": name, "content": output}
                )
                followup = llm.create_chat_completion(messages=messages)
                reply = followup["choices"][0]["message"]["content"]
            else:
                reply = f"Unknown function: {name}"
        else:
            reply = message.get("content", "")

        messages.append({"role": "assistant", "content": reply})
        print(f"Assistant: {reply}\n")


if __name__ == "__main__":
    main()
