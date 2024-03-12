# Author: Jeonghoon Kang (https://github.com/jeonghoonkang/BerePi

import threading
import glob
import os

f1 = glob.glob('*.mkv')

def status():

    threading.Timer(5.0, status).start()
    f2 = glob.glob('*.mkv')
    f3 = set(f2) - set(f1)

    if len(f3) == 0 :
        print ("No new file")
    else:
        print ("got new file trigger")
        print (list(f3)[0])
        print ("list element")
        print (list(f3)) 

print (os.getcwd())

status()
