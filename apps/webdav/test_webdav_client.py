# Author: Jeonghoon Kang (github.com/jeonghoonkang)

import sys
from webdav3.client import Client
options = {
 'webdav_hostname': "**nextcloud URL**",
 'webdav_login':    "**nextcloud USER**",
 'verbose'    : True,
 'webdav_password': "**nextcloud PW**"
}
from webdav3.exceptions import WebDavException
import json

def scan_remote():
    try:
        client = Client(options)
        client.verify = True # To not check SSL certificates (Default = True)

        files=client.list(get_info=True)

    except WebDavException as e:
        print(e)

    print (files)
    print ()


    for file in files:
        if file['isdir'] == True:
            print ('##DIRECTORY##', file['path'] )
        else:
            print("**FILE**", file['path'])

    #print (client.info("remote.php/dav/files/tinyos/"))

    #client.download_sync(remote_path="dir1/file1", local_path="~/Downloads/file1")
    #client.upload_sync(remote_path="dir1/file1", local_path="~/Documents/file1")

    print ()
    return client

if __name__ == "__main__":

    print (" KJH webdav_client.py is being run directly")

    webdav_client = scan_remote()
    print (webdav_client.info("/"))
    
    list_ret = webdav_client.list("/")
    json_formatted_str = json.dumps(list_ret, indent=2)
    print (json_formatted_str)

    if len(sys.argv) < 3:
        print ("Usage: webdav_client.py {upload or download} {remote_dir_name} {local_dir_name}")
        print (" for your reliabe code, webdav remote filename and download target file name should exist")
        sys.exit(1)

    
    src_dir_name = sys.argv[2] # remote for download
    dest_dir_name = sys.argv[3] # local for download
    print ("src:", src_dir_name, "dest:", dest_dir_name)

    if len(sys.argv) == 4:
        copy_path = sys.argv[3]
        
    if sys.argv[1] == "upload":
        webdav_client.upload_sync(src_dir_name, dest_dir_name)
    elif sys.argv[1] == "download":
        webdav_client.download_sync(src_dir_name, dest_dir_name)
    else:
        print ("Usage: webdav_client.py {upload or download} {remote_dir_name} {local_dir_name}")
        sys.exit(1)
    
    print (" KJH end of main function")
    
