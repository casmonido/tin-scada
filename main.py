#!/usr/bin/python2
from struct import *
import socket
import sys
import mutex
import threading
import time
import logging
import SLMP
import StringIO
import linecache

#zawartosc pliku konfiguracyjnego, nadawane funkcja configure
global SCADA_IP  
global SCADA_PORT 
global BUFFER_SIZE  # sa rozne dla scady i servera - do zmiany
global PLC_SERVER_PORT 

#mutexy na ktorych zawieszac sie beda serwer i klient
waitngForMessage = threading.Semaphore(0)  
waitingForResponse = threading.Semaphore(0) 

notEmpty = threading.Condition() #wait(), notify()
occupied = 0


scadaMessage = ""
serverReply = ""

def configure():
	global SCADA_IP  # docelowo do pliku konfiguracyjnego 
	global SCADA_PORT 
	global BUFFER_SIZE  # sa rozne dla scady i servera - do zmiany
	global PLC_SERVER_PORT 
	configureFile = open("config.txt")
	#pobieramy linie
	SCADA_IP =linecache.getline("config.txt" , 1) 
	## sa w formacie string bierzemy wszystko od 10 znaku do przedostatniego
	SCADA_IP = SCADA_IP[10:-1]					
	SCADA_PORT =linecache.getline("config.txt" , 2)
	SCADA_PORT = SCADA_PORT[12:-1]
	SCADA_PORT = int(SCADA_PORT)
	BUFFER_SIZE =linecache.getline("config.txt", 3)
	BUFFER_SIZE = BUFFER_SIZE[13:-1]
	BUFFER_SIZE = int(BUFFER_SIZE)  ##wymaga dodatkowego rzutowania, chcemy inta a nie stringa
	PLC_SERVER_PORT =linecache.getline("config.txt" , 4)
	PLC_SERVER_PORT = PLC_SERVER_PORT[17:-1]
	PLC_SERVER_PORT = int(PLC_SERVER_PORT)

	configureFile.close()

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
		
		while 1:

			waitngForMessage.acquire()

			ServerSock.send(scadaMessage) 
			myServerReply = ServerSock.recv(BUFFER_SIZE)
			logging.debug(SLMP.binary_array2string(myServerReply))

			serverReply = myServerReply
			waitingForResponse.release()



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
configure()

logging.basicConfig(level=logging.DEBUG,format='[%(levelname)s] (%(threadName)-9s) %(message)s',)

client_threads_collection = []

serverthread = ServerThread('127.0.0.1', PLC_SERVER_PORT)
serverthread.daemon = True   ##to znaczy ze watek zostanie zamkniety/umrze jak zginie watek glowny
serverthread.start()

ClientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ClientSock.bind((SCADA_IP, SCADA_PORT))
ClientSock.listen(1)
while 1:
	NewClientSock = ClientSock.accept()[0]
	newthread = ClientThread(NewClientSock) 
	client_threads_collection.append(newthread)
	newthread.daemon = True  ##to znaczy ze watek zostanie zamkniety/umrze jak zginie watek glowny
	newthread.start()
	#NewClientSock.close() # dunno 

