#!/usr/bin/python3
from socket import socket, AF_INET, SOCK_DGRAM, timeout
from serial import Serial, SerialException
from threading import Thread, Event
from queue import Queue, Empty
from socketserver import BaseRequestHandler, ThreadingMixIn, TCPServer
from time import sleep
from os import path
import signal # to catch ctrl-c or SIGINT
import click # for CLI args
import json
import sys

# this class handles inbound TCP connections and is threaded
# IE one per opened socket
class ThreadedAISTCPHandler(BaseRequestHandler):
    def setup(self):
        print("New client, creating queue.")
        # subscribe to input messages
        self.q = Queue()
        self.server.subscribers.append(self.q)

    def handle(self):
        try:
            while not self.server.stop_event.is_set():
                try:
                    data = self.q.get(timeout=1)
    #                print("Sending", data)
                    self.request.sendall(data)
                    self.q.task_done()
                except Empty:
                    # this is only to allow regular checking of stop_event
                    pass
        except BrokenPipeError as e:
            print("Connection error:", e)

    def finish(self):
        print("Lost client, destroying queue.")
        self.server.subscribers.remove(self.q)

# this overloads the ThreadedTCPServer so that an additional argument can be passed in,
# in our case the subscriber queue list and stop event
class ThreadedTCPServer(ThreadingMixIn, TCPServer):
    def __init__(self, host_port_tuple, streamhandler, subscribers, stop_event):
        super().__init__(host_port_tuple, streamhandler)
        self.subscribers = subscribers
        self.stop_event = stop_event

# listen to a serial port and send any data to all subscribers
def serialListener(subscribers, stop_event, serial_port='/dev/serial0', serial_rate=38400):
    print("Listening to serial device", serial_port)
    try:
        with Serial(serial_port, serial_rate, timeout=1) as ser:
            while not stop_event.is_set():
                data = ser.readline()
                if data:
                    print("SER:", data.decode('utf-8').rstrip())
                    [q.put(data) for q in subscribers]
    except SerialException as e:
        print("Serial exception:", e)
        pass

# listen to a UDP port and send any data to all subscribers
def udpListener(subscribers, stop_event, host):
    print(f"Listening to UDP on {host[0]} port {host[1]}")
    # Create a UDP input socket
    with socket(AF_INET, SOCK_DGRAM) as s:
        # Bind the socket to the port
        s.bind(host)
        s.settimeout(1)
        while not stop_event.is_set():
            try:
                data, address = s.recvfrom(4096)
                print("UDP:", data.decode('utf-8').rstrip())
                [q.put(data) for q in subscribers]
            except timeout:
                # this is only to allow regular checking of stop_event
                pass

# subscribe to input AIS streams and send out to UDP destination(s)
def udpDispatcher(server, destinations, subscribers, stop_event):
    # subscribe
    q = Queue()
    subscribers.append(q)

    try:
        # create a UDP socket to send with
        with socket(AF_INET, SOCK_DGRAM) as s:

            while not stop_event.is_set():
                try:
                    data = q.get(timeout=1)
                    [s.sendto(data, host) for host in destinations]
                    q.task_done()
                except Empty:
                    # timeout to check status of stop_event periodically
                    pass
            # unsubscribe
            subscribers.remove(q)

    except OSError as e:
        print("udpDispatcher failed:", e)

def signal_handler(sig, frame):
    pass

@click.command()
@click.option('--host', required=True, type=click.Tuple([str, int]), default=('',0), help='Host <ip> <port> - the local interface to attach server to')
@click.option('--serial-port', type=str, default='', help='Serial device e.g. /dev/serial0')
@click.option('--serial-rate', type=int, default=38400, help='Serial port baudrate (default 38400)')
@click.option('--udp-src', type=click.Tuple([str, int]), default=('',0), help='UDP source <ip> <port> (typically same IP as --host but with a different port to listen on)')
@click.option('--udp-dest', type=click.Tuple([str, int]), default=('',0), help='UDP forward destination <ip> <port>')
def dispatcher(
    host,
    serial_port,
    serial_rate,
    udp_src,
    udp_dest
    ):

    if not host[0]:
        print('--host argument required')
        exit(1)

    udp_destinations = []
    # UDP destinations
    if udp_dest[0]:
        udp_destinations = [ udp_dest ]
    else:
        try:
            # look for file in the script's location
            with open(path.realpath(sys.path[0])+'/udp_destinations.json') as json_file:
                config = json.load(json_file)
                for dest in config:
                    print(f"Adding udp destination {dest[0]} port {dest[1]}")
                    udp_destinations.append(tuple(dest))
        except FileNotFoundError:
            print("udp_destinations.json file not detected")

    # these queues exist between listeners (either serial or UDP input threads) and dispatchers (UDP outputs, or TCP outputs)
    subscribers = []

    # used to signal to listener thread to stop running
    stop_event=Event()
    
    # list of listener threads
    threads = []

    if udp_src[0]:
        threads.append( Thread(target=udpListener, args=(subscribers, stop_event, udp_src)) )

    if serial_port:
        threads.append( Thread(target=serialListener, args=(subscribers, stop_event, serial_port, serial_rate)) )

    threads.append( Thread(target=udpDispatcher, args=(host, udp_destinations, subscribers, stop_event)) )

    print(f"Starting TCP server on {host[0]} port {host[1]}")
    try:
        server = ThreadedTCPServer(host, ThreadedAISTCPHandler, subscribers, stop_event)
        ip, port = server.server_address

        # start a thread with the server -- that thread will then start one
        # more thread for each request
        server_thread = Thread(target=server.serve_forever)
        # exit the server thread when context is lost (end of program)
        server_thread.daemon = True
        server_thread.start()

    except (OSError) as e:
        print(e)
        exit(1)

    print("Starting any listeners and dispatchers...")
    # kick off listener threads
    for thread in threads:
        # exit the threads when context is lost (end of program)
        thread.daemon = True
        thread.start()

    signal.signal(signal.SIGINT, signal_handler)
    print('Press Ctrl+C or SIGINT to stop')

    # this will wait until the handler exits
    signal.pause()
    server.shutdown()
    stop_event.set()

    print("Waiting for threads to stop...")
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    dispatcher()
