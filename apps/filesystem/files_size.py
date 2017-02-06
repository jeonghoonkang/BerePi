
# -*- coding: utf-8 -*-
# Author : jeonghoonkang https://github.com/jeonghoonkang

# file list and size 

from __future__ import print_function
import os
import sys
import operator

def null_decorator(ob):
    return ob

if sys.version_info >= (3,2,0):
    import functools
    my_cache_decorator = functools.lru_cache(maxsize=4096)
else:
    my_cache_decorator = null_decorator

start_dir = os.path.normpath(os.path.abspath(sys.argv[1])) if len(sys.argv) > 1 else '.'

@my_cache_decorator
def get_dir_size(start_path = '.'):
    total_size = 0
    if 'scandir' in dir(os):
        # using fast 'os.scandir' method (new in version 3.5)
        for entry in os.scandir(start_path):
            if entry.is_dir(follow_symlinks = False):
                total_size += get_dir_size(entry.path)
            elif entry.is_file(follow_symlinks = False):
                total_size += entry.stat().st_size
    else:
        # using slow, but compatible 'os.listdir' method
        print (start_path)
        for entry in os.listdir(start_path):
            full_path = os.path.abspath(os.path.join(start_path, entry))
            if os.path.isdir(full_path):
                total_size += get_dir_size(full_path)
            elif os.path.isfile(full_path):
                total_size += os.path.getsize(full_path)
    return total_size

############################################################
###  main ()
############################################################
if __name__ == '__main__':
    dir_tree = {}
    ### version, that uses 'slow' [os.walk method]
    #get_size = get_dir_size_walk
    ### this recursive version can benefit from caching the function calls (functools.lru_cache)
    get_size = get_dir_size

    filenames = os.listdir(start_dir)
    for filename in filenames:
        #print ("last -> " + filename[-1:] )
        #print ("first -> " + filename[:1] )
        if ( '.' == filename[-1:] || '~' == filename[:1] ) :
            continue
        full_filename = os.path.join(start_dir, filename)
        print (full_filename)
        break

    for root, dirs, files in os.walk(start_dir):
        for d in dirs:
            print (dirs)
            print ("check")
            dir_path = os.path.join(root, d)
            if os.path.isdir(dir_path):
                dir_tree[dir_path] = get_size(dir_path)

#    for d, size in sorted(dir_tree.items(), key=operator.itemgetter(1), reverse=True):
#        print('%s\t%s' %(bytes2human(size, format='%(value).2f%(symbol)s'), d))
    #print( dir_tree.items()) 
    #print( 'size = %d' dir_tree) 
    print('-' * 80)
    if sys.version_info >= (3,2,0):
        print(get_dir_size.cache_info())
