
### After UBUNTU 17.01
- NetPlan
- /etc/netplan/*.yaml
- netplan apply

### before UBUNTU 17.01
- /etc/network/interfaces

<pre>
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
  address 192.168.100.99
  netmask 255.255.255.0
  gateway 192.168.100.254
  dns-nameserver 8.8.8.8
iface eth1 inet dhcp
</pre>


#### 참조
- joinc.co.kr/w/Site/System_management/NetworkConfiguration
