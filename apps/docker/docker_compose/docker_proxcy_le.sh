# Author : Jeonghoonkang, github.com/jeonghoonkang

# should run by sudo

docker run --detach \
    --name nginx-proxy \
    --publish 80:80 \
    --publish 443:443 \
    --volume /home/tinyos/devel/docker/nginx_proxy/nginx_certs:/etc/nginx/certs \
    --volume /home/tinyos/devel/docker/nginx_proxy/nginx_vhost.d:/etc/nginx/vhost.d \
    --volume /home/tinyos/devel/docker/nginx_proxy/nginx_html:/usr/share/nginx/html \
    --volume /home/tinyos/devel/docker/nginx_proxy/nginx_conf:/etc/nginx/conf.d \
    --volume /var/run/docker.sock:/tmp/docker.sock:ro \
    jwilder/nginx-proxy


docker run --detach \
    --name nginx-proxy-letsencrypt \
    --volumes-from nginx-proxy \
    --volume /var/run/docker.sock:/var/run/docker.sock:ro \
    --env "DEFAULT_EMAIL=jeonghoon.kang@encrypt.tld" \
    jrcs/letsencrypt-nginx-proxy-companion


docker run --detach \
    --name your-proxyed-app \
    --env "VIRTUAL_HOST=www.win.tld" \
    --env "LETSENCRYPT_HOST=tinyos.win.tld" \
    nginxdemos/hello

    nginx


docker run --detach \
    --name grafana \
    --env "VIRTUAL_HOST=othersubdomain.yourdomain.tld" \
    --env "VIRTUAL_PORT=3000" \
    --env "LETSENCRYPT_HOST=othersubdomain.yourdomain.tld" \
    --env "LETSENCRYPT_EMAIL=mail@yourdomain.tld" \
    grafana/grafana


docker run -d --name wordpress -e VIRTUAL_HOST=imbang.net, www.imbang.net -e \
    LETSENCRYPT_EMAIL=jeonghoon.kang@encrypt.tld -v wordpress:/var/www/html wordpress:latest


docker run -P -d nginxdemos/hello

