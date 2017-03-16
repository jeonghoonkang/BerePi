#server program
import socket
import threading

HOST = ''
PORT = 4000
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(3)
conn, addr = s.accept()
print(' '*10, 'Connected by', addr)

# def sendingMsg():
# 	while True:
# 		data = input()
# 		data = data.encode("utf-8")
# 		conn.send(data)
# 	conn.close()

def gettingMsg():
	while True:
		data = conn.recv(1024)
		if not data:
			break
		else:
			# data = str(data).split("b'", 1)[1].rsplit("'",1)[0]
            data = data[:5]
			print(data)
	conn.close()

threading._start_new_thread(sendingMsg,())
threading._start_new_thread(gettingMsg,())

while True:
	pass
