#!/usr/bin/python2
from struct import *
import socket
import struct
import sys
import mutex
import threading
import time
import logging
import SLMP
import linecache
import errno
from socket import error as socket_error

# zmienne do synchronizacji
waitngForMessage = threading.Semaphore(0)  
waitingForResponse = threading.Semaphore(0) 
notEmpty = threading.Condition()
occupied = 0 
global scadaMessage
global serverReply
# zmienne ustawiane przy konfiguracji srodowiska
global SCADA_IP  
global SCADA_PORT 
global PLC_SERVER_PORT



def configure(configFilePath):
	global SCADA_IP, SCADA_PORT 
	global PLC_SERVER_PORT 
	global SCADA_BUFFER_SIZE, SERVER_BUFFER_SIZE

	configFile = open(configFilePath)

	SCADA_IP = linecache.getline(configFilePath, 1) # pobierz linie
	SCADA_IP = SCADA_IP[10:-1] # znajac format linii: 'SCADA_IP: 127.0.0.1', pobierz znaki od 10-go do przedostaniego
	SCADA_PORT = linecache.getline(configFilePath, 2)
	SCADA_PORT = SCADA_PORT[12:-1]
	SCADA_PORT = int(SCADA_PORT)
	PLC_SERVER_PORT =linecache.getline(configFilePath, 3)
	PLC_SERVER_PORT = PLC_SERVER_PORT[17:-1]
	PLC_SERVER_PORT = int(PLC_SERVER_PORT)
	configFile.close()



# funkcja pomocnicza do odbierania zadanej liczby bajtow za pomaca recv(), jesli bedzie mniej bajtow zwraca None
def recvall(sock, expectedLen):
	data = ''
	while len(data) < expectedLen:
		packet = sock.recv(expectedLen - len(data)) # recv() pobierze maksimum tyle bajtow, ile podane w argumencie
		if not packet:
			return None
		data += packet
	return data



class ServerThread (threading.Thread):

	def __init__(self, ip, port):
		threading.Thread.__init__(self)
		self.ip = ip
		self.port = port

	def run(self):
		global scadaMessage, serverReply
		ServerSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# w razie braku polaczenia z serwerem ponawiaj proby
		while True:
			try:
				connected = ServerSock.connect((self.ip, self.port))
			except socket_error as serr:
				if serr.errno != errno.ECONNREFUSED:
					raise serr # to nie jest blad ktory chcemy obsluzyc - re-raise
				print('[ServerThread]\t Waiting for connection to the server...')
				time.sleep(5)
				continue # sprobuj ponownie
			else: # jesli nie bylo except, idz dalej
				break

		print('[ServerThread]\t Connected')
		while 1:
			waitngForMessage.acquire()

			ServerSock.send(scadaMessage)

			# tu moga byc bledy -- do obsluzenia
			myServerReply = recvall(ServerSock, 9) # to find out why 9, see SMLP manual page 23
			msgLen = struct.unpack('<H', myServerReply[7:]) # <H means litle endian ushort
			myServerReply += recvall(ServerSock, msgLen[0]) # msgLen is a tuple

			logging.debug(SLMP.binary_array2string(myServerReply))
			serverReply = myServerReply

			waitingForResponse.release()



class ClientThread (threading.Thread):

	def __init__(self, ClientSock):
		threading.Thread.__init__(self)
		self.ClientSock = ClientSock

	def run(self):
		global occupied, scadaMessage, serverReply
		while True:

			myScadaMessage = recvall(self.ClientSock, 9)
			if myScadaMessage == None: # jesli nie udalo sie odebrac chociaz naglowka, wyjdz
			 	print('[ClientThread]\t Exiting')
				self.ClientSock.close()
				return
			print('[ClientThread]\t Receiving message') 
			msgLen = struct.unpack('<H', myScadaMessage[7:])
			myScadaMessage += recvall(self.ClientSock, msgLen[0]) # tu tez potencjalnie moga byc bledy
			logging.debug(SLMP.binary_array2string(myScadaMessage))

			notEmpty.acquire()
			while occupied == 1:
				notEmpty.wait()
			occupied = 1
			notEmpty.release()

			scadaMessage = myScadaMessage

			waitngForMessage.release()
			print('[ClientThread]\t Waiting for response from server')
			time.sleep(2)

			waitingForResponse.acquire()
			myServerReply = serverReply

			notEmpty.acquire()
			occupied = 0
			notEmpty.notify()
			notEmpty.release()

			self.ClientSock.send(myServerReply) # tu tez moga byc bledy, tez exit
			print('[ClientThread]\t Reply sent to SCADA')




# konfiguracja srodowiska: 
if  len(sys.argv) < 2:
	print("Przy wywolywaniu programu, podaj sciezke do pliku konfiguracyjnego")
	quit()
configure(sys.argv[1])
logging.basicConfig(level=logging.DEBUG,format='[%(levelname)s] (%(threadName)-9s) %(message)s',)

# tworzenie watkow:
serverThread = ServerThread('127.0.0.1', PLC_SERVER_PORT)
serverThread.daemon = True		# watek zostanie zamkniety/umrze kiedy zginie watek glowny
serverThread.start()

clientThreadsCollection = []
ClientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ClientSock.bind((SCADA_IP, SCADA_PORT))
ClientSock.listen(1)
print("Proxy oczekuje polaczen na porcie " + str(SCADA_PORT))
while True:
	NewClientSock = ClientSock.accept()[0]
	newThread = ClientThread(NewClientSock) 
	clientThreadsCollection.append(newThread)
	newThread.daemon = True
	newThread.start()