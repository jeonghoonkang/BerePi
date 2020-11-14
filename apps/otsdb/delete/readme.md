
- tsdb {sub command}

- scan [--delete|--import] START-DATE [END-DATE] query [queries...]
  - tsdb scan --delete 1970/01/01-00:00:00 sum temperatures
  - tsdb scan --delete 1970/01/01-00:00:00 sum meterreadings

- <code> sudo tsdb uid grep metrics . </code>
  - sudo tsdb uid grep metrics 'Han*'

- sudo tsdb uid delete metrics {metric name}
