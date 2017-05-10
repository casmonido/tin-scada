#!/usr/bin/python2
#trzeba zmienic plc_server.y PORT na 1780
from struct import *
import socket
import sys
import mutex
import threading

import SLMP
import StringIO

SCADA_IP = '127.0.0.1' # docelowo do pliku konfiguracyjnego 
SCADA_PORT = 1280 
BUFFER_SIZE = 2000 # sa rozne dla scady i servera - do zmiany


# i guess these should not be global as well
waitngForMessage = threading.Semaphore(0)  # should have been a mutex with initial value of zero
waitingForResponse = threading.Semaphore(0) #acquire(), release()
notEmpty = threading.Condition() #wait(), notify()
occupied = 0
#wouldn't get recognized as non-global
scadaMessage = ""
serverReply = ""

class ServerThread (threading.Thread):

	def __init__(self, ip, port):
		threading.Thread.__init__(self)
		self.ip = ip
		self.port = port

	def run(self):

		global scadaMessage, serverReply
		ServerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		ServerSock.connect((self.ip, self.port))
		print("ServerThread connected...")
		while 1:

			waitngForMessage.acquire()


			print("Will send Client Message to server soon")
			print SLMP.binary_array2string(scadaMessage)

			ServerSock.send(scadaMessage) 
			myServerReply = ServerSock.recv(BUFFER_SIZE)

			print SLMP.binary_array2string(myServerReply)

			serverReply = myServerReply
			waitingForResponse.release()

		print "Exiting Server Thread"
		ServerSock.close()




class ClientThread (threading.Thread):

	def __init__(self, ClientSock):
		threading.Thread.__init__(self)
		self.ClientSock = ClientSock

	def run(self):
		global occupied, scadaMessage, serverReply
		while 1:
			print("ClientThread receiving data...")
			myScadaMessage = self.ClientSock.recv(BUFFER_SIZE) # tak chyba nie mozna do StringIO


			notEmpty.acquire()
			while occupied == 1:
				notEmpty.wait()
			occupied = 1

			notEmpty.release()

			scadaMessage = myScadaMessage

			print(occupied)
			print SLMP.binary_array2string(scadaMessage)
			
			waitngForMessage.release()
			print("Client waiting for response")
			waitingForResponse.acquire()
			myServerReply = serverReply

			notEmpty.acquire()
			zajete = 0
			notEmpty.notify()
			notEmpty.release()

			self.ClientSock.send(myServerReply)
		print "Exiting Client Thread"
		ClientSock.close()



#main
client_threads_collection = []

serverthread = ServerThread('127.0.0.1', 1780)
serverthread.start()

ClientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ClientSock.bind((SCADA_IP, SCADA_PORT))
ClientSock.listen(1)
while 1:
	NewClientSock = ClientSock.accept()[0]
	newthread = ClientThread(NewClientSock) 
	client_threads_collection.append(newthread) 
	newthread.start()
	#NewClientSock.close() # dunno 

serverthread.join()
for x in client_threads_collection:
	x.join()
print "Exiting Main Thread"
ClientSock.close()
0

