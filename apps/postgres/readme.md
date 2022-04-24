<pre>
copy file from local to live container: docker cp file.csv container:/file.csv
enter live container: docker exec -it container_id bash
login postgres database from within the container: psql -U superset -d superset
create table in db and copy new table:
create table new (field type ...);
\copy new from 'file.csv' with delimiter as ',' csv header;
</pre>
