4 tables tsdb, tsdb-meta, tsdb-uid, tsdb-tree among them tsdb is the single huge table 
where OpenTSDB puts the whole data. So to set delete time we need to alter conf for tsdb table only.

As per the excerpt from the docs (above) TTL can be set for column family - tsdb has a single cf i.e. t, 
which is to fulfill the bare minimum i.e. HBase requires a table to have at-least one column family.

check the current value for the TTL, via shell:

hbase> describe 'tsdb'

Table tsdb is ENABLED
tsdb, {NAME => 't', VERSIONS => 1, COMPRESSION => 'NONE', TTL => 'FOREVER'}
using HBase shell - setting TTL:

hbase> alter ‘tsdb′, NAME => ‘t′, TTL => 8640000
8640000 number of seconds equal to 100 days (3 months approx)
