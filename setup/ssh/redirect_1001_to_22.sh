#!/bin/bash

# Redirect incoming connections on port 1001 to the local SSH service (port 22)
# Run this script with root privileges.

iptables -t nat -A PREROUTING -p tcp --dport 1001 -j REDIRECT --to-port 22
iptables -t nat -A OUTPUT -p tcp --dport 1001 -j REDIRECT --to-port 22
