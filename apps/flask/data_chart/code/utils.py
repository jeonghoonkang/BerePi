import sys
import os

def recursive_search_dir(_nowDir, _filelist):
    dir_list = [] 
    try:
        f_list = os.listdir(_nowDir)
    except FileNotFoundError:
        print("\n"+_nowDir)
        sys.exit(1)

    for fname in f_list:
        if os.path.isdir(_nowDir + "/" + fname):
            dir_list.append(_nowDir + "/" + fname)
        elif os.path.isfile(_nowDir + "/" + fname):
            file_extension = os.path.splitext(fname)[1]
            if file_extension == ".csv" or file_extension == ".CSV":  # csv
                _filelist.append(_nowDir + "/" + fname)

    for toDir in dir_list:
        recursive_search_dir(toDir, _filelist)