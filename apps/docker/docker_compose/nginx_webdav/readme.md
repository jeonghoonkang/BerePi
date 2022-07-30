
<pre>

version: '3'

services:

  uploadserver:
    image: sashgorokhov/webdav
    container_name: up-nginx
    environment:
      - USERNAME:"user"
      - PASSWORD:"pass"
    volumes:
      - ./up_files:/media
    ports:
      - 5233:80
      
</pre>
