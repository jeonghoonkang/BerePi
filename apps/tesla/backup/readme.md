# Backup and Restore of Teslamate
- refence : https://docs.teslamate.org/docs/maintenance/backup_restore/
## DB Backup
<pre> docker-compose exec -T database pg_dump -U teslamate teslamate > /backuplocation/teslamate.bck </pre>
- DATABASE_NAME=teslamate
- DATABASE_USER=teslamate
- DATABASE_HOST=database

## Restore DB
<pre>
# Stop the teslamate container to avoid write conflicts
docker-compose stop teslamate

# Drop existing data and reinitialize
docker-compose exec -T database psql -U teslamate << .
drop schema public cascade;
create schema public;
create extension cube;
create extension earthdistance;
CREATE OR REPLACE FUNCTION public.ll_to_earth(float8, float8)
    RETURNS public.earth
    LANGUAGE SQL
    IMMUTABLE STRICT
    PARALLEL SAFE
    AS 'SELECT public.cube(public.cube(public.cube(public.earth()*cos(radians(\$1))*cos(radians(\$2))),public.earth()*cos(radians(\$1))*sin(radians(\$2))),public.earth()*sin(radians(\$1)))::public.earth';
.

# Restore
docker-compose exec -T database psql -U teslamate -d teslamate < teslamate.bck

# Restart the teslamate container
docker-compose start teslamate
</pre>
