# Ansible 오픈소스 사전 안내서

> 이 문서는 Ansible을 도입하거나 처음 사용하는 개발자·인프라 운영자를 위한 사전 읽기 자료이다. 제품 구성, 핵심 특징, 기술 규격, 설치 및 기본 사용법과 운영 시 주의점을 한 문서에 정리한다. 내용은 2026-09-12에 Ansible 공식 문서를 기준으로 확인했다. 실제 도입 시에는 사용할 `ansible-core` 버전의 지원 표와 각 Collection 문서를 다시 확인한다.

## 1. Ansible이란?

Ansible은 서버, 네트워크 장비, 클라우드 자원과 애플리케이션의 상태를 코드로 정의하고 자동화하는 오픈소스 IT 자동화 도구이다. 제어 노드(Control node)에서 명령을 실행해 여러 관리 노드(Managed node)를 원격으로 구성한다.

대표 사용 사례는 다음과 같다.

- 운영체제와 패키지 설정을 원하는 상태로 유지하는 구성 관리
- 애플리케이션 배포와 롤링 업데이트
- 계정, 파일, 서비스, 보안 정책의 일괄 관리
- 클라우드·가상화·컨테이너·네트워크 자원의 프로비저닝
- 장애 대응, 점검, 백업 같은 반복 운영 절차의 오케스트레이션

Ansible 프로젝트에서 자주 혼동되는 구성은 다음과 같이 구분한다.

| 이름 | 의미 |
|---|---|
| `ansible-core` | 실행 엔진, CLI, Playbook 언어, 기본 제공 모듈·플러그인을 포함한 최소 런타임 |
| `ansible` | `ansible-core`에 커뮤니티가 선정한 여러 Collection을 함께 제공하는 확장 배포 패키지 |
| Ansible Collection | 모듈, 플러그인, 역할(Role), Playbook, 문서를 배포하는 버전 관리 단위 |
| Ansible Galaxy | Collection과 Role을 검색·배포하는 커뮤니티 서비스 및 CLI |
| AWX | 웹 UI, REST API, 작업 스케줄링, 자격 증명 및 권한 관리를 제공하는 오픈소스 자동화 플랫폼 |
| Red Hat Ansible Automation Platform | Red Hat이 지원하는 상용 엔터프라이즈 제품군. 오픈소스 Ansible 자체와 동일한 제품은 아님 |

`ansible-core` 저장소는 **GPL-3.0-or-later** 라이선스로 배포된다. 개별 Collection과 포함 파일은 서로 다른 오픈소스 라이선스를 사용할 수 있으므로 재배포 전 해당 Collection의 라이선스를 별도로 확인해야 한다.

## 2. 핵심 특징

### 에이전트리스 구조

대부분의 Linux/Unix 대상에는 상주 에이전트를 설치하지 않고 SSH로 접속한다. Windows는 주로 WinRM 또는 PSRP를 사용하며, 네트워크 장비와 클라우드 서비스는 전용 연결 및 API 플러그인을 사용한다. 제어 노드에도 별도 데이터베이스나 상주 데몬이 필수는 아니다.

### 선언적이며 읽기 쉬운 자동화

Playbook은 YAML로 작성하며 “패키지가 설치됨”, “서비스가 실행 중임”처럼 목표 상태를 기술한다. 많은 모듈은 현재 상태를 확인한 뒤 필요한 경우에만 변경한다.

단, **멱등성은 Ansible 전체가 무조건 보장하는 성질이 아니라 사용하는 모듈과 작성 방식에 달려 있다.** `command`, `shell`, 외부 API 호출처럼 임의 동작을 실행하는 작업에는 `creates`, `removes`, `changed_when` 또는 사전 조건 검사를 사용해 반복 실행 안전성을 직접 설계해야 한다.

### 재사용과 확장

- Role로 task, handler, template, file, variable을 재사용 가능한 단위로 구성한다.
- Collection으로 도메인별 자동화 콘텐츠와 플러그인을 배포한다.
- Python으로 사용자 정의 모듈과 플러그인을 개발할 수 있다.
- Jinja2 표현식과 템플릿으로 환경별 설정을 생성한다.
- 정적 인벤토리뿐 아니라 클라우드 등에서 대상을 조회하는 동적 인벤토리 플러그인을 지원한다.

### 오케스트레이션 기능

호스트 그룹, 조건문, 반복문, handler, tag, role, block, 오류 처리, 비동기 실행, 직렬 실행(`serial`)을 조합할 수 있다. 기본은 제어 노드가 작업을 대상에 밀어 넣는 push 방식이지만, `ansible-pull`을 이용한 pull 형태도 가능하다.

### 변경 전 검증

`--syntax-check`, `--check`, `--diff`, `--limit`, `--list-hosts`, `--list-tasks` 등을 제공한다. 다만 check mode는 시뮬레이션이며 모든 모듈이 지원하는 것은 아니므로 실제 검증 환경을 대체하지 않는다.

## 3. 동작 구조

```text
개발자/CI/AWX
      |
      v
제어 노드의 ansible-core
  |-- Inventory: 대상 호스트와 그룹
  |-- Playbook/Role: 원하는 상태와 실행 순서
  |-- Module/Plugin/Collection: 실제 기능
  |-- Variables/Vault: 환경 값과 암호화 데이터
      |
      +-- SSH/SFTP 또는 SCP ---> Linux/Unix 관리 노드
      +-- WinRM/PSRP ----------> Windows 관리 노드
      +-- API/전용 연결 -------> Cloud/Network/Service
```

일반적인 POSIX 대상 작업은 다음 순서로 진행된다.

1. 인벤토리와 변수, 설정을 읽고 대상 호스트를 결정한다.
2. SSH 등 선택된 connection plugin으로 접속한다.
3. 필요한 모듈 코드와 인자를 임시 전송해 실행한다.
4. JSON 형태의 실행 결과를 수집하고 화면 또는 callback plugin으로 출력한다.
5. 변경이 발생하고 `notify`된 경우 해당 play 구간 끝에서 handler를 실행한다.

## 4. 기술 규격

| 구분 | 규격 및 설명 |
|---|---|
| 구현 언어 | 제어 엔진과 다수 모듈이 Python 기반 |
| 자동화 문서 | YAML 형식의 Playbook, Jinja2 표현식·템플릿 |
| 인벤토리 | INI 또는 YAML 정적 파일, 실행 가능한 스크립트, 동적 inventory plugin |
| 기본 통신 | POSIX 계열은 일반적으로 SSH, Windows는 WinRM/PSRP, 장비·서비스는 API 또는 Collection별 연결 방식 |
| 대상 실행 | 일반적인 POSIX 모듈에는 대상 Python과 대화형 POSIX shell이 필요. `raw` 작업, 일부 네트워크 모듈 등은 예외 |
| 권한 상승 | `become` 추상화로 sudo, su 등 지원. 방식과 지원 범위는 플랫폼·플러그인별로 다름 |
| 데이터 교환 | 모듈 입력·결과는 주로 JSON 호환 데이터 구조 사용 |
| 설정 파일 | INI 계열의 `ansible.cfg` |
| 콘텐츠 주소 | FQCN(Fully Qualified Collection Name), 예: `ansible.builtin.copy` |
| 비밀 관리 | Ansible Vault로 변수·파일의 저장 상태(data at rest)를 암호화 |
| 병렬 처리 | fork 기반 병렬 실행, strategy plugin, `serial`, `throttle` 등으로 제어 |
| 확장 지점 | module, action, connection, callback, lookup, filter, inventory, strategy 등 plugin 체계 |
| 라이선스 | `ansible-core`: GNU GPL v3.0 or later. Collection은 각각 확인 필요 |

### 지원 환경

- **제어 노드:** Python이 설치된 Linux, macOS, BSD 등 대부분의 Unix 계열을 지원한다. Windows 자체는 네이티브 제어 노드로 지원하지 않으며 WSL을 사용한다.
- **POSIX 관리 노드:** Ansible 설치는 필요하지 않다. 일반적으로 SSH 접속 계정, 대화형 POSIX shell, 호환 Python이 필요하다.
- **Windows 관리 노드:** Windows용 모듈과 PowerShell remoting 구성을 사용한다. `ansible-core` 버전에 따라 지원 Windows/PowerShell 범위가 달라진다.
- **네트워크·어플라이언스:** 대상에 Python이 없어도 Collection의 network CLI, NETCONF, HTTPAPI 등의 연결 방식을 사용할 수 있다.

Python 지원 버전을 하나의 고정 숫자로 간주하면 안 된다. 공식 정책상 최근 `ansible-core`는 제어 노드의 최근 Python 릴리스 일부와 관리 노드의 더 넓은 Python 범위를 지원하며, 구체 범위는 릴리스마다 달라진다. 운영 표준을 정할 때 [공식 릴리스 및 지원 매트릭스](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html)를 기준으로 Ansible과 Python 버전을 함께 고정한다.

### 주요 파일과 데이터 모델

| 파일/디렉터리 | 역할 |
|---|---|
| `ansible.cfg` | 인벤토리 위치, 실행 옵션, plugin 경로 등 프로젝트 설정 |
| `inventory/` | 환경별 관리 노드, 그룹 및 inventory plugin 설정 |
| `group_vars/` | 그룹에 적용할 변수 |
| `host_vars/` | 개별 호스트에 적용할 변수 |
| `site.yml` | 전체 자동화의 진입점으로 흔히 사용하는 Playbook 이름 |
| `roles/<role>/tasks/main.yml` | Role이 수행할 기본 task |
| `roles/<role>/handlers/main.yml` | 변경 알림을 받는 handler |
| `roles/<role>/templates/` | Jinja2 템플릿 |
| `roles/<role>/files/` | 그대로 전송할 정적 파일 |
| `roles/<role>/defaults/main.yml` | 쉽게 덮어쓸 수 있는 낮은 우선순위 기본 변수 |
| `roles/<role>/vars/main.yml` | Role 내부의 높은 우선순위 변수 |
| `requirements.yml` | 필요한 Collection 또는 Role과 버전 정의 |

### 핵심 용어

- **Inventory:** 관리 대상 host와 group의 집합이다.
- **Playbook:** 하나 이상의 play를 순서대로 담은 YAML 자동화 문서이다.
- **Play:** 특정 host pattern에 적용할 변수, role, task 등을 묶는다.
- **Task:** 모듈 하나를 특정 인자로 호출하는 실행 단위이다.
- **Module:** 패키지, 파일, 사용자, 클라우드 자원 같은 대상을 실제로 조회·변경하는 기능이다.
- **Plugin:** 연결, 인벤토리, 값 조회, 출력, 실행 전략 등 엔진 동작을 확장한다.
- **Role:** 관련 task, handler, 변수, template, file을 표준 디렉터리 구조로 묶은 재사용 단위이다.
- **Handler:** 변경이 발생한 task에서 알림을 받아 필요할 때만 실행되는 task이다.
- **Facts:** 관리 노드에서 수집한 운영체제, 주소, 하드웨어 등의 정보이다.
- **Collection:** `namespace.name`으로 식별되는 자동화 콘텐츠 배포 단위이다.

## 5. 빠른 시작

### 5.1 설치

Python 애플리케이션을 격리하는 `pipx` 설치 예시는 다음과 같다.

```bash
# 여러 커뮤니티 Collection이 포함된 전체 패키지
pipx install --include-deps ansible

# 또는 최소 실행 엔진만 설치
pipx install ansible-core

# 설치 확인: 이 명령은 연결된 ansible-core 버전을 표시한다.
ansible --version

# 전체 ansible 커뮤니티 패키지 버전 확인
ansible-community --version
```

가상환경에서 `pip`를 사용하는 방법도 가능하다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install ansible
ansible --version
```

시스템 Python에 전역 설치하기보다 프로젝트별 가상환경, `pipx` 또는 Execution Environment 컨테이너를 사용하고 버전을 고정하는 편이 재현성에 유리하다.

### 5.2 최소 프로젝트 만들기

```text
ansible-demo/
├── ansible.cfg
├── inventory.yml
└── site.yml
```

`ansible.cfg`:

```ini
[defaults]
inventory = ./inventory.yml
interpreter_python = auto_silent
host_key_checking = True
retry_files_enabled = False

[ssh_connection]
pipelining = True
```

`inventory.yml`:

```yaml
---
all:
  children:
    web:
      hosts:
        web01:
          ansible_host: 192.0.2.10
      vars:
        ansible_user: deploy
```

예시의 `192.0.2.10`은 문서용 주소이므로 실제 서버 주소로 바꾼다. 먼저 SSH 키 인증과 호스트 키 검증이 정상 동작하는지 확인한다.

```bash
ssh deploy@192.0.2.10
ansible-inventory --graph
ansible web -m ansible.builtin.ping
```

`ping` 모듈은 ICMP ping이 아니라 Ansible 접속과 대상 Python 실행 가능 여부를 확인한다.

### 5.3 첫 Playbook

`site.yml`:

```yaml
---
- name: Configure web servers
  hosts: web
  become: true
  gather_facts: true

  vars:
    web_package: nginx

  tasks:
    - name: Ensure web package is installed
      ansible.builtin.package:
        name: "{{ web_package }}"
        state: present

    - name: Ensure web service is enabled and running
      ansible.builtin.service:
        name: "{{ web_package }}"
        enabled: true
        state: started
```

실행 전 검사와 적용:

```bash
ansible-playbook site.yml --syntax-check
ansible-playbook site.yml --check --diff
ansible-playbook site.yml
```

`become: true`를 사용하려면 원격 계정에 적절한 권한 상승 정책이 있어야 한다. 암호 입력이 필요한 환경에서는 `--ask-become-pass`를 사용할 수 있지만 CI에서는 전용 자격 증명 관리 방식을 사용한다.

### 5.4 설정 파일 배포와 Handler

```yaml
---
- name: Configure nginx
  hosts: web
  become: true

  tasks:
    - name: Render nginx configuration
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: "0644"
        validate: "nginx -t -c %s"
      notify: Restart nginx

  handlers:
    - name: Restart nginx
      ansible.builtin.service:
        name: nginx
        state: restarted
```

template 내용이 바뀐 경우에만 handler가 통지되며, 일반적으로 play의 해당 구간이 끝날 때 한 번 실행된다. `mode`는 YAML 숫자 해석 문제를 피하도록 문자열로 작성한다.

### 5.5 자주 쓰는 명령

```bash
# 인벤토리 확인
ansible-inventory -i inventory.yml --graph
ansible-inventory -i inventory.yml --host web01

# 대상과 접속 확인
ansible all -i inventory.yml -m ansible.builtin.ping

# 일회성(ad hoc) 명령
ansible web -i inventory.yml -m ansible.builtin.command -a "uptime"

# 실행 대상·task 확인
ansible-playbook -i inventory.yml site.yml --list-hosts
ansible-playbook -i inventory.yml site.yml --list-tasks

# 일부 호스트/태그만 실행
ansible-playbook -i inventory.yml site.yml --limit web01
ansible-playbook -i inventory.yml site.yml --tags deploy

# 모듈 문서 확인
ansible-doc ansible.builtin.copy

# 현재 설정값과 출처 확인
ansible-config dump --only-changed
```

## 6. Collection과 Role 사용

외부 콘텐츠는 `requirements.yml`에 버전을 명시해 재현 가능하게 관리한다.

```yaml
---
collections:
  - name: community.general
    version: ">=10.0.0,<11.0.0"

roles:
  - name: geerlingguy.docker
    version: "7.4.7"
```

```bash
ansible-galaxy collection install -r requirements.yml
ansible-galaxy role install -r requirements.yml
ansible-galaxy collection list
```

예시 버전은 형식을 설명하기 위한 값이다. 실제 사용 전 호환 버전과 유지보수·라이선스·출처를 검토하고 lock 또는 Execution Environment 이미지로 고정한다. 모듈은 이름 충돌과 출처 혼동을 막기 위해 `copy`보다 `ansible.builtin.copy`처럼 FQCN으로 쓰는 것을 권장한다.

Role 기본 구조는 다음 명령으로 만들 수 있다.

```bash
ansible-galaxy role init roles/webserver
```

Playbook에서 호출하는 예:

```yaml
---
- name: Apply webserver role
  hosts: web
  become: true
  roles:
    - role: webserver
```

## 7. 변수와 환경 분리

권장 프로젝트 예시는 다음과 같다.

```text
.
├── ansible.cfg
├── requirements.yml
├── inventories/
│   ├── development/
│   │   ├── hosts.yml
│   │   └── group_vars/
│   └── production/
│       ├── hosts.yml
│       └── group_vars/
├── playbooks/
│   └── site.yml
└── roles/
```

```bash
ansible-playbook -i inventories/development/hosts.yml playbooks/site.yml
ansible-playbook -i inventories/production/hosts.yml playbooks/site.yml --limit web
```

변수는 inventory, `group_vars`, `host_vars`, role defaults/vars, play/task vars, extra vars 등 여러 위치에서 정의할 수 있으며 우선순위 규칙이 복잡하다. 같은 키를 여러 곳에서 재정의하기보다 다음 원칙을 지킨다.

- 변경 가능한 기본값은 `roles/<name>/defaults/main.yml`에 둔다.
- 환경 공통값은 `group_vars`에 둔다.
- 정말 호스트별인 값만 `host_vars`에 둔다.
- `--extra-vars`는 높은 우선순위가 의도된 배포 파라미터에 제한한다.
- `ansible-inventory --host <host>`와 `ansible-config dump --only-changed`로 최종 값을 확인한다.

## 8. 비밀 정보 관리

평문 암호, 개인 키, API 토큰을 Playbook이나 Git 저장소에 넣지 않는다. Ansible Vault는 파일 또는 변수를 암호화할 수 있다.

```bash
# 암호화된 변수 파일 생성
ansible-vault create inventories/production/group_vars/all/vault.yml

# 기존 파일 암호화/편집/조회
ansible-vault encrypt secrets.yml
ansible-vault edit secrets.yml
ansible-vault view secrets.yml

# 실행 시 암호 입력
ansible-playbook -i inventories/production/hosts.yml playbooks/site.yml \
  --ask-vault-pass
```

Vault는 **저장 중인 데이터만** 보호한다. 복호화된 값이 task 출력, diff, 오류 메시지, callback log에 노출될 수 있으므로 비밀을 다루는 task에는 필요에 따라 `no_log: true`와 `diff: false`를 적용한다. Vault 암호 자체는 저장소 밖의 secret manager나 CI 자격 증명 저장소에서 관리한다.

## 9. 안전한 운영 절차

프로덕션 적용 전 다음 순서를 권장한다.

1. `ansible-lint`와 YAML 검사 도구로 정적 검사한다.
2. `--syntax-check`, `--list-hosts`, `--list-tasks`로 대상과 구문을 확인한다.
3. 검증 환경에서 실제 실행하고 두 번째 실행의 `changed=0` 여부를 확인한다.
4. 지원 모듈에 한해 `--check --diff`를 사용한다. diff의 비밀 노출 여부도 확인한다.
5. 프로덕션의 한 호스트 또는 작은 그룹에 `--limit`과 `serial`로 canary 적용한다.
6. 실패 조건, 백업, 복구 Playbook과 관측 방법을 준비한 후 전체에 확대한다.

운영 품질을 높이는 작성 원칙은 다음과 같다.

- `shell`/`command`보다 상태를 이해하는 전용 모듈을 우선한다.
- task마다 결과가 드러나는 고유한 `name`을 작성한다.
- 모듈과 role/collection 버전을 고정하고 업그레이드 시 porting guide를 검토한다.
- `latest` 상태는 예기치 않은 업그레이드를 만들 수 있으므로 변경 정책이 명확할 때만 쓴다.
- SSH host key 검증을 단순 편의를 위해 끄지 않는다.
- `become` 범위와 원격 계정 권한을 최소화한다.
- 외부 Collection은 코드, 서명/출처, 유지보수 상태와 라이선스를 검토한다.
- 민감한 파일에는 소유자와 권한을 명시하고 log/diff 노출을 차단한다.
- 동시 변경이 위험한 서비스는 `serial`, `throttle`, `max_fail_percentage` 등을 설계한다.
- `ansible.cfg`를 신뢰할 수 없는 world-writable 디렉터리에서 사용하지 않는다.

## 10. 제약과 도입 판단

Ansible은 사람이 수행하던 순차적 운영 절차와 이기종 시스템 오케스트레이션에 특히 적합하다. 반면 다음 사항을 고려해야 한다.

- 대상 수, task 수, 네트워크 지연이 커지면 SSH 연결과 제어 노드 자원이 병목이 될 수 있다.
- 중앙 서버 없이 CLI만 사용할 경우 스케줄링, RBAC, 감사 이력, 자격 증명 위임은 별도 도구가 필요하다.
- YAML 자체는 단순하지만 변수 우선순위, include/import, plugin과 Collection 호환성은 규모가 커질수록 복잡해진다.
- 장시간 지속적으로 상태를 감시하는 에이전트형 시스템과 달리 기본 동작은 실행 시점에 상태를 적용한다.
- `--check` 결과가 실제 실행을 완전히 예측하지 않으며 외부 시스템 상태나 비멱등 task로 인해 결과가 달라질 수 있다.
- 대규모 환경에서는 동적 인벤토리, 실행 환경 컨테이너, 중앙 실행 플랫폼(AWX 등), observability 및 Git 기반 변경 절차를 함께 검토한다.

## 11. 문제 해결 요령

```bash
# 상세 로그. 접속 문제는 보통 -vvv 또는 -vvvv부터 확인
ansible web -m ansible.builtin.ping -vvvv

# 설정 파일, Python, 모듈 경로 확인
ansible --version

# 인벤토리가 의도대로 파싱되는지 확인
ansible-inventory -i inventory.yml --list

# 대상 Python을 못 찾을 때 실제 경로 지정 예
ansible web -m ansible.builtin.ping \
  -e ansible_python_interpreter=/usr/bin/python3
```

흔한 원인은 SSH 사용자/키/host key, `become` 권한, 방화벽, 대상 Python 경로, 잘못된 host pattern, 변수 우선순위, Collection 미설치 또는 버전 불일치이다. 오류가 난 task의 FQCN을 `ansible-doc`으로 조회해 해당 버전의 요구 사항과 반환값을 먼저 확인한다.

## 12. 공식 자료

- [Ansible Community Documentation](https://docs.ansible.com/projects/ansible/latest/)
- [Ansible 설치 가이드](https://docs.ansible.com/projects/ansible/latest/installation_guide/intro_installation.html)
- [Getting Started](https://docs.ansible.com/projects/ansible/latest/getting_started/index.html)
- [Playbook 사용 가이드](https://docs.ansible.com/projects/ansible/latest/playbook_guide/index.html)
- [Inventory 사용 가이드](https://docs.ansible.com/projects/ansible/latest/inventory_guide/index.html)
- [Collection 사용 가이드](https://docs.ansible.com/projects/ansible/latest/collections_guide/index.html)
- [Ansible Vault 가이드](https://docs.ansible.com/projects/ansible/latest/vault_guide/index.html)
- [릴리스·유지보수 및 Python 지원 매트릭스](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html)
- [ansible-core GitHub 저장소](https://github.com/ansible/ansible)
- [Ansible Galaxy](https://galaxy.ansible.com/)
- [AWX GitHub 저장소](https://github.com/ansible/awx)

---

요약하면 Ansible은 에이전트 설치 부담이 적고, 사람이 읽을 수 있는 YAML과 방대한 Collection 생태계를 이용해 다양한 시스템을 한 흐름으로 자동화할 수 있다는 장점이 있다. 안정적인 운영을 위해서는 멱등성 검증, 버전 고정, 최소 권한, 비밀 관리, 작은 범위부터의 단계적 적용을 함께 설계해야 한다.
