# Gemma 4 31B를 활용한 Ansible 자동화 확장 안내서

> 이 문서는 [pre_readme.md](./pre_readme.md)의 Ansible 기본 개념을 전제로, 로컬 LLM `gemma4:31b`를 결합해 구현할 수 있는 기능과 안전한 운영 방식을 정리한다. 2026-09-12에 `pre_readme.md` 전체를 로컬 Ollama의 `gemma4:31b` 모델에 입력해 받은 제안을 검토·확장하여 작성했다.

## 1. 목표와 핵심 원칙

Gemma 4 31B는 Ansible의 실행 엔진을 대체하지 않는다. 자연어 요구사항, 내부 운영 문서, 점검 결과와 오류 로그를 해석해 **계획·코드 후보·진단 설명을 제안하는 보조자**로 사용한다. 실제 변경은 결정론적인 검증기와 권한이 분리된 Ansible 실행기가 수행한다.

핵심 운영 모델은 **LLM-Guided, Human-Verified**이다.

```text
자연어 요청/이벤트/로그
        |
        v
컨텍스트 수집·비밀 제거·RAG
        |
        v
Gemma 4 31B: 계획 또는 코드 후보 생성
        |
        v
JSON Schema + 정책 allowlist + 정적 검사
        |
        v
검증 환경 실행 + check/diff + 멱등성 검사
        |
        v
사람 승인 ---- 거부/수정 ---> 다시 제안
        |
        v
CI/AWX의 제한된 실행 자격 증명
        |
        v
결과 수집·요약·감사·피드백
```

반드시 지킬 경계는 다음과 같다.

- LLM은 프로덕션 변경을 직접 실행하거나 스스로 승인하지 않는다.
- 모델 응답은 명령이 아니라 검증 전의 **제안 artifact**로 취급한다.
- 실행 대상 inventory, host group, Collection, module, 인자와 권한은 코드 기반 정책으로 제한한다.
- Vault 평문, SSH 개인 키, API token, 사용자 개인정보와 원본 민감 로그는 모델 입력에 넣지 않는다.
- `ansible-lint`, `--syntax-check`, schema, allowlist, 검증 환경 테스트 중 하나라도 실패하면 자동 중단한다.
- 프로덕션 적용에는 사람 승인과 변경 이력을 남기며, `--limit` 또는 `serial`로 작은 범위부터 적용한다.

## 2. 자동화 가능한 기능

| 기능 | 입력 | LLM 출력 | 우선순위 | 자동 실행 수준 |
|---|---|---|---|---|
| 자연어 요구사항 구조화 | 변경 요청, 티켓 | 범위·위험·수락 기준 JSON | P0 | 제안만 자동 |
| Playbook/Role 초안 | 승인된 명세, 내부 표준 | YAML 후보와 필요한 변수 | P0 | 생성·검사 자동, 적용은 승인 필요 |
| 기존 코드 리뷰 | Playbook, Role, lint 결과 | 멱등성·보안·유지보수 개선안 | P0 | 읽기 전용 |
| 실패 로그 진단 | 비식별화된 실행 결과 | 원인 후보, 증거, 다음 점검 | P0 | 읽기 전용 |
| 실행 결과 요약 | recap, diff, 이벤트 | 영향 범위와 변경 요약 | P0 | 읽기 전용 |
| 내부 문서 RAG 질의 | 표준 Role, runbook, CMDB 사본 | 근거가 연결된 답변 | P1 | 읽기 전용 |
| 테스트 생성 | Role과 수락 기준 | Molecule/검증 task 후보 | P1 | 격리 환경만 자동 |
| 버전 전환 보조 | porting guide, deprecation | 변경 후보와 migration 계획 | P1 | PR 제안까지 |
| 인벤토리 질의 번역 | “서울 개발 웹 서버” | 허용된 group/host pattern 후보 | P1 | 조회만 자동 |
| Runbook 탐색 | 경보, 서비스 정보 | 적용 가능한 기존 Playbook 추천 | P1 | 추천만 자동 |
| 변경 PR 작성 | 검증된 후보와 보고서 | 코드 diff, 설명, 테스트 근거 | P2 | 초안 PR까지 |
| 이벤트 대응 | 모니터링 경보 | 진단 workflow 또는 복구안 | P2 | 진단 자동, 복구 승인 필요 |

### 2.1 자연어를 실행 명세로 변환

사용자의 “웹 서버에 nginx 설정을 배포해 줘” 같은 요청을 바로 YAML로 바꾸지 않는다. 먼저 대상, 원하는 상태, 금지 사항, 검증 방법, 롤백과 위험도를 포함한 중간 명세로 변환한다.

LLM이 추가 확인이 필요한 항목을 `questions`에 반환하도록 하면 모호한 요청이 곧바로 실행 코드가 되는 것을 막을 수 있다.

### 2.2 Playbook과 Role 초안 생성

승인된 명세와 조직 표준을 입력해 다음을 생성할 수 있다.

- FQCN을 사용하는 task 후보
- `defaults`, `vars`, `handlers`, `templates`로 분리된 Role 구조
- 변경이 있을 때만 동작하는 handler
- `validate`, `failed_when`, `changed_when`과 오류 처리 후보
- canary 적용을 위한 `serial`, tag, health check
- 배포 후 검증 및 복구 Playbook 후보

생성기는 `ansible.builtin.shell`과 `ansible.builtin.command`를 기본 금지하고, 전용 모듈로 표현할 수 없는 사유가 명시된 경우에만 검토 대상으로 허용하는 것이 좋다.

### 2.3 기존 Ansible 코드 리뷰

LLM은 정적 분석 결과와 diff를 함께 받아 다음 항목을 설명할 수 있다.

- 반복 실행 시 매번 `changed`가 발생할 가능성
- `state: latest`, 광범위한 host pattern, 과도한 `become` 사용
- 파일 권한 누락, `no_log` 또는 `diff: false` 필요 여부
- FQCN과 Collection 버전 미고정
- handler 대신 무조건 서비스를 재시작하는 task
- 변수 우선순위 충돌과 환경별 값의 잘못된 배치
- 복구 경로와 검증 task 누락

LLM 리뷰는 `ansible-lint`, YAML parser, schema 검사 결과를 대체하지 않고 사람이 이해할 수 있는 설명을 추가한다.

### 2.4 실행 실패와 로그 진단

Ansible event에서 task 이름, host의 비식별 별칭, return code, 표준화된 오류 범주와 앞뒤 몇 줄만 추출해 모델에 전달한다. 모델은 다음 형태로 응답한다.

- 가장 가능성 높은 원인과 신뢰도
- 판단에 사용한 로그 근거
- 안전한 읽기 전용 확인 명령
- 관련 내부 runbook 또는 공식 모듈 문서
- 재시도 가능 여부와 사람에게 전달할 항목

모델이 제안한 진단 명령도 allowlist를 거쳐야 하며, `curl | sh`, 임의 다운로드, 파일 삭제, 방화벽 해제 같은 동작은 거부한다.

### 2.5 RAG 기반 운영 지식 활용

다음 자료를 검색 색인으로 구성할 수 있다.

- 승인된 Role과 Playbook
- 변수 정의서와 서비스 소유권
- 운영 표준, 보안 기준, 장애 runbook
- Ansible 버전별 porting guide와 Collection 문서
- 과거 작업의 비식별화된 실패 원인과 해결 결과

검색 결과에는 문서 경로, 버전, 갱신일과 짧은 인용 범위를 붙인다. 모델은 검색되지 않은 정책을 추측하지 않고 `insufficient_context`를 반환할 수 있어야 한다. inventory 원본 전체, Vault 파일, 자격 증명은 RAG 색인에서 제외한다.

### 2.6 실행 결과와 변경 보고서 생성

AWX job event 또는 `ansible-playbook` JSON callback 결과를 기반으로 다음 보고서를 만들 수 있다.

- 성공·변경·실패·도달 불가 host 수
- 실제 변경된 task와 파일
- check 결과와 실제 결과 차이
- canary 단계별 health check 결과
- 승인된 계획과 실제 실행의 차이
- 롤백 여부와 후속 조치

수치와 host 목록은 원본 event에서 프로그램으로 계산하고, LLM은 계산된 사실의 설명만 담당하도록 한다.

## 3. 권장 구성요소와 책임 분리

| 구성요소 | 책임 | 가져서는 안 되는 권한 |
|---|---|---|
| 요청 API/UI | 사용자 인증, 요청 접수, 승인 상태 표시 | Ansible 실행 자격 증명 |
| Context builder | RAG 검색, 최소 컨텍스트 구성, 비밀·개인정보 제거 | 모델 출력 승인 권한 |
| Gemma 4 서비스 | 계획, 코드와 설명 후보 생성 | Vault, SSH key, 프로덕션 쓰기 권한 |
| Output validator | JSON Schema, YAML parse, 모듈·인자 allowlist 검사 | 예외를 임의 승인할 권한 |
| Test runner | lint, syntax, check, Molecule, 격리 실행 | 프로덕션 inventory 접근 |
| Approval service | 변경 diff와 증거 표시, 승인자 기록 | 코드 생성 또는 승인 우회 |
| CI/AWX runner | 승인된 commit과 inventory로 실행 | 모델 API가 부여하는 동적 권한 |
| Audit store | prompt hash, 모델·문서 버전, 검사·승인·실행 결과 보관 | 비밀 평문 저장 |

모델 API와 Ansible 실행기를 같은 프로세스나 같은 서비스 계정으로 운영하지 않는다. 네트워크 정책으로 모델 서비스에서 관리 노드의 SSH/WinRM 포트에 직접 접근하지 못하게 하는 것이 좋다.

## 4. 구조화 출력 계약

자유 형식 YAML을 즉시 실행하지 말고, 먼저 다음과 같은 JSON 계약으로 의도를 받는다.

```json
{
  "schema_version": "1.0",
  "request_id": "CHG-2026-0012",
  "status": "proposal",
  "summary": "web 그룹의 nginx 설정 후보를 배포한다",
  "scope": {
    "inventory_alias": "production",
    "host_patterns": ["web_canary"],
    "excluded_hosts": []
  },
  "risk": {
    "level": "medium",
    "reasons": ["service restart may be required"]
  },
  "operations": [
    {
      "module": "ansible.builtin.template",
      "args_profile": "nginx_main_config",
      "notify": ["Restart nginx"]
    }
  ],
  "validation": [
    "ansible-lint",
    "syntax-check",
    "check-diff-canary",
    "nginx-config-test",
    "idempotence-test"
  ],
  "rollback": "restore_previous_template_and_restart",
  "evidence_refs": ["standards/nginx.md#configuration"],
  "questions": [],
  "requires_human_approval": true
}
```

검증기는 다음을 프로그램 코드로 강제한다.

- `schema_version`, enum, 필수 필드와 최대 배열 길이
- `inventory_alias`와 `host_patterns`의 사전 등록 여부
- 허용 Collection 및 FQCN 목록
- 허용된 인자 profile만 사용하고 임의 shell 문자열은 거부
- 프로덕션 요청의 `requires_human_approval: true`
- 위험도별 필수 검사, 승인자 수, canary와 rollback 규칙
- 근거 문서가 현재 버전이며 실제로 검색된 문서인지 확인

LLM이 module의 모든 인자를 자유롭게 만들도록 하기보다, 검토된 `args_profile`을 선택하게 하고 프로그램이 실제 task로 렌더링하면 공격 표면을 크게 줄일 수 있다.

## 5. 프롬프트 설계 예시

```text
[System]
당신은 Ansible 변경 계획 보조자다. 실행자가 아니다.
반드시 제공된 JSON Schema만 출력한다.
검색 컨텍스트에 없는 host, 변수, module 또는 정책을 만들지 않는다.
비밀을 요청하거나 출력하지 않는다.
모호하거나 위험하면 status=needs_clarification과 questions를 반환한다.
프로덕션 변경은 requires_human_approval=true로 설정한다.

[Policy]
- inventories: development, staging, production
- allowed host patterns: web_canary, web, app_canary, app
- allowed modules: ansible.builtin.package, template, service, uri
- forbidden modules: ansible.builtin.shell, command, raw
- production max first batch: 1 host

[Retrieved context]
문서 ID와 필요한 짧은 내용만 제공한다.

[Request]
사용자가 제출한 변경 요청
```

프롬프트 안에 “이전 지침을 무시하라” 같은 문장이 검색 문서나 로그에서 발견돼도 지시로 취급하지 않도록, 외부 콘텐츠를 명확한 데이터 블록으로 구분한다. 최종 보안은 프롬프트가 아니라 출력 검증과 실행 권한 분리가 담당한다.

## 6. 로컬 Gemma 4 호출 예시

이 저장소에서 사용하는 기본 모델 식별자는 `gemma4:31b`이고 Ollama 기본 API는 `http://127.0.0.1:11434/api/generate`이다. 환경에 따라 보호된 프록시 또는 별도 포트를 사용한다.

```bash
export ANSIBLE_AGENT_LLM_URL="http://127.0.0.1:11434/api/generate"
export ANSIBLE_AGENT_LLM_MODEL="gemma4:31b"

jq -n \
  --arg model "$ANSIBLE_AGENT_LLM_MODEL" \
  --arg prompt "읽기 전용 Ansible 변경 계획을 JSON으로 제안하세요." \
  '{
    model: $model,
    stream: false,
    format: "json",
    prompt: $prompt,
    options: {temperature: 0.1}
  }' |
curl --fail --silent --show-error \
  "$ANSIBLE_AGENT_LLM_URL" \
  -H 'Content-Type: application/json' \
  --data-binary @-
```

실제 구현에서는 timeout, 최대 입력·출력 크기, 동시 요청 수, model digest, 재시도 횟수와 circuit breaker를 설정한다. 모델 서버를 외부에 직접 노출하지 말고 인증·TLS·접근 제어가 있는 gateway를 사용한다. 프롬프트 또는 응답 전문을 무조건 로그로 남기지 않는다.

## 7. 검증 및 승인 파이프라인

### 7.1 생성 직후 검사

1. 응답 크기와 UTF-8 형식을 확인한다.
2. Markdown code fence나 설명을 제거하려 하지 말고 JSON 단독 응답이 아니면 실패시킨다.
3. JSON parser와 고정된 JSON Schema로 검사한다.
4. host, module, role, Collection, tag, 변수 이름을 allowlist와 비교한다.
5. 금지 문자열과 고위험 작업을 탐지하되 문자열 검사만 보안 경계로 의존하지 않는다.
6. 승인된 renderer가 JSON을 임시 branch의 YAML 후보로 변환한다.

### 7.2 Ansible 검사

```bash
yamllint .
ansible-lint
ansible-playbook -i inventories/staging/hosts.yml playbooks/site.yml --syntax-check
ansible-playbook -i inventories/staging/hosts.yml playbooks/site.yml --list-hosts
ansible-playbook -i inventories/staging/hosts.yml playbooks/site.yml --check --diff
```

그다음 격리된 검증 환경에서 실제 적용과 검증을 수행하고, 동일 Playbook을 두 번째 실행했을 때 의도하지 않은 `changed`가 없는지 검사한다. `--check`를 지원하지 않는 module은 별도 통합 테스트가 필요하다.

### 7.3 사람 승인 화면에 표시할 내용

- 자연어 원요청과 구조화된 수락 기준
- 변경될 repository diff와 생성에 사용한 model/digest
- 대상 inventory 별칭과 host pattern, 첫 batch 크기
- lint, syntax, check, 실제 검증 환경 및 멱등성 결과
- 설정 파일의 before/after diff에서 비밀을 제거한 결과
- 영향 서비스, 위험도, health check, 예상 중단 시간
- 롤백 절차와 이전 정상 artifact 식별자
- 근거 문서 경로와 버전

승인은 특정 commit SHA, inventory revision, Execution Environment image digest에 묶는다. 승인 뒤 코드나 대상이 바뀌면 승인을 무효화한다.

## 8. CI와 AWX 연동

### CI 기반 흐름

```text
변경 요청
 -> LLM 계획 JSON 생성
 -> schema/policy 검사
 -> 임시 branch에 코드 후보 생성
 -> lint/syntax/unit/Molecule
 -> staging 적용 및 idempotence
 -> PR + 검사 증거
 -> CODEOWNERS 승인
 -> 승인된 commit만 배포 workflow가 사용
```

LLM 서비스에는 Git 쓰기 권한을 직접 주지 않는다. 별도 bot이 검증된 diff만 임시 branch에 올리고, 보호 branch와 CODEOWNERS 규칙으로 병합을 통제한다.

### AWX Workflow Job Template 예시

1. **Survey/요청:** 사전 정의된 inventory, service, change window만 선택한다.
2. **Preflight:** inventory 동기화, 변수 schema, 대상 수와 maintenance window를 확인한다.
3. **Check:** check/diff job을 실행하고 결과를 비식별화한다.
4. **Approval:** 운영 승인자가 diff와 검사 증거를 확인한다.
5. **Canary:** 1대 또는 canary group에 제한 실행한다.
6. **Health gate:** 모니터링 또는 검증 Playbook이 성공해야 다음 단계로 이동한다.
7. **Rollout:** `serial` batch로 확대하고 실패 기준을 넘으면 중단한다.
8. **Report/Rollback:** 결과를 보고하고 필요하면 사전 승인된 rollback template을 별도 승인 후 실행한다.

LLM이 AWX credential ID, extra vars 또는 job template ID를 임의 생성하지 못하게 한다. 사용자가 이해하는 service 이름을 사전 등록된 template ID로 바꾸는 작업은 신뢰된 정책 서비스가 담당한다.

## 9. 보안 위협과 통제

| 위협 | 예시 | 필수 통제 |
|---|---|---|
| 환각 | 존재하지 않는 module/인자 생성 | FQCN 문서 조회, Collection 고정, schema와 syntax 검사 |
| 프롬프트 인젝션 | 로그나 README가 정책 무시를 지시 | 외부 콘텐츠를 데이터로 격리, 신뢰 등급, allowlist, 권한 분리 |
| 비밀 유출 | Vault 평문이나 token이 prompt/log에 포함 | 입력 전 탐지·마스킹, secret manager 분리, `no_log`, 보존 최소화 |
| 범위 확대 | `web_canary` 대신 `all`을 선택 | host pattern allowlist, 최대 대상 수, 승인 화면에 대상 고정 |
| 위험 명령 생성 | `rm`, `curl | sh`, 방화벽 해제 | shell/raw 기본 금지, 인자 profile, sandbox 검사 |
| 공급망 공격 | 악성 Collection 또는 바뀐 이미지 | 허용 registry, 서명/해시 검증, 버전·digest 고정 |
| 권한 혼합 | 모델이 SSH key와 승인 권한 보유 | 서비스 계정·네트워크·credential 완전 분리 |
| 데이터 오염 | 오래된 runbook이 검색됨 | 문서 소유자, 버전, 만료일, 출처와 freshness gate |
| 로그 위조 | 모델 요약 수치가 원본과 불일치 | 수치는 코드로 집계, 원본 event hash와 링크 제공 |
| 과도한 신뢰 | 자연스러운 설명 때문에 오류를 승인 | 검사 증거 우선 UI, 위험 변경 이중 승인, 정기 red-team 평가 |

## 10. 실패 처리 원칙

다음 조건에서는 자동으로 실행 단계에 진입하지 않는다.

- 모델 timeout, 빈 응답, JSON parse/schema 실패
- 근거 문서가 없거나 서로 충돌함
- 승인되지 않은 host pattern, Collection, module 또는 인자
- diff에 비밀 또는 예상 밖 파일이 나타남
- check와 검증 환경 결과가 다름
- 두 번째 실행에서도 불필요한 변경이 발생함
- canary health check 실패 또는 도달 불가 host 발생
- 승인 이후 commit, inventory 또는 image digest 변경

모델 장애 시 기존의 검증된 Playbook과 수동 runbook은 계속 사용할 수 있어야 한다. LLM을 필수 실행 의존성으로 만들지 않는 것이 중요하다.

## 11. 단계별 도입 로드맵

### 0단계: 기준선과 정책

- 기존 Playbook, inventory, Collection과 실행 경로를 목록화한다.
- 허용 모듈, 금지 동작, 위험 등급, 승인자, rollback 기준을 코드로 정의한다.
- 성공률, 작업 시간, 재실행 변경률과 장애 건수의 현재 기준값을 수집한다.

### 1단계: 읽기 전용 보조

- 문서 Q&A, 코드 설명, lint 결과 해석, 실패 로그 요약만 제공한다.
- 프로덕션 자격 증명과 네트워크 접근을 모델에서 완전히 차단한다.
- 답변 근거, 오답과 운영자 수정 내용을 평가 데이터로 축적한다.

### 2단계: 구조화된 계획 생성

- 자연어 요청을 JSON Schema에 맞는 변경 계획으로 변환한다.
- inventory/module allowlist와 정책 검사까지 자동화한다.
- 코드는 생성하지 않고 계획 품질과 질문 정확도를 측정한다.

### 3단계: 격리된 코드 및 테스트 생성

- 임시 branch에서 Playbook/Role과 테스트 후보를 생성한다.
- lint, syntax, Molecule, staging, 멱등성 검사를 CI에서 실행한다.
- 사람의 수정률이 충분히 낮아질 때까지 프로덕션 경로와 분리한다.

### 4단계: 승인 기반 canary 실행

- 보호 branch, 고정 artifact와 사람 승인을 거친 변경만 AWX로 전달한다.
- 한 호스트 canary, 자동 health gate와 중단 조건을 적용한다.
- rollback은 검증된 별도 workflow로 유지한다.

### 5단계: 제한적 이벤트 대응

- 반복적이며 영향이 작은 진단 workflow부터 event-triggered 방식으로 연결한다.
- 자동 복구는 충분한 성공 이력, 명확한 범위와 사전 승인 정책이 있는 항목에만 검토한다.
- 고위험 변경과 데이터 삭제는 항상 사람 승인을 유지한다.

## 12. 성공 지표

| 분류 | 지표 예시 |
|---|---|
| 정확성 | schema·lint·syntax 1차 통과율, 존재하지 않는 module/인자 생성률 |
| 코드 품질 | 검증 환경 성공률, 두 번째 실행 `changed=0` 비율, 사람 수정 라인 비율 |
| 안전성 | 정책 차단 건수, 승인 우회 0건, 비밀 노출 0건, rollback/사고율 |
| 진단 품질 | 원인 Top-3 포함률, 불필요한 재시도 감소율, 운영자 채택률 |
| 효율 | 요청에서 검증된 PR까지 걸린 시간, 평균 복구 시간, 반복 작업 절감 시간 |
| RAG 품질 | 근거 포함률, 오래된 문서 사용률, `insufficient_context`의 정확도 |
| 운영성 | 모델 timeout률, p95 응답 시간, 수동 fallback 성공률, 추론 자원 사용량 |

생성된 Playbook 수나 LLM 호출 수 자체를 성공 지표로 사용하지 않는다. 더 많은 자동 생성보다 검증 가능한 정확성, 변경 실패 감소와 운영 시간 절감이 중요하다.

## 13. 구현 체크리스트

- [ ] 모델 서비스와 Ansible 실행기의 계정·네트워크를 분리했다.
- [ ] 모델명뿐 아니라 model digest와 prompt/template 버전을 기록한다.
- [ ] 입력 전에 secret·개인정보·불필요한 로그를 제거한다.
- [ ] 신뢰된 문서만 RAG 색인하고 소유자·버전·만료일을 관리한다.
- [ ] JSON Schema와 host/module/argument allowlist가 있다.
- [ ] shell, command, raw는 기본 금지한다.
- [ ] Collection, Execution Environment와 dependency를 고정한다.
- [ ] lint, syntax, check, 실제 검증 환경, 멱등성 gate가 있다.
- [ ] 승인 내용을 commit·inventory·image digest에 묶는다.
- [ ] canary, health gate, 자동 중단과 검증된 rollback이 있다.
- [ ] 원본 event 수치는 코드로 계산하고 LLM은 설명만 한다.
- [ ] prompt/response 감사 정책과 보존 기간을 정했다.
- [ ] 모델 장애 시 기존 Playbook을 사용할 수 있는 fallback이 있다.
- [ ] 오답, 차단, 수정 결과를 정기적으로 평가한다.

## 14. 결론

Gemma 4 31B와 Ansible을 결합할 때 가장 가치 있는 자동화는 자연어를 곧바로 실행하는 것이 아니다. 운영 지식을 찾아 요구사항을 구조화하고, Playbook과 테스트 후보를 만들며, 실패 원인과 diff를 사람이 이해하기 쉽게 설명하는 과정이다.

LLM은 설계·진단 보조자, schema와 정책 엔진은 경계 검사자, Ansible은 결정론적 실행자, 사람은 최종 승인자라는 책임 분리를 유지해야 한다. 이 구조에서 읽기 전용 기능부터 시작해 검증된 변경만 단계적으로 실행 범위에 포함하면 생산성을 높이면서도 Ansible의 재현성과 운영 통제를 유지할 수 있다.
