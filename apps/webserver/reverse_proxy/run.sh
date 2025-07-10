#! /bin/bash  

echo "server list" 
cat server_list.txt  

echo " This mahine has 192.168.0.** , 2290 -> 22"                                                                           
sudo bash ../../../setup/ssh/redirect_2290_to_22.sh                                                                           

port_map=' --map 2280:localhost:80                                                                                                  
--map 2281:localhost:81                                                                                                             
--map 2282:localhost:82                                                                                                             
--map 2283:localhost:83                                                                                                             
--map 2284:localhost:84                                                                                                             
--map 2285:localhost:85                                                                                                             
--map 2286:localhost:86                                                                                                             
--map 2287:localhost:87                                                                                                             
--map 2288:localhost:88                                                                                                             
--map 2289:localhost:89 '

echo 'python3 multi_reverse_proxy.py $port_map  --status-port 89 --status-user admin --status-pass  ####'                                                                                                                                         

sudo python3 multi_reverse_proxy.py $port_map  --status-port 89 --status-user admin --status-pass ####     
