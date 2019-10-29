# VPN (Virtual private network)

  1) PPTP (Point to Point Tunneling Protocol)
  2) L2TP (Layer 2 Tunneling Protocol)
  3) SSTP (Secure Socket Tunneling Protocol)
  4) OpenVPN


## 1. SERVER

## 2. CLIENT

### 1) install pptp-linux

  ```sudo apt install pptp-linux```

### 2) create VPN profile

- create _berepi_ profile

  ```sudo vim /etc/ppp/peers/berepi```


```
pty "pptp $VPNHOSTNAME --nolaunchpppd --debug"
name $USERNAME
password $PASSWORD
remotename PPTP
require-mppe-128
require-mschap-v2
refuse-eap
refuse-pap
refuse-chap
refuse-mschap
noauth
debug
persist
maxfail 0
defaultroute
replacedefaultroute
usepeerdns
```

https://prosindo.com/blog/2015/08/24/vpn-pptp-client-on-raspberry-pi/
