#!/usr/bin/python3
from socket import socket, AF_INET, SOCK_DGRAM
from serial import Serial

# if serial module is missing then: sudo pip3 install pyserial

# this machine's interface to bind to
SERVER=('192.168.1.4', 5001)

# input serial port device
INPUT = '/dev/serial0'

# UDP destinations
DESTINATIONS = [
	['192.168.1.3', 5001],
	['192.168.1.11', 5001],
	['localhost',   5001]
]

ser = Serial(INPUT, 38400)

# create a UDP socket
s = socket(AF_INET, SOCK_DGRAM)

# bind the socket to the port
s.bind(SERVER)

print("Reading serial... (ctrl-c to exit)\n")
while True:
    data = ser.readline()
    print("SER:", data)

    for host in DESTINATIONS:
#        print('Dispatching to', host)
        s.sendto(data, tuple(host))

