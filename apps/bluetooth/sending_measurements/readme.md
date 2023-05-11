
To enable sending measurements Via Bluetooth on RaspberryPi
from https://towardsdatascience.com/sending-data-from-a-raspberry-pi-sensor-unit-over-serial-bluetooth-f9063f3447af


Installation and Setup
Before we start there are a couple of changes required for the Bluetooth to work. These are outlined below.

Configuring the device Bluetooth
We begin by changing the configuration of the installed Bluetooth library:

sudo nano /etc/systemd/system/dbus-org.bluez.service
Here we locate the line starting ExecStart , and replace it with the following:

ExecStart=/usr/lib/bluetooth/bluetoothd --compat --noplugin=sap
ExecStartPost=/usr/bin/sdptool add SP
Having added the ‘compatibility’ flag, we now have to restart the Bluetooth service on the Pi:

sudo systemctl daemon-reload;
sudo systemctl restart bluetooth.service;
Pairing our monitor device
To prevent issues with pairing Bluetooth devices whilst out in the field, it is always a good idea to pre-pair devices — saving their configuration.

To do this we use bluetoothctl following the process described in the link below:

Pairing a Bluetooth device using a terminal
In using a raspberry pi zero, you are limited on USB ports. Instead of having to always have a USB hub connected to the…
medium.com

Locate our host MAC address
hcitool scan
This gives results in the format:

Scanning ...
XX:XX:XX:XX:XX:XX device1
XX:XX:XX:XX:XX:XX device2
2. select the device we want and copy its address.

3. execute the following:

sudo bluetoothctl
4. In the Bluetooth console run the following 3 commands (substituting your copied address):

discoverable on
# then
pair XX:XX:XX:XX:XX:XX
# and 
trust XX:XX:XX:XX:XX:XX
# where XX corresponds to the address copied from above
When pairing you may be asked to confirm a pin on both devices. trust saves the device address to the trusted list.

To make a PI discoverable on boot, you can have a look at the code here:

Keep Bluetooth discoverable (RPI / Unix )
How to enable Bluetooth visibility and pair from the boot.
medium.com

Enabling communication on startup
Finally, we wish to tell the device to watch for incoming Bluetooth connections when it boots. To do this we can add the following file to /etc/rc.local (before the exit command).

sudo rfcomm watch hci0 &
Take care to include the ampersand at the end, as otherwise, it will stall the device bootup process. Also if you are reading another device over serial, e.g. a GPS receiver, you may want to use rfcomm1 instead of hci0 (rfcomm0).

Connecting to the Bluetooth serial from another device
Depending on what device you are using, the method to read from a serial monitor varies. On an android device, you may take the node/javascript approach (this should work on all operating systems!). For the purpose of this demo, I will describe a method using python to check things are working on a MacBook Pro.

Determining the port name
If you have a terminal, the simplest way to do this is to type

ls /dev/tty.
and hit the tab (autocomplete) button.

Presuming you have not changed this, this should be your device hostname followed by SerialPort. The default serial port path for a freshly installed raspberry pi should be

/dev/tty.raspberrypi-SerialPort
Reading data received
To read any data received, we can use the python serial library coupled with the following code snippet.

import serial
ser = serial.Serial('/dev/tty.raspberrypi-SerialPort', timeout=1, baudrate=115000)
serial.flushInput();serial.flushOutput()
   
while True:
    out = serial.readline().decode()
    if out!='' : print (out)
Note that this is an infinite loop that keeps printing anything it receives. To cancel it when the message ‘exit’ is received we can use:

if out == 'exit': break
Sending data from the sensor
From the shell
When testing the simplest way to send data is to echo it to /dev/rgcomm0 from the raspberry pi shell. This allows us to manually test communication over the port before writing anything more complicated.

echo "hello!" > /dev/rfcomm0
From a python script
If reading data from the raspberry pi and pre-processing it, chances are we will be using python to do the heavy lifting. From here we can treat the rfcomm0 channel as a file and write to it as follows:

with open(‘/dev/rfcomm0’,’w’,1) as f:
     f.write(‘hello from python!’)
Conclusions
If we want to quickly check that our sensors are behaving whilst out in the field, we can make use of the Bluetooth capabilities of the Raspberry Pi. This is done by creating a Bluetooth serial port and sending data over it. Such methods are particularly useful if we do not wish to carry bulky laptops, or where a WiFi network is occupied or unavailable.

More complex tasks such as sending commands to the Raspberry Pi, or even SSHing into it over Bluetooth are also possible but are beyond the scope of this tutorial.
