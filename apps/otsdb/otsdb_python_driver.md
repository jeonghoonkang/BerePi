#### OpenTSDB driver functions
  - OpenTSDB
    - Time Series Database
    - http://opentsdb.net/
    - 복잡한 테이블, 스키마 기반의 데이터관리가 아닌, 파일타입의 순서가있는 측정 데이터 관리 DB
    - 데이터 연계, 다양한 종류 데이터 확산
    
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

    - Copy
      - read and write to different metric
 
