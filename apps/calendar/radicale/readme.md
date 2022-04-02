# Installation
- $ python3 -m pip install --upgrade radicale
- $ python3 -m radicale --storage-filesystem-folder=~/.var/lib/radicale/collections
### Installation sub check 
- htpasswd -B -c /etc/radicale/users loom loom
- 
# Run

# Config check
## Radicale
-  tail -f /var/log/radicale/radicale.log
-  auth : /etc/radicale/users 
-  /etc/radicale/config
   - hosts = 0.0.0.0:5232
   - htpasswd_filename = /etc/radicale/users
   - htpasswd_encryption = bcrypt

## nginx
-  /etc/nginx/conf.d/radicale.conf
-  port check : netstat -lntp
-  

