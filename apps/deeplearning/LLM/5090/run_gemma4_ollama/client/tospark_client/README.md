# To Spark Client

Static web client for sending an OpenAI-compatible chat completion request to:

```text
http://10.0.0.17:26000/v1/chat/completions
```

Run the local proxy server:

```bash
python3 serve.py
```

Then open:

```text
http://127.0.0.1:8091
```

Edit the endpoint/model/message if needed, and press `Send`.

You can also open `index.html` directly. If the browser blocks the direct request because the target server does not allow CORS, use `serve.py` or press `Copy curl` and run the generated command from a terminal.
