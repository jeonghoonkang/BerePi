#! /bin/bash  
echo " This mahine has 192.168.0.**"      

sudo python3 multi_reverse_proxy.py --map 2280:localhost:80 \ 
        --map 2281:localhost:81 \
        --map 2282:localhost:82 \        
        --status-port 90 --status-user **** --status-pass ****
        
