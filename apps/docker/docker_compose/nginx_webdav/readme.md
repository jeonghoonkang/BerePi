
<pre>

version: '3'

services:

  uploadserver:
    image: sashgorokhov/webdav
    container_name: up-nginx
    environment:
      - SERVER:"http://keties.iptime.org"
      - USERNAME:"ev"
      - PASSWORD:"onedaymovie"
    volumes:
      - ./up_files:/media
    ports:
      - 5233:80
      
</pre>
