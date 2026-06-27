# Motion Image Reliable Send Spec

이 문서는 `detection_5min.py`가 Motion 감지 사진을 모델 서버와 Telegram으로 전송할 때, 파일 유실을 줄이고 재시작 가능한 방식으로 처리하기 위한 동작 규격이다.

## 목적

- Motion 감지 사진을 모델 서버에 안정적으로 전송한다.
- 모델 서버, GPU, 네트워크, Telegram 장애가 있어도 미처리 사진을 로컬에 보존한다.
- 같은 사진을 중복 queue에 넣지 않고, 처리 완료된 사진만 queue에서 제거한다.
- cron으로 반복 실행되어도 이전 실행의 미처리분을 이어 처리한다.

## 관련 파일

- 실행 스크립트: `detection_5min.py`
- 설정 파일: `conf_connect_model.conf`
- 로컬 pending queue: `pending_model_images`
- 로컬 skipped queue: `motion_skiped`
- 이벤트 로그: `logs/person_detected_events.jsonl`
- 최근 파일 수 로그: `logs/motion_recent_file_counts.jsonl`
- 실행 lock: `detection_5min.lock`

`pending_dir`, `skipped_dir`, 로그 경로가 상대 경로이면 `conf_connect_model.conf`가 있는 디렉터리를 기준으로 해석한다.

## Queue 개념

### Local pending queue

`pending_model_images`는 모델 서버로 전송 예정인 사진 파일을 저장하는 로컬 디스크 queue이다.

- queue 항목은 메모리가 아니라 파일이다.
- 프로세스가 중단되어도 queue 파일은 유지된다.
- 다음 실행에서 남은 queue 파일을 다시 읽어 처리한다.
- 기본 최대 저장 수는 `max_pending_files = 200`이다.

### Local skipped queue

`motion_skiped`는 현재 실행과 겹쳐 처리하지 못한 이미지 또는 pending queue 여유가 없어 뒤로 미룬 이미지를 보관하는 로컬 디스크 queue이다.

- 다음 실행에서 GPU가 idle이고 pending queue에 여유가 있으면 pending queue로 이동한다.
- skipped queue는 pending queue와 합쳐 전체 미처리 이미지 수로 계산한다.

### Model server queue

모델 서버 queue는 이미지 파일 자체를 보관하는 queue가 아니다. `detection_5min.py`는 pending 파일을 읽어 base64로 변환한 뒤 모델 서버에 POST하고, 응답으로 받은 `prompt_queue_id`를 사용해 결과를 polling한다.

## 설정 로딩 규격

설정은 실행 시작 시 `conf_connect_model.conf`에서 한 번 읽는다.

```ini
[model]
server_url = http://127.0.0.1:8082
endpoint_url =
result_url =
status_url =
model_name = gemma4:31b
user_id =
user_pw =
timeout_seconds = 600
poll_interval_seconds = 1.0
auto_parallel_requests = true
max_parallel_requests = 4
```

- `endpoint_url`이 비어 있으면 `{server_url}/api/enqueue-generate`를 사용한다.
- `result_url`이 비어 있으면 `{server_url}/api/prompt-result`를 사용한다.
- `status_url`이 비어 있으면 `{server_url}/api/status`를 사용한다.
- 실행 중 설정 파일을 변경해도 현재 프로세스에는 반영되지 않는다.
- 변경된 서버 URL은 다음 실행 또는 프로세스 재시작부터 적용된다.

## 전송 흐름

1. `motion_dir`에서 최근 `lookback_minutes` 이내의 이미지 파일을 찾는다.
2. 각 이미지에 대해 파일 경로, mtime, 크기 기반의 고유 pending 파일명을 만든다.
3. 이미 pending queue에 같은 항목이 있으면 중복 enqueue하지 않는다.
4. pending queue 여유가 있으면 `shutil.copy2()`로 사진을 `pending_model_images`에 복사한다.
5. pending queue 파일 목록을 오래된 순서로 정렬한다.
6. 모델 서버 `status_url`(`/api/status`)을 조회해 사용 가능한 모델/GPU/worker 용량을 확인한다.
7. 확인된 용량과 `max_parallel_requests` 중 작은 값만큼 병렬 worker를 만든다. 상태 확인 실패 또는 용량 확인 불가 시 worker 1개로 처리한다.
8. 각 pending 파일을 읽어 base64로 인코딩하고 모델 서버 `endpoint_url`에 JSON으로 POST한다.
9. 응답에서 `prompt_queue_id`를 받는다.
10. `result_url?id={prompt_queue_id}`를 주기적으로 GET polling한다.
11. 모델 결과를 파싱해 사람 감지 여부와 인원수를 판단한다.
12. 처리 완료된 pending 파일을 삭제한다.

모델 서버 POST payload 형식:

```json
{
  "model": "gemma4:31b",
  "prompt": "...",
  "images": ["<base64 image>"],
  "stream": false
}
```

모델 서버 enqueue 응답은 반드시 `prompt_queue_id`를 포함해야 한다.

```json
{
  "prompt_queue_id": 123
}
```

모델 서버 결과 조회 응답은 `done` 값을 포함해야 한다.

```json
{
  "done": true,
  "response": "{\"person_detected\": true, \"person_count\": 1}"
}
```

## 삭제 규격

pending queue 파일은 아래 조건에서만 삭제한다.

- 모델 판정이 완료되고 사람이 감지되지 않은 경우
- 모델 판정이 완료되고 사람 감지 이벤트를 로그/Telegram 처리한 경우
- Telegram 사진 제한으로 텍스트 알림 queue에 반영한 경우
- 이미지 파일 자체를 읽을 수 없어 더 이상 처리할 수 없는 경우

아래 조건에서는 pending queue 파일을 삭제하지 않는다.

- 모델 서버 POST 실패
- 모델 서버 polling 실패
- 모델 서버 timeout
- 모델 응답 형식 오류
- GPU busy timeout
- 프로세스 강제 종료
- 장비 재부팅

따라서 모델/네트워크 장애로 처리하지 못한 사진은 다음 실행에서 재시도된다.

## 중복 방지 규격

pending 파일명은 다음 값으로 만든다.

- 원본 경로
- 원본 파일 mtime nanoseconds
- 원본 파일 크기
- 위 값을 SHA-1로 만든 digest

이 방식으로 같은 원본 파일이 여러 번 scan되어도 같은 pending 파일명을 갖는다. 이미 pending 파일이 있으면 새로 복사하지 않는다.

## 동시 실행 방지

`detection_5min.py`는 시작 시 `detection_5min.lock` 파일에 exclusive lock을 잡는다.

- lock 획득 성공: 정상 처리 진행
- lock 획득 실패: 다른 실행이 처리 중인 것으로 판단
- lock 실패 시 최근 이미지는 `motion_skiped`로 이동하고 현재 실행은 종료

이 규칙은 cron이 5분마다 실행될 때 이전 실행과 겹쳐 같은 이미지를 동시에 처리하는 일을 줄인다.

## GPU 대기 규격

`[gpu] enabled = true`이면 모델 서버 전송 전 `nvidia-smi`로 GPU 사용률을 확인한다.

- 이 검사는 모델 서버가 로컬(`localhost`, `127.0.0.1`)일 때만 적용한다.
- 원격 모델 서버이면 로컬 GPU 검사는 건너뛰고 `status_url`(`/api/status`)의 원격 GPU/worker 용량을 사용한다.
- GPU 사용률이 `max_utilization_percent` 이하이면 모델 전송을 시작한다.
- GPU가 busy이면 `poll_interval_seconds`마다 재확인한다.
- `wait_timeout_seconds`를 넘으면 해당 실행에서는 pending 파일을 유지하고 다음 실행으로 넘긴다.

GPU 상태 확인 실패는 busy로 간주한다.

## 장애 처리 규격

### 모델 서버 장애

모델 서버 요청 실패, timeout, 응답 오류가 발생하면:

- pending 파일은 유지한다.
- 오류 로그를 남긴다.
- 1시간 throttling 기준으로 Telegram 장애 알림을 보낼 수 있다.
- 다음 실행에서 다시 시도한다.

### Telegram 장애

Telegram 전송 실패가 발생하면:

- 현재 구현은 해당 pending 파일을 삭제한다.
- 모델 판정은 이미 끝난 것으로 취급한다.
- Telegram 재전송 queue는 별도로 보존하지 않는다.

따라서 “모델 전송 신뢰성”과 달리 Telegram 전송은 완전한 재시도 보장을 하지 않는다.

### 프로세스 중단

프로세스가 중단되면:

- pending queue 파일은 디스크에 남는다.
- skipped queue 파일도 디스크에 남는다.
- 다음 실행에서 남은 파일을 이어 처리한다.
- 단, 모델 서버에 이미 POST되어 서버 queue에 등록된 job의 결과를 기다리던 중 종료되면, 로컬 pending 파일이 남아 다음 실행에서 새 job으로 다시 POST될 수 있다.

## 운영 명령

queue 상태 확인:

```bash
cd /home/tinyos/devel_opment/BerePi/apps/camera/motion
python3 detection_5min.py --queue-status
```

dry-run 실행:

```bash
cd /home/tinyos/devel_opment/BerePi/apps/camera/motion
python3 detection_5min.py --dry-run
```

cron 라인 출력:

```bash
cd /home/tinyos/devel_opment/BerePi/apps/camera/motion
python3 detection_5min.py --print-crontab
```

특정 실행에서 처리할 최대 pending 이미지 수 제한:

```bash
python3 detection_5min.py --max-batch-images 10
```

## 운영 확인 항목

- `pending_model_images` 파일 수가 계속 증가하면 모델 서버, GPU, timeout 설정을 확인한다.
- `motion_skiped` 파일 수가 증가하면 실행 시간이 cron 주기보다 긴지 확인한다.
- `logs/detection_5min.log`에서 `model request failed`, `gpu busy timeout`, `pending queue full` 메시지를 확인한다.
- `logs/motion_recent_file_counts.jsonl`에서 최근 이미지 수와 pending 수 추이를 확인한다.
- 모델 서버 URL 변경 후에는 현재 실행이 끝났는지 확인하고 다음 실행부터 적용 여부를 확인한다.

## 현재 보장 수준

| 항목 | 보장 수준 |
| --- | --- |
| 프로세스 재시작 후 pending 이미지 보존 | 보장 |
| 모델 서버 장애 시 이미지 보존 | 보장 |
| GPU busy 시 이미지 보존 | 보장 |
| 같은 이미지 pending 중복 방지 | 보장 |
| cron 중복 실행 방지 | lock 기반 보장 |
| 모델 서버에 등록된 job의 exactly-once 처리 | 미보장 |
| Telegram 전송 실패 시 사진 재전송 | 미보장 |
| 설정 파일 변경의 실행 중 hot reload | 미보장 |

## 개선 후보

- Telegram 전송 실패 파일을 별도 `telegram_pending` queue로 보존한다.
- 모델 서버 POST 후 받은 `prompt_queue_id`를 로컬 metadata 파일에 저장해 프로세스 재시작 후 polling을 재개한다.
- pending 이미지마다 상태 파일을 두어 `pending`, `posted`, `detected`, `telegram_sent` 단계를 명확히 기록한다.
- queue 파일 정리 정책을 추가해 너무 오래된 pending/skipped 파일을 운영자가 확인 후 archive 또는 삭제할 수 있게 한다.
