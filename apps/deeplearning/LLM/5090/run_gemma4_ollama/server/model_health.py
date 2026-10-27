"""Hourly inference checks of models loaded in the local Ollama backend."""
import copy
import threading
import time


class ModelHealthMonitor:
    PROMPT = "다른 문자 없이 ok만 회신"

    def __init__(self, request, interval=3600):
        self.request = request
        self.interval = interval
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._state = dict(status="waiting", active_count=0, working_count=0,
                           results=[], checked_at=None, next_check_at=None, error="")

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._state)

    def _update(self, **values):
        with self._lock:
            self._state.update(values)

    def check_once(self):
        if not self._run_lock.acquire(blocking=False):
            return
        started = time.time()
        try:
            self._update(status="checking", error="", next_check_at=None)
            try:
                data = self.request("/api/ps", timeout=10)
                rows = data.get("models")
                if not isinstance(rows, list):
                    raise ValueError("Invalid Ollama active model list")
                names = list(dict.fromkeys(row.get("name") or row.get("model") for row in rows))
                if any(not isinstance(name, str) or not name for name in names):
                    raise ValueError("Invalid active model name")
            except Exception as exc:
                self._update(status="error", error=str(exc))
                return
            results = [dict(model=name, status="pending", response="", error="") for name in names]
            self._update(active_count=len(names), working_count=0, results=copy.deepcopy(results),
                         checked_at=None)
            for result in results:
                if self._stop.is_set():
                    return
                result["status"] = "checking"
                self._update(results=copy.deepcopy(results))
                try:
                    reply = self.request("/api/generate", payload={
                        "model": result["model"], "prompt": self.PROMPT,
                        "stream": False, "think": False,
                        "options": {"temperature": 0, "num_predict": 16},
                    }, timeout=60)
                    response = reply.get("response")
                    valid = (isinstance(response, str) and response.strip() == "ok"
                             and reply.get("done") is True and not reply.get("error"))
                    result.update(status="ok" if valid else "failed",
                                  response=str(response or "")[:256],
                                  error="" if valid else str(reply.get("error") or "Expected exact ok response"))
                except Exception as exc:
                    result.update(status="failed", error=str(exc))
                self._update(results=copy.deepcopy(results),
                             working_count=sum(item["status"] == "ok" for item in results))
            self._update(status="complete", checked_at=time.time())
        finally:
            self._update(next_check_at=max(started + self.interval, time.time()))
            self._run_lock.release()

    def _loop(self):
        while not self._stop.is_set():
            self.check_once()
            delay = max(0, (self.snapshot()["next_check_at"] or time.time()) - time.time())
            if self._stop.wait(delay):
                break

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="model-health", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
