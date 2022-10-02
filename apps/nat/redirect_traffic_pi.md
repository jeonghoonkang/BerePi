## Redirect traffic with Raspberry Pi
- I will use iptables for this example, but first we need to check is port forwarding enabled on our raspberry pi, and we can do that with next command  as root:
  - cat /proc/sys/net/ipv4/ip_forward
- If the return value is 1, we are ready to go, but if return value is 0, we need to set that value to 1 with next command:
  - echo “1” > /proc/sys/net/ipv4/ip_forward
- Now we can start configuring iptables. We would like to forward specific traffic to cloud server and that traffic is defined on a couple of ports. If we have a website on our server we need to forward port 80 (for HTTP) and if we want to have an option to connect remotely to our server with ssh connection we need to forward port 22.  Also, we need to forward port that is your server specific, in my case we need to forward 1500 that is defined for our MqTT server. We can do this following commands:
  - iptables -t nat -A PREROUTING -p tcp –dport {Source_Port_Number} -j DNAT –to-destination {Destination_IP_address}:{Destination_Port_Number}

- Example:
<pre>
iptables -t nat -A PREROUTING -p tcp –dport 80 -j DNAT –to-destination 66.249.75.126:80

# And now we need to save our iptables with next command:
iptables -t nat -A POSTROUTING -j MASQUERADE

</pre>
