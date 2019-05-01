#-*-coding:utf8-*-
#!/usr/bin/python
# Author : Jeonghoonkang, github.com/jeonghoonkang

from __future__ import print_function
import sys, os

total_size = 0
start_path = "/var/lib/motion"
old_path = "/var/lib/motion/old"
# motion directory /var/lib/motion
# old file diectory /var/lib/motion/old
def get_size():
    #get size of current directory
    for path, dirs, files in os.walk(start_path):
    for f in files:
    fp = os.path.join(path,f)
    _size += os.path.getsize(fp)
    return _size

if __name__ == '__main__' :

    total_size = get_size()
    _ksz_ = int(total_size/1024)

    print("Drictory size:" + str(total_size))
    print('Drictory size: {:,} bytes'.format(total_size).replace(',', ' '))
    print('Drictory size: {:,} KB'.format(_ksz_).replace(',', ' '))
    print('Drictory size: {:,} MB'.format(_ksz_*1024).replace(',', ' '))
    print('Drictory size: {:,} GB'.format(_ksz_*1024**3).replace(',', ' '))

    if _ksz_ > 1024*50 :
        # move old files to OLD dir
        
