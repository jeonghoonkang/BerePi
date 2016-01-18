#!/usr/bin/python
 
import socket
import os
import sys
import struct
import time

ETYPE_VALUE_MAX = 8000

def main():
	SERVER_ADDR = "125.xx.xx.41"
	SERVER_PORT = 8283
	print "   try connecting .... "
	
	sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
	ret_conn = sock.connect( ( SERVER_ADDR, SERVER_PORT ) )
	
	readBuffer = ""
	receivedLines = []
	sendLines = []
	
	while True:
		# provide buffer
		recv = sock.recv( 1024 )
		readBuffer += recv

		print recv
	
		# consume buffer	
		l = readBuffer.split( ":" )
		
		if ( len(l) < 2 ):
			pass # nothing to do
		else:
			# dump
			#print >> sys.stderr, "*readBuffer='" + readBuffer + "'"

			#
			readBuffer = ""
	
			# check last
			e = l[-1]
			l = l[:-1]
			if e != "":
				readBuffer = e
				# dump
				#print >> sys.stderr, "+readBuffer='" + readBuffer + "'"
	
			# check first
			s = l[0]
			if s.startswith( "Welcome" ):
				s = s[ len( "Welcome"): ]
				l[0] = s
	
			#
			receivedLines += l
	
			# 
			#for s in l:
			#	print >> sys.stderr, "+line='" + s + "'"
	
		# make packets
		for s in receivedLines:
			#
			if len( s ) < 48:
				print >> sys.stderr, "wrong data:" + s
				print >> sys.stderr, "dump receivedLines"
				for ss in receivedLines:
					print >> sys.stderr, ss

			assert len(s)>=48

			# common
			head = s[:20]
			type = s[20:24]
			serialID = s[24:36]
			nodeID = s[36:40]
			seq = s[40:44]
			battery = s[44:48]
	
			#
			if type == "0064": # TH
				temperature = bigEndian( s[48:52] )
				humidity = bigEndian( s[52:56] )
				light = bigEndian( s[56:60] )

				# T
				v1 = -39.6 + 0.01 * temperature
				
				# H
				tmp = -4 + 0.0405 * humidity + (-0.0000028) * humidity * humidity
                            	v2 = (v1 - 25) * (0.01 + 0.00008 * humidity) + tmp

				# L
				tmp = (light * 100) / 75
                            	v3 = tmp * 10
				
				#
				t = int( time.time() )
				print "thl.temperature %d %f nodeid=%d" % ( t, v1, bigEndian( nodeID ) )
				print "thl.humidity %d %f nodeid=%d" % ( t, v2, bigEndian( nodeID ) )
				print "thl.light %d %f nodeid=%d" % ( t, v3, bigEndian( nodeID ) )
	
			elif type == "0065":# PIR
				pass # ignore this.
	
			elif type == "0066":# CO2
				ppm = s[48:52]

				t = int( time.time() )
				tmp = float( bigEndian( ppm ) )
				value = float( 1.5 * ( tmp  / 4086 ) * 2 * 1000 )

				print "co2.ppm %d %f nodeid=%d" % ( t, value, bigEndian( nodeID ) )
	
			elif type == "006D" or type == "006d": # SPlug
				#current = s[48:54]
				#t_current = s[60:66]
				rawData = s[54:60]
				tmp = bigEndian( rawData )
				if tmp > 15728640:
					tmp = 0
				else:
					tmp = float( tmp / 4.127 / 10 )

				watt = tmp
				t = int( time.time() )
				print "splug.watt %d %f nodeid=%d" % ( t, watt, bigEndian( nodeID ) )

	
			elif type == "00D3" or type == "00d3": # etype
				# length check
				if len( s ) < 72:
					print >> sys.stderr, "ignore too short data for etype:" + s
					continue

				t_current = s[48:56]
				current = s[64:72]
	
				current = toFloat( swapBytes( current ) )
				t_current = littleEndian( swapBytes( t_current ) )
				nodeID = bigEndian( nodeID )

			else:
				print >> sys.stderr, "Invalid type:" + type
				pass
	
		# clear
		receivedLines = []
		sys.stdout.flush()	
	
if __name__ == "__main__":
	main()
	

