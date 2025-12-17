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

- 선택한 컬럼만 추출하여 새 CSV 생성하기

  ```bash
  python apps/csv/ev_field_check/run.py sample.csv --extract time voltage current
  ```
