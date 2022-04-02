# Installation
- $ python3 -m pip install --upgrade radicale
- $ python3 -m radicale --storage-filesystem-folder=~/.var/lib/radicale/collections
- 
# Run

# Config check
## Radicale
-  tail -f /var/log/radicale/radicale.log
-  auth : /etc/radicale/users 
## nginx
-  /etc/nginx/conf.d/radicale.conf

