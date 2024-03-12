# Author: Jeonghoon Kang (https://github.com/jeonghoonkang/BerePi

import threading
import glob
import os

FILE_TYPE = "*.mkv"
Thread_time = 10.0

f1 = glob.glob(FILE_TYPE)

def status():
    
    threading.Timer(Thread_time, status).start()
    f2 = glob.glob(FILE_TYPE)
    f3 = set(f2) - set(f1)

    if len(f3) == 0 :
        pass
        #print ("No new file")
    else:
        print (os.getcwd())        
        print ("got new file trigger")
        print (list(f3)[0])
        #print ("list element")
        #print (list(f3)) 



if __name__ == "__main__":
    print ("scan_new_file.py is being run directly")
    print (os.getcwd())
    print ("scanning new file of ", FILE_TYPE, "Thread time: ", Thread_time )
    #run scan 
    status()
