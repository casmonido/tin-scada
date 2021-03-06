#!/usr/bin/python2
from struct import *
import socket
import struct
import sys
import mutex
import threading
import time
import logging
import logging.config
import SLMP
import linecache
import errno
import os
from logging.handlers import TimedRotatingFileHandler
from socket import error as socket_error

# zmienne do synchronizacji
waitngForMessage = threading.Semaphore(0)  
waitingForResponse = threading.Semaphore(0) 
notEmpty = threading.Condition()
occupied = 0

#zmienne przesylanych wiadomosci 
global scadaMessage
global serverReply

# zmienne ustawiane przy konfiguracji srodowiska
global SCADA_IP
global PLC_SERVER_IP  
global SCADA_PORT 
global PLC_SERVER_PORT
global LOGGER_CONFIG


#funkcja, ktora czyta z pliku konfiguracyjnego dane wejsciowe polaczenia
def configure(configFilePath):
	global SCADA_IP, SCADA_PORT 
	global PLC_SERVER_IP, PLC_SERVER_PORT 
	global LOGGER_CONFIG

	configFile = open(configFilePath)

	SCADA_IP = linecache.getline(configFilePath, 1) # pobierz linie
	SCADA_IP = SCADA_IP[10:-1] # znajac format linii: 'SCADA_IP: 127.0.0.1', pobierz znaki od 10-go do przedostaniego
	PLC_SERVER_IP = linecache.getline(configFilePath, 2)
	PLC_SERVER_IP = PLC_SERVER_IP[15:-1]
	SCADA_PORT = linecache.getline(configFilePath, 3)
	SCADA_PORT = SCADA_PORT[12:-1]
	SCADA_PORT = int(SCADA_PORT)
	PLC_SERVER_PORT =linecache.getline(configFilePath, 4)
	PLC_SERVER_PORT = PLC_SERVER_PORT[17:-1]
	PLC_SERVER_PORT = int(PLC_SERVER_PORT)
	LOGGER_CONFIG = linecache.getline(configFilePath, 5)
	LOGGER_CONFIG = LOGGER_CONFIG[15:-1]
	configFile.close()



# funkcja pomocnicza do odbierania zadanej liczby bajtow za pomaca recv(), jesli bedzie mniej bajtow zwraca None
def recvall(sock, expectedLen, threadType):
	data = ''
	
	while len(data) < expectedLen:
		try:
			packet = sock.recv(expectedLen - len(data)) # recv() pobierze maksimum tyle bajtow, ile podane w argumencie
		
		except socket.timeout as err:
			logger_debug.debug(threadType + 'Timeout error - receive returning empty string')
			return None
		
		if not packet: # None jesli 'connection reset by peer'
			logger_debug.debug(threadType + 'Receive returning empty string')
			return None

		data += packet
	return data



#funkcja pomocnicza uzywana przez ServerThread, do ponawiania prob polaczenia z serwerem
def reconnect(addr, port):
	logger_debug.debug('[ServerThread]\t Disconnected from the server')
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	
	# w razie braku polaczenia ponawiaj proby
	while True:
		try:
			sock.connect((addr, port))

		except socket_error as serr:
			if serr.errno != errno.ECONNREFUSED:
				raise serr # to nie jest blad ktory chcemy obsluzyc - re-raise
			
			logger_debug.debug('[ServerThread]\t Waiting for connection to the server...')
			time.sleep(3)
			continue # sprobuj ponownie

		else: # jesli nie bylo except, idz dalej
			sock.settimeout(5)
			break
	logger_debug.debug('[ServerThread]\t Connected')
	return sock



#definicja klasy watku serwera
class ServerThread (threading.Thread):

	def __init__(self, ip, port):
		threading.Thread.__init__(self)
		self.ip = ip
		self.port = port

	def run(self):
		global scadaMessage, serverReply
		ServerSock = reconnect(self.ip, self.port)
		
		while True:					
			waitngForMessage.acquire()
			
			# scadaMessage czeka w swoim buforze. 
			# obsluguj ja do skutku
			while True:
			
				try:
					retVal = ServerSock.sendall(scadaMessage) 

				except Exception:
					logger_debug.debug('[ServerThread]\t Exception raised by sendall - unlikely when running on the same PC')
				if retVal != None: # blad
					logger_debug.debug('[ServerThread]\t Sending request to server unsuccessful')
					ServerSock.close()
					ServerSock = reconnect(self.ip, self.port)
					continue

				logger_debug.debug('[ServerThread]\t SCADA message sent to server')
				# pobierz naglowek odpowiedzi 
				# jesli sie nie uda, po resecie polaczenia trzeba wrocic DO WYSYLANIA WIADOMOSCI DO SEWERA
				myServerReply = recvall(ServerSock, 9, '[ServerThread]\t') # pobierz 9 znakow - zob. SMLP manual str. 23

				if myServerReply == None:
					logger_debug.debug('[ServerThread]\t Error receiving server\'s reply header')
					ServerSock.close()
					ServerSock = reconnect(self.ip, self.port)
					continue

				logger_debug.debug('[ServerThread]\t Received server\'s reply header')
				# dowiedz sie jak dluga jest reszta 
				msgLen = struct.unpack('<H', myServerReply[7:]) # <H means litle endian ushort
				# pobierz reszte
				tempServerReply = recvall(ServerSock, msgLen[0], '[ServerThread]\t') # msgLen to tuple (krotka)

				if tempServerReply == None:
					logger_debug.debug('[ServerThread]\t Error receiving server\'s reply')
					ServerSock.close()
					ServerSock = reconnect(self.ip, self.port)
					continue
				else:
					myServerReply += tempServerReply
					logger_debug.debug('[ServerThread]\t Received server reply')
					break # wszystko sie udalo, mozna isc dalej

			logger_debug.debug('[ServerThread]\t' + SLMP.binary_array2string(myServerReply))
			serverReply = myServerReply

			waitingForResponse.release()	


#definicja klasy watkow klientow
class ClientThread (threading.Thread):

	def __init__(self, ClientSock):
		threading.Thread.__init__(self)
		self.ClientSock = ClientSock

	def run(self):
		global occupied, scadaMessage, serverReply
		while True:
			logger_debug.debug('[ClientThread]\t Waitng for message')
			time.sleep(1.5)
			myScadaMessage = recvall(self.ClientSock, 9, '[ClientThread]\t')

			if myScadaMessage == None: # jesli nie udalo sie odebrac chociaz naglowka, wyjdz
			 	logger_debug.debug('[ClientThread]\t No message has been received - exiting')
				self.ClientSock.close()
				return

			logger_debug.debug('[ClientThread]\t Receiving message') 
			msgLen = struct.unpack('<H', myScadaMessage[7:])
			tempScadaMessage = recvall(self.ClientSock, msgLen[0], '[ClientThread]\t') # tu tez potencjalnie moga byc bledy

			if tempScadaMessage == None: 
			 	logger_debug.debug('[ClientThread]\t Didnt receive full message - exiting')
				self.ClientSock.close()
				return

			logger_debug.debug('[ClientThread]\t Received full message from SCADA')
			myScadaMessage += tempScadaMessage
			logger_debug.debug('[ClientThread]\t' + SLMP.binary_array2string(myScadaMessage))

			notEmpty.acquire()

			while occupied == 1:
				notEmpty.wait()
			occupied = 1
			notEmpty.release()

			scadaMessage = myScadaMessage

			waitngForMessage.release()
			logger_debug.debug('[ClientThread]\t Waiting for response from server')
			time.sleep(1.5)

			waitingForResponse.acquire()
			myServerReply = serverReply

			notEmpty.acquire()
			occupied = 0
			notEmpty.notify()
			notEmpty.release()

			try:
				retVal = self.ClientSock.sendall(myServerReply)

			except Exception:
				logger_debug.debug('[ClientThread]\t Exception raised by sendall - unlikely when running on the same PC')

			if retVal == None: # sendall udane
				logger_debug.debug('[ClientThread]\t Reply sent to SCADA')
				logger_info.info('\n' + 'SCADA_IP\t  -->\t\t  ' + str(SCADA_IP) + '\n' +
					'PLC_SERVER_IP\t -->\t\t  ' + str(PLC_SERVER_IP) + '\n' + 
					'SCADA_PORT\t  -->\t  ' + str(SCADA_PORT) + '\n' +
					'SCADA_MESSAGE\t  -->\t  ' + repr(scadaMessage) + '\n' +
					'SERVER_PORT\t  -->\t  ' + str(PLC_SERVER_PORT) + '\n' + 
					'SERVER_REPLY\t  -->\t  ' + repr(serverReply) + '\n' +
					'********************************************************************************************')
			else:
				logger_debug.debug('[ClientThread]\t SCADA left without getting a reply - exiting')
				return


try:
	# konfiguracja srodowiska: 
	if  len(sys.argv) < 2:
		logger_debug.debug("[ERROR] Please write a path to configuration file")
		quit()

	#tworzy foldery do logow
	if not os.path.exists('log/messages'):
    		os.makedirs('log/messages')
		os.makedirs('log/test')

	configure(sys.argv[1])

	#logger configuration file
	logging.config.fileConfig(LOGGER_CONFIG)

	# create logger
	logger_info = logging.getLogger('IMessage')
	logger_debug = logging.getLogger('DMessage')

	# tworzenie watku serwera
	serverThread = ServerThread(PLC_SERVER_IP, PLC_SERVER_PORT)
	serverThread.daemon = True		# watek zostanie zamkniety/umrze kiedy zginie watek glowny
	serverThread.start()
	
	# tworzenie watkow klientow
	clientThreadsCollection = []
	ClientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	ClientSock.bind((SCADA_IP, SCADA_PORT)) #socket.gethostname() for IP does not work
	ClientSock.listen(1)
	logger_debug.debug("Proxy is waiting for connection on port " + str(SCADA_PORT))

	#petla glowna dzialania proxy
	while True:
		NewClientSock = ClientSock.accept()[0]
		NewClientSock.settimeout(1)
		newThread = ClientThread(NewClientSock) 
		clientThreadsCollection.append(newThread)
		newThread.daemon = True
		newThread.start()
	
except KeyboardInterrupt:	
	logger_debug.debug('Proxy ended it\'s work. Bye!')
