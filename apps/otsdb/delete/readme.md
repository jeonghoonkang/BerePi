
- tsdb {sub command} 사용 방법

- 데이터 검색, 삭제 방법
  - scan [--delete|--import] START-DATE [END-DATE] query [queries...]
    - tsdb scan --delete 1970/01/01-00:00:00 sum temperatures
    - tsdb scan --delete 1970/01/01-00:00:00 sum meterreadings
    - time sudo tsdb scan 2014/01/01-00:00:00 2017/06/01-00:10:00 none HanuriTN_00test

- <code> sudo tsdb uid grep metrics . </code>
  - 모든 메트릭 이름 검색
  - 스펠링포함 검색 sudo tsdb uid grep metrics 'Han*'

- 메트릭 이름만 삭제, 데이터는 안 지워짐
  - sudo tsdb uid delete metrics {metric name}
