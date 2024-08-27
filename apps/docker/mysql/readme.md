
Docker MySQL

<pre>
docker run --name mysql-test-container \
-e MYSQL_ROOT_PASSWORD=1234 \
-e MYSQL_USER=myuser \
-e MYSQL_PASSWORD=1234 \
-e MYSQL_DATABASE=mydb \
-d maridadb
</pre>
