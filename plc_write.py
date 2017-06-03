#!/usr/bin/python2

from struct import *
import socket
import SLMP
import sys
import time

PLC_IP = '127.0.0.1'
PLC_PORT = 1444 #1280
BUFFER_SIZE = 100

def binary_array2string(data):
    s = ""
    for byte in data:
	s = s + str(hex(ord(byte))) + " "
    return s;

if len(sys.argv)<3:
    print "Two parameters needed - register number and value (both decimal, 16bit register)"
    exit();

numArg1 = int(sys.argv[1])
numArg2 = int(sys.argv[2])
print "numArg1", numArg1	
print "numArg2", numArg2


while 1:
	time.sleep(2)
	message = SLMP.prepare_device_write_one_word_message(int(numArg1), 0xa8,int(numArg2))
	print "numArg1", numArg1	
	print "numArg2", numArg2
	numArg1 = numArg1 + 1 
	numArg2 = numArg2 + 1 
	
	print "Request packet"
	print binary_array2string(message)

	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((PLC_IP, PLC_PORT))
	s.send(message)

	response = s.recv(BUFFER_SIZE)

	print "Response packet"
	print binary_array2string(response)

	s.close()
