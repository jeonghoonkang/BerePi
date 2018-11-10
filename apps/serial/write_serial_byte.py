import serial,os,time
import sys
import fcntl, socket, struct

lineCnt = 0

def getHwAddr(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
	return ':'.join(['%02x' %ord(char) for char in info[18:24]])

def init():
    macAddr = getHwAddr('eth0')
    macAddr = macAddr.replace(':','.')
    return " # eth0 MAC " + macAddr

sdev = '/dev/ttyAMA0'
rpi3dev = '/dev/serial0'

if __name__== "__main__" :

    if len(sys.argv) is 1:
        print " # RaspberryPi2 SW "
        print " # Serial Byte read and print "
        print " # Default serial device is /dev/ttyAMA0 "
        print " # example : python serial_byte.py 115200 "
        exit(1)

    rate = sys.argv[1]

    maddr = init()

    try:
        # open RASPI serial device, 38400
        # Check speed 38400 or 115200, 9800
        serial_out_device = serial.Serial(rpi3dev, rate)

    except serial.SerialException, e:
        print " << Serial open error"
        exit(1)
    
    print (serial_out_device.name)
    print " >> Serial Open Complete "

    i = " Hi Serial World " # from %s " %maddr
    while True:
        try:
            serial_out_device.write(i) 
            time.sleep(1)

        except serial.SerialException, e:
            print e
            print " [cnt: %3d]" %lineCnt, " << Serial read error"
            exit(0)
