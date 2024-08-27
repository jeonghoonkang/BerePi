
Docker MySQL

<pre>
docker run --name my-mysql-container \
-e MYSQL_ROOT_PASSWORD=my-secret-pw \
-e MYSQL_USER=myuser \
-e MYSQL_PASSWORD=myuserpassword \
-e MYSQL_DATABASE=mydatabase \
-d mysql:latest
</pre>
