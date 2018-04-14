# -*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang

from __future__ import print_function
import subprocess
import sys

if __name__ == '__main__':


    print ("usage : python sshkey.py {IP_ADD} {PORT}, {} : user should input")

    if len(sys.argv) < 2:
        exit("[bye] you need to input args")

    arg1 = sys.argv[1]
    arg2 = sys.argv[2]
    arg3 = sys.argv[3]

    ip = arg1
    port = arg2
    id = arg3
    print ("...running", " inputs are ", ip, port, id)



'''
if [ -z $ip ];
then #아규먼트가 없으면 실행
    echo "you need to input IP and port number"
#    find ./ -name "*.flac" -print0 | xargs -0 -i -t ffmpeg -i {}
#            -codec:a libmp3lame -b:a 256k {}.mp3
else #아규먼트가 있으면
    ssh-keygen
    cat ~/.ssh/id_rsa.pub | ssh -p $port tinyos@$ip 'cat>>/home/tinyos/.ssh/authorized_keys'
fi
'''
