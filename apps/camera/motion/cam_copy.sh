#!/bin/bash
#Author: github.com/jeonghoonkang

rsync -avhz --partial '--rsh=ssh -p PORTNUM' /var/lib/motion/*.jpg tinyos@IP or URL:webdav/gw/cam
