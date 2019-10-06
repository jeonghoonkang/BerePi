# -*- coding: utf-8 -*-
# Author : jeonghoonkang, https://github.com/jeonghoonkang

from __future__ import print_function
import subprocess
import os
import sys

if __name__ == '__main__':

    print ("usage : python %s {ID@IP_ADD} {PORT} {file}, {} : user should input" %__file__)
    print (" if {file} is 'None' : will use /home/user/.ssh/id_rsa ")

    if len(sys.argv) < 4:
        exit("[bye] you need to input args")

    arg1 = sys.argv[1]
    arg2 = sys.argv[2]
    arg3 = sys.argv[3]
    if arg3 == 'None':
        arg3 = '~/.ssh/id_rsa.pub'
    
    ip = arg1
    port = arg2
    print ("... start running", " inputs are ", ip, port)

    print ("... key generating")
    if arg3 == None: os.system('ssh-keygen')

    print ("... entering copying security file")
    run_cmd = "cat %s" %(arg3)
    run_cmd += " | ssh -p %s %s" %(port, ip)
    run_cmd += " 'cat>>/home/%s/.ssh/authorized_keys'" %ip[:ip.index('@')]
    print (run_cmd)
    os.system(run_cmd)

    ''' 아래 코드는 동작을 안함. 확인 필요 '''
    #ret = subprocess.check_output(run_cmd)
    #print (ret)
