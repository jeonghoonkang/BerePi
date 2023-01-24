## nginx readme

- configuration file
  - sudo docker cp nginx:/etc/nginx/conf.d/default.conf ./

- to modify
<pre>

    location / {
        root   /usr/share/nginx/html;
        index  index.html index.htm;
        autoindex on;
        auth_basic "First Page";
        auth_basic_user_file /etc/.passwd;
    }
    
</pre>

## nginx run option
- sudo docker run --name nginx -p 80:80 -v /web:/usr/share/nginx/html:ro nginx


# passwd
- sudo htpasswd /etc/nginx/.htpasswd another_user
