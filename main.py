#!/usr/bin/python2
#trzeba zmienic plc_server.y PORT na 1780
from struct import *
import socket
import sys
import mutex
import threading



SCADA_IP = '127.0.0.1' # docelowo do pliku konfiguracyjnego 
SCADA_PORT = 1280 
BUFFER_SIZE = 2000 # sa rozne dla scady i servera - do zmiany


# i guess these should not be global as well
waitngForMessage = threading.Semaphore(0)  # should have been a mutex with initial value of zero
waitingForResponse = threading.Semaphore(0) #acquire(), release()
outsideMutex = mutex.mutex() #lock(), unlock(), testandset()
notEmpty = threading.Condition() #wait(), notify()


class ServerThread (threading.Thread):

	def __init__(self, ip, port, scadaMessage, serverReply):
		threading.Thread.__init__(self)
		self.ip = ip
		self.port = port
		self.scadaMessage = scadaMessage
		self.serverReply = serverReply

	def run(self):
		ServerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		ServerSock.connect((self.ip, self.port))
		print("ServerThread connected...")
		while 1:

			waitngForMessage.acquire()
			ServerSock.send(self.scadaMessage) 
			myServerReply = ServerSock.recv(BUFFER_SIZE)
			serverReply = myServerReply
			waitingForResponse.release()

		print "Exiting Server Thread"
		ServerSock.close()




class ClientThread (threading.Thread):

	def __init__(self, ClientSock, scadaMessage, serverReply):
		threading.Thread.__init__(self)
		self.ClientSock = ClientSock
		self.scadaMessage = scadaMessage
		self.serverReply = serverReply

	def run(self):
		while 1:
			print("ClientThread receiving data...")
			myScadaMessage = self.ClientSock.recv(BUFFER_SIZE) # tak chyba nie mozna do StringIO 

			if outsideMutex.testandset() == False:
				notEmpty.wait()
			scadaMessage = myScadaMessage
			waitngForMessage.release()
			waitingForResponse.acquire()
			myServerReply = serverReply
			notEmpty.notify() #czy to zadziala?
			outsideMutex.unlock()

			ClientSock.send(myServerReply)
		print "Exiting Client Thread"
		ClientSock.close()



#main
scadaMessage = "" # these should be StringIOs insead of regular strings probably 
serverReply = ""
client_threads_collection = []

serverthread = ServerThread('127.0.0.1', 1780, scadaMessage, serverReply)
serverthread.start()

ClientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ClientSock.bind((SCADA_IP, SCADA_PORT))
ClientSock.listen(1)
while 1:
	NewClientSock = ClientSock.accept()[0]
	newthread = ClientThread(NewClientSock, scadaMessage, serverReply) 
	client_threads_collection.append(newthread) 
	newthread.start()
	#NewClientSock.close() # dunno 

serverthread.join()
for x in client_threads_collection:
	x.join()
print "Exiting Main Thread"
ClientSock.close()
0

