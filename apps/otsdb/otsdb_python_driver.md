##### OpenTSDB driver functions
  - Class TSDB
    - init
      - Time period
      - Metric name

    - read
      - Just read of TSDB
      - It returns String but we have to change it to dictionary format
      - Read specific metric
      - Return metric name which has been read by funcion (dictionary)

    - write
      - Jsut write
      - Write specific metric
      - Return metric name which has been written by funcion (dictionary)
