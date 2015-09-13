
# author : https://github.com/jeonghoonkang
# this shell file should run by root "sudo -s"

./build/tsdb tsdb --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/data --auto-metric

