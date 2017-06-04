 - Setting the Raspberry Pi’s IP address
   - Edit your cmdline.txt file:
   - You can edit it directly on the Raspberry Pi:
   - /boot/cmdline.txt
   - You will need to add the ip=x.x.x.x value to the end of the line (ensure you do not add any extra lines).

  - For network settings where the IP address is obtained automatically, use an address in the range 169.254.X.X (169.254.0.0 – 169.254.255.254):
    - ip=169.254.0.2
      - For network settings where the IP address is fixed, use an address which matches the laptop/computers address except the last one (assuming your netmask is at least 255.255.255.0 / 255.255.0.0).
    - ip=192.168.0.2
      - Ensure you take note of this IP address (you will need it every time you want to directly connect to the Raspberry Pi, although you might be able to use the hostname).
      
