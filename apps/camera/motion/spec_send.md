1. `detection_5min.py`는 Motion 이미지 파일을 `pending_model_images` 큐에 보관한 뒤 LLM 서버로 순차 또는 병렬 전송한다.
2. LLM 서버 기본 주소는 `[model] server_url`이며, 미지정 시 `http://127.0.0.1:8082`를 사용한다.
3. 전송 endpoint는 `[model] endpoint_url`이며, 미지정 시 `{server_url}/api/enqueue-generate`로 POST 요청한다.
4. 결과 조회 endpoint는 `[model] result_url`이며, 미지정 시 `{server_url}/api/prompt-result?id={prompt_queue_id}`로 GET polling한다.
5. 상태 조회 endpoint는 `[model] status_url`이며, 미지정 시 `{server_url}/api/status`로 모델/큐 상태와 병렬 처리 가능량을 확인한다. 서버가 사용 가능한 모델/GPU/worker 수를 알려주면 그 수의 `capacity_usage_ratio`(기본 0.60)까지만 한 번에 전송한다.
6. POST payload는 JSON이며 `model`, `prompt`, `images`, `user_id`, `password` 필드를 포함한다.
7. `images` 필드는 이미지 파일을 읽어 base64 문자열로 인코딩한 배열이며, 현재 전송은 이미지 1장 단위로 수행한다.
8. LLM 서버 응답에서 `prompt_queue_id`를 받아야 정상 접수로 판단하고, `done=true`가 될 때까지 `poll_interval_seconds` 간격으로 조회한다.
9. 최종 응답의 `response`, `visible_response`, `answer` 중 사용 가능한 텍스트를 파싱해 사람 감지 여부와 인원 수를 판정한다.
10. 전송 실패, timeout, 응답 형식 오류가 발생하면 pending 이미지는 삭제하지 않고 다음 실행에서 재시도하며, 필요 시 Telegram 실패 알림을 보낸다.
