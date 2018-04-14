# -*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang

from __future__ import print_function
import subprocess
import os
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
    print ("... start running", " inputs are ", ip, port, id)

    print ("... key generating")
    os.system('ssh-keygen')

    run_cmd = "cat '/home/tinyos/.ssh/id_rsa.pub'"
    run_cmd += " | ssh -p %s %s@%s" %(port, id, ip)
    run_cmd += " 'cat>>/home/%s/.ssh/authorized_keys'" %id
    print (run_cmd)
    os.system(run_cmd)

    ''' 아래 코드는 동작을 안함. 확인 필요 '''
    #ret = subprocess.check_output(run_cmd)
    #print (ret)
