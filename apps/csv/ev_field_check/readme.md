# apps/csv/ev_field_check 실행 방법

CSV 필드를 확인하고 그래프를 그리거나 필요한 컬럼만 추출할 수 있는 CLI 스크립트가 `apps/csv/ev_field_check/run.py` 에 있습니다.
실행 전에 pandas와 matplotlib를 설치합니다.

```bash
pip install pandas matplotlib
```

주요 사용 예시는 아래와 같습니다 (리포지토리 루트 기준 경로 사용).

- 필드만 확인 (콘솔 출력 + `*_fields.txt` 저장)

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --list-only
  ```

- 시간 컬럼과 여러 수치 컬럼 그래프 그리기

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --time-field time --value-fields voltage current
  ```

- 여러 CSV 파일의 필드를 통합 확인하기

  ```bash
  python apps/csv/ev_field_check/run.py --multi-file a.csv b.csv --list-only
  ```

- CSV 요약 정보 확인하기 (행 수, 필드 수, 시간 컬럼 표시 포함)

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --details --time-field time
  ```

- 선택한 컬럼만 추출하여 새 CSV 생성하기

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --extract time voltage current
  ```

  - 기본 저장 파일명: `sample_extracted.csv` (여러 파일을 합치면 `a_combined_extracted.csv`)

- 추출 시 숫자가 아닌 값이 섞인 컬럼을 제외하기

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --extract voltage current --drop-non-numeric
  ```

  - 제외된 컬럼은 콘솔에 안내 메시지로 표시됩니다.

- 숫자가 아닌 값이 있는 컬럼과 샘플 값 확인하기

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --drop-non-numeric-list
  ```

  - 각 컬럼의 앞쪽 5개, 마지막 5개 값이 함께 출력됩니다.

- 특정 컬럼 값 분포(고유 값+건수) 확인하기

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --value-counts status mode
  ```

- 선택한 컬럼을 새 이름으로 저장하며 추출하기

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --extract time voltage --extract-output filtered.csv
  ```

- 조건을 추가해 필요한 컬럼만 추출하기 (예: status가 OK이고 temp > 30)

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --extract time temp status \
    --extract-filter "status=OK" --extract-filter "temp>30"
  ```

- `example_args.txt` 파일의 인자를 그대로 사용하여 실행하기

  ```bash
  python apps/csv/ev_field_check/run.py $(cat apps/csv/ev_field_check/example_args.txt)
  ```
  - `example_args.txt`에는 `sample.csv --time-field time --y-fields voltage current --normalize`가 줄바꿈 단위로 기록되어 있어, 위 명령으로 동일한 인자가 전달됩니다.

- 별도 플로팅 스크립트로 CSV 그리기 (`plot.py`)

  ```bash
  # 시간 컬럼(time)을 x축으로 하고 나머지 모든 컬럼을 y축으로 표시
  python apps/csv/ev_field_check/plot.py sample.csv --time-field time

  # y축 컬럼을 지정하고, 여러 컬럼을 첫 유효 값 기준으로 정규화하여 표시
  python apps/csv/ev_field_check/plot.py sample.csv --time-field time --y-fields voltage current --normalize

  # 비수치 데이터가 포함된 컬럼을 제외하고 그리기
  python apps/csv/ev_field_check/plot.py sample.csv --time-field time --drop-non-numeric

  # 비수치 제외와 정규화를 함께 사용할 때, Boolean 컬럼은 자동으로 0/1로 변환 후 플롯
  python apps/csv/ev_field_check/plot.py sample.csv --time-field time --y-fields flag_a flag_b --drop-non-numeric --normalize

  # 인자 파일(@args.txt)로부터 옵션을 읽어 실행 (파일 내 공백/줄바꿈 기준으로 인자 전달)
  python apps/csv/ev_field_check/plot.py @apps/csv/ev_field_check/example_args.txt
  ```
