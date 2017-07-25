# kill a long time copying process
kill $(ps aux |awk '/tinyos.com.com/ {print $2}')
