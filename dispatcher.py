#!/usr/bin/python3
from socket import socket, AF_INET, SOCK_DGRAM
from serial import Serial
from threading import Thread, Event
from queue import Queue
from socketserver import BaseRequestHandler, ThreadingMixIn, TCPServer
from time import sleep
import click # for CLI args

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
            while True:
                data = self.q.get()
#                print("Sending", data)
                self.request.sendall(data)
                self.q.task_done()
        except BrokenPipeError as e:
            print("Connection error:", e)

    def finish(self):
        print("Lost client, destroying queue.")
        self.server.subscribers.remove(self.q)

# this overloads the ThreadedTCPServer so that an additional argument can be passed in,
# in our case the subscriber queue list
class ThreadedTCPServer(ThreadingMixIn, TCPServer):
    def __init__(self, host_port_tuple, streamhandler, subscribers):
        super().__init__(host_port_tuple, streamhandler)
        self.subscribers = subscribers

# listen to a serial port and send any data to all subscribers
def serialListener(subscribers, stop_event, serial_port='/dev/serial0', serial_rate=38400):
    # give the main process time to set stop_event if port isn't available
    sleep(0.5)

    print("Listening to serial device", serial_port)
    ser = Serial(serial_port, serial_rate)

    while not stop_event.is_set():
        data = ser.readline()
        print("SER:", data.decode('utf-8').rstrip())
        [q.put(data) for q in subscribers]

# listen to a UDP port and send any data to all subscribers
def udpListener(subscribers, stop_event, host):
    # give the main process time to set stop_event if port isn't available
    sleep(0.5)

    print("Listening to UDP on", host)
    # Create a UDP input socket
    s = socket(AF_INET, SOCK_DGRAM)
    # Bind the socket to the port
    s.bind(host)

    while not stop_event.is_set():
        data, address = s.recvfrom(4096)
        print("UDP:", data.decode('utf-8').rstrip())
        [q.put(data) for q in subscribers]

# subscribe to input AIS streams and send out to UDP destination(s)
def udpDispatcher(server, destinations, subscribers, stop_event):
    # give the main process time to set stop_event if port isn't available
    sleep(0.5)

    # subscribe
    q = Queue()
    subscribers.append(q)

    # create a UDP socket to send with
    s = socket(AF_INET, SOCK_DGRAM)

    # bind the socket to the UDP port
    s.bind(server)

    while not stop_event.is_set():
        data = q.get()
        [s.sendto(data, host) for host in destinations]
        q.task_done()

    # unsubscribe
    subscribers.remove(q)

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

    # UDP destinations
    if udp_dest[0]:
        udp_destinations = [ udp_dest ]
    else:
        # todo, read from config file instead of hardcode
        udp_destinations = [
            ('192.168.1.3', 1371),
            ('192.168.1.11', 1371),
            ('localhost', 1371)
        ]

    # these queues exist between listeners (either serial or UDP input threads) and dispatchers (UDP outputs, or TCP outputs)
    subscribers = []

    # used to signal to listener thread to stop running
    stop_event=Event()
    
    print("Starting listeners...")
    if udp_src[0]:
        listener = Thread(target=udpListener, args=(subscribers, stop_event, udp_src))
        listener.daemon = True
        listener.start()

    if serial_port:
        listener = Thread(target=serialListener, args=(subscribers, stop_event, serial_port, serial_rate))
        listener.daemon = True
        listener.start()

    print("Starting UDP dispatcher...")
    dispatcher = Thread(target=udpDispatcher, args=(host, udp_destinations, subscribers, stop_event)) 
    dispatcher.start()

    print("Starting TCP server on", host)
    try:
        server = ThreadedTCPServer(host, ThreadedAISTCPHandler, subscribers)
        with server:
            ip, port = server.server_address

            # start a thread with the server -- that thread will then start one
            # more thread for each request
            server_thread = Thread(target=server.serve_forever)
            # exit the server thread when the main thread terminates
            server_thread.daemon = True
            server_thread.start()
            while True:
                sleep(10)

    except (OSError, KeyboardInterrupt) as e:
        print(e)
        # stop threads!
        stop_event.set()

if __name__ == "__main__":
    dispatcher()
