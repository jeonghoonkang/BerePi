https://gist.github.com/spy86/a2a6bb49a62bdc932cae4954dc981a0a

<pre>

version: '3.7'
services:
  traefik:
    image: traefik:v2.2.0
    ports:
      - "${FRONT_HTTP_PORT:-80}:80"
      # - "${TRAEFIK_PORT:-8080}:8080"
    environment: 
      # - TRAEFIK_LOG_LEVEL=DEBUG
      - TRAEFIK_PROVIDERS_DOCKER_EXPOSEDBYDEFAULT=false
      - TRAEFIK_PROVIDERS_DOCKER=true
      - TRAEFIK_PROVIDERS_DOCKER_NETWORK=traefik01
      # - TRAEFIK_API_INSECURE=true
      - TRAEFIK_ENTRYPOINTS_FRONT=true
      - TRAEFIK_ENTRYPOINTS_FRONT_ADDRESS=:${FRONT_HTTP_PORT:-80}
    networks:
      - traefik01
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    security_opt:
      - label:type:docker_t
  app1:
    image: nginx:1.17.6-alpine
    expose:
      - 80
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.app1.entrypoints=front"
      - "traefik.http.routers.app1.rule=PathPrefix(`/app1{regex:$$|/.*}`)"
      - "traefik.http.routers.app1.middlewares=app1-stripprefix"
      - "traefik.http.middlewares.app1-stripprefix.stripprefix.prefixes=/app1"
    networks:
      - traefik01
  app2:
    image: httpd:2.4.41-alpine
    expose:
      - 80
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.app2.entrypoints=front"
      - "traefik.http.routers.app2.rule=PathPrefix(`/app2{regex:$$|/.*}`)"
      - "traefik.http.routers.app2.middlewares=app2-stripprefix"
      - "traefik.http.middlewares.app2-stripprefix.stripprefix.prefixes=/app2"
    networks:
      - traefik01
networks:
  traefik01:
    driver: bridge

</pre>
