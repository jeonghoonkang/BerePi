
# Author: Jeonghoon Kang (https://github.com/jeonghoonkang/BerePi

import threading
import glob
import os, time, sys
import natsort

FILE_TYPE = "*.mkv"
Thread_time = 10.0
FPATH = "/var/lib"

def get_init():
    f = glob.glob(FILE_TYPE) 
    return f  
    
def status(f0):
    
    #threading.Timer(Thread_time, status).start()
    print (sys._getframe().f_code.co_name) 
    print (time.strftime('%Y.%m.%d - %H:%M:%S')) 
    f1 = f0
    f2 = glob.glob(FILE_TYPE)
    f3 = set(f2) - set(f1)

    if len(f3) == 0 :
        pass
        #print ("No new file")
    else:
        print ("got new file trigger")
        f_sort = natsort.natsorted(f3)   
        print (f_sort[-1]) 
        
        #print (list(f3)[0])
        #print ("list element")
        #print (list(f3)) 

if __name__ == "__main__":
    print ("scan_new_file.py is being run directly")
    print (os.getcwd())
    print ("scanning new file of ", FILE_TYPE, "Thread time: ", Thread_time )
    #run scan 
    f0 = get_init()  
    os.chdir(FPATH) 
    print (os.getcwd())  
    while (True): 
        status(f0)
        f0 = get_init() 
        time.sleep(5)  
