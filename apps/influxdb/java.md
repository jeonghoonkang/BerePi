# InfluxDB를 Java로 연동

## 필요한 라이브러리
* [Google Core Libraries for Java](https://github.com/google/guava)
  * [JAR 다운로드](https://mvnrepository.com/artifact/com.google.guava/guava)
* [A modern I/O API for Java](https://github.com/square/okio)
  * [JAR 다운로드](https://mvnrepository.com/artifact/com.squareup.okio/okio)
* [An HTTP+HTTP/2 client for Android and Java applications](https://github.com/square/okhttp)
  * [JAR 다운로드](https://mvnrepository.com/artifact/com.squareup.okhttp3/okhttp)
* [Logging Interceptor](https://github.com/square/okhttp/tree/master/okhttp-logging-interceptor)
  * [JAR 다운로드](https://mvnrepository.com/artifact/com.squareup.okhttp3/logging-interceptor)
* [A modern JSON library for Android and Java](https://github.com/square/moshi)
  * [JAR 다운로드](https://mvnrepository.com/artifact/com.squareup.moshi/moshi)
* [Type-safe HTTP client for Android and Java by Square, Inc](https://github.com/square/retrofit)
  * [JAR 다운로드](https://mvnrepository.com/artifact/com.squareup.retrofit2/retrofit)
* [Converter](http://square.github.io/retrofit/)
  * [JAR 다운로드](https://mvnrepository.com/artifact/com.squareup.retrofit2/converter-moshi)
* [Java client for InfluxDB](https://github.com/influxdata/influxdb-java)
  * [JAR 다운로드](https://mvnrepository.com/artifact/org.influxdb/influxdb-java)

## [예제](TestInfluxDB.java)
### connect
* InfluxDBFactory.connect()를 호출
  * InfluxDB가 return됨
  * 연결이 안 되면 exception이 발생
### write
* 먼저 Point라는 구조체에 내용을 입력
  * Tag는 tag()로 입력
  * Field는 addField()로 입력
* InfluxDB.write()로 Point를 write
### query
* 먼저 Query라는 구조체에 InfluxQL 구문을 입력
* InfluxDB.query()를 호출
* QueryResult라는 구조체에 결과가 담겨 return됨
### close
* InfluxDB.close()

## 참고자료
* [API Client Libraries](https://docs.influxdata.com/influxdb/v1.2/tools/api_client_libraries/)
