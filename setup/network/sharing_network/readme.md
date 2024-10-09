## Network setup
### IP address for direct connetion with PC
- Connect RaspberryPi with PC directlry
 - RPI should have DHCP ethernet connection
 - after that, ifcofifg gives Bridge IP address scope
- Scan ping with IP scope
  - remove >/dev/null if you want to read the result
  - <pre> for ip in $(seq 1 4); do ping -c 1 -W 1 192.168.2.$ip > /dev/null; done </pre>
