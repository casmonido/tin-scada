#!/usr/bin/python2
#trzeba zmienic plc_server.y PORT na 1780
from struct import *
import socket
import sys
import mutex
import threading
import time
import logging

import SLMP
import StringIO

SCADA_IP = '127.0.0.1' # docelowo do pliku konfiguracyjnego 
SCADA_PORT = 1298
BUFFER_SIZE = 2000 # sa rozne dla scady i servera - do zmiany
PLC_SERVER_PORT = 2010


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
		
		logging.debug('ServerThread connected')
		#print("ServerThread connected...")
		while 1:

			waitngForMessage.acquire()

			#logging.debug( 'Will send Client Message to server soon: ',  SLMP.binary_array2string(scadaMessage))
			#print "Will send Client Message to server soon: ",  SLMP.binary_array2string(scadaMessage)
			

			ServerSock.send(scadaMessage) 
			myServerReply = ServerSock.recv(BUFFER_SIZE)
			logging.debug(SLMP.binary_array2string(myServerReply))

			#print SLMP.binary_array2string(myServerReply)

			serverReply = myServerReply
			logging.debug(' waitingForResponse.release() before ')
			waitingForResponse.release()
			logging.debug(' waitingForResponse.release() after')

		logging.debug( 'Exiting Server Thread' )
		ServerSock.close() 




class ClientThread (threading.Thread):

	def __init__(self, ClientSock):
		threading.Thread.__init__(self)
		self.ClientSock = ClientSock

	def run(self):

		global occupied, scadaMessage, serverReply
		#while 1:
		logging.debug('ClientThread receiving data...')
		myScadaMessage = self.ClientSock.recv(BUFFER_SIZE) # tak chyba nie mozna do StringIO


		notEmpty.acquire()
		while occupied == 1:
			notEmpty.wait()
		occupied = 1

		notEmpty.release()

		scadaMessage = myScadaMessage

		#print "occupied: " , occupied 
		#print(occupied)
		#print "scadaMessage: " , SLMP.binary_array2string(scadaMessage)
		
		waitngForMessage.release()
		logging.debug('Client waiting for response')
		time.sleep(5)
		waitingForResponse.acquire()
		myServerReply = serverReply
		logging.debug ('Client wake up')
		notEmpty.acquire()
		occupied = 0
		
		self.ClientSock.send(myServerReply)
		logging.debug('To Client Sent message')			
		notEmpty.notify()
		notEmpty.release()
			
		logging.debug('Exiting Client Thread')
		self.ClientSock.close()



#main
logging.basicConfig(level=logging.DEBUG,format='[%(levelname)s] (%(threadName)-9s) %(message)s',)

client_threads_collection = []

serverthread = ServerThread('127.0.0.1', PLC_SERVER_PORT)
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
logging.debug('Exiting Main Thread')
ClientSock.close()


