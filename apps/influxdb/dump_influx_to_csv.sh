# run in bash
echo " please input table_name, db_name, time"
echo " for example # dump_influx_to_csv.sh table_name db_name start_time end_time csv_name"

table_name=$1
db_name=$2
field_name=$3
start_time=$4
end_time=$5
csv_name=$6

influx -database db_name -execute "SELECT "$field_name" FROM "$table_name" WHERE time >= "$start_time" and time <="$end_time" -format csv >>"$csv_name


#influx -database 'kwangmyung' -execute "SELECT Power FROM slave1_ctn_02 WHERE time >= '2017-04-26 00:00:00' and time <='2017-05-06 00:00:00' "  -format csv >> slave1_CTN_02.csv
