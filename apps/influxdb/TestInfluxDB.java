import java.util.concurrent.TimeUnit;

import org.influxdb.InfluxDB;
import org.influxdb.InfluxDBFactory;
import org.influxdb.dto.Point;
import org.influxdb.dto.Pong;
import org.influxdb.dto.Query;
import org.influxdb.dto.QueryResult;


public class TestInfluxDB {

  private InfluxDB influxDB;
  private String dbName;


  public TestInfluxDB() {
    influxDB = InfluxDBFactory.connect(
      "http://192.168.149.146:8086", "root", "root");
    dbName = "pobmons";

    Pong pong = influxDB.ping();
    System.out.println("pong = " + pong);

    String version = influxDB.version();
    System.out.println("version = " + version);

    influxDB.enableBatch(2000, 100, TimeUnit.MILLISECONDS);

    Point point1 = Point.measurement("cpu")
      .time(System.currentTimeMillis(), TimeUnit.MILLISECONDS)
      .addField("idle", 90L)
      .addField("user", 9L)
      .addField("system", 1L)
      .build();
    influxDB.write(dbName, "autogen", point1);

    Query query = new Query("SELECT * FROM cpu", dbName);
    QueryResult queryResult = influxDB.query(query);
    System.out.println(queryResult);

    /*
    Query query = new Query(
      "SELECT * FROM temperature.celsius.1000000001 WHERE time > '2016-09-18'"
      , "pobmons");
    QueryResult queryResult = influxDB.query(query);
    */
    //System.out.println(queryResult.getResults().get(0));
  }


  public static void main(String[] args) {
    TestInfluxDB testInfluxDB = new TestInfluxDB();
  }
}
