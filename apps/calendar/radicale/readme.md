# Installation
- $ python3 -m pip install --upgrade radicale
- $ python3 -m radicale --storage-filesystem-folder=~/.var/lib/radicale/collections

### Installation sub check 
- sudo pip install passlib (for encrypt)
- sudo apt install apache2-utils (for htpasswd)
- htpasswd -B -c /etc/radicale/users {id} {pass}


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
  - config code
    <pre>
     server {
           listen 5232;
           listen [::]:5232;
   
           location /radicale/ { # The trailing / is important!
                   proxy_pass        http://localhost:5232/; # The / is important!
                   proxy_set_header  X-Script-Name /radicale;
                   proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
                   proxy_set_header  Host $http_host;
                   proxy_pass_header Authorization;
          }
     }
   </pre>
-  network port check : netstat -lntp

