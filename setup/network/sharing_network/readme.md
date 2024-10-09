## Network setup
### IP address for direct connetion with PC
- Connect RaspberryPi with PC directlry and PC has setting of Internet sharing with ethernet
  - RPI should have DHCP ethernet connection
  - after that, ifcofifg gives Bridge IP address scope
- Scan ping with IP scope
  - remove >/dev/null if you want to read the result
  - <pre> for ip in $(seq 1 4); do ping -c 1 -W 1 192.168.2.$ip > /dev/null; done </pre>
### setup Mac OSX
- use control panel to setup sharing Internet
- Backbone : wifi, Client : apple USB adapter
- <img width="450" alt="image" src="https://github.com/user-attachments/assets/dd9cfb8f-8c52-4422-b7b3-13b634747bf3">
 
