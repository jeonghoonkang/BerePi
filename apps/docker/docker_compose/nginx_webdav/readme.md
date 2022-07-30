
<pre>

version: '3'

services:

  uploadserver:
    image: sashgorokhov/webdav #https://github.com/sashgorokhov/docker-nginx-webdav
    container_name: up-nginx
    environment:
      - USERNAME:"user"
      - PASSWORD:"pass"
    volumes:
      - ./up_files:/media
    ports:
      - 5233:80
      
</pre>
