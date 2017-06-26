/**
 * File: TestInfluxDB.java
 *
 * Description:
 * TestInfluxDB class tests InfluxDB in Java.
 *
 * @author Sukun Kim <sukunkim@sinbinet.com>
 */

import java.util.concurrent.TimeUnit;

import org.influxdb.InfluxDB;
import org.influxdb.InfluxDBFactory;
import org.influxdb.dto.BatchPoints;
import org.influxdb.dto.Point;
import org.influxdb.dto.Pong;
import org.influxdb.dto.Query;
import org.influxdb.dto.QueryResult;


public class TestInfluxDB {

  public static final String HOST = "192.168.149.146";
  public static final int PORT = 8086;
  public static final String ID = "root";
  public static final String PW = "root";
  public static final String DB = "test";


  public TestInfluxDB() {
    InfluxDB influxDB
      = InfluxDBFactory.connect("http://" + HOST + ":" + PORT, ID, PW);


    Pong pong = influxDB.ping();
    System.out.println("pong = " + pong);

    String version = influxDB.version();
    System.out.println("version = " + version);


    Point point1 = Point.measurement("cpu")
      //.time(System.currentTimeMillis(), TimeUnit.MILLISECONDS)
      .tag("SensorId", "100")
      .addField("idle", 10L)
      .addField("user", 11L)
      .addField("system", 1L)
      .build();

    influxDB.write(DB, "autogen", point1);


    BatchPoints batchPoints = BatchPoints.database(DB).build();

    Point point2 = Point.measurement("cpu")
      //.time(System.currentTimeMillis(), TimeUnit.MILLISECONDS)
      .tag("SensorId", "200")
      .addField("idle", 20L)
      .addField("user", 22L)
      .addField("system", 2L)
      .build();

    Point point3 = Point.measurement("cpu")
      //.time(System.currentTimeMillis(), TimeUnit.MILLISECONDS)
      .tag("SensorId", "300")
      .addField("idle", 30L)
      .addField("user", 33L)
      .addField("system", 3L)
      .build();

    batchPoints.point(point2);
    batchPoints.point(point3);
    influxDB.write(batchPoints);


    Query query = new Query("SELECT * FROM cpu", DB);
    QueryResult queryResult = influxDB.query(query);
    System.out.println(queryResult);


    influxDB.close();
  }


  public static void main(String[] args) {
    TestInfluxDB testInfluxDB = new TestInfluxDB();
  }
}
