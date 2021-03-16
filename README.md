# AIS dispatcher

Takes AIS data from a serial or UDP input.

Starts threaded TCP server that accepts connections to forward AIS data on to.

Dispatches AIS data in UDP payloads to list of destinations.*

*Note that this can include localhost, which allows other tools run on the same machine (for example, the aishub dispatcher) to read this as input.

## Prerequisits

python3

...and the following pip3 modules:

`sudo pip3 install pyserial click`

## Usage

Example:
`./dispatcher.py --host 192.168.1.4 1371 --serial-port /dev/serial0`

Here the IP is the address of the interface on the local machine from which to serve (in this example, using port 1371).

The complete list of arguments are given by the --help.

```
Usage: dispatcher.py [OPTIONS]

Options:
  --host <TEXT INTEGER>...      Host <ip> <port> - the local interface to
                                attach server to  [required]
  --serial-port TEXT            Serial device e.g. /dev/serial0
  --serial-rate INTEGER         Serial port baudrate (default 38400)
  --udp-src <TEXT INTEGER>...   UDP source <ip> <port> (typically same IP as
                                --host but with a different port to listen on)
  --udp-dest <TEXT INTEGER>...  UDP forward destination <ip> <port>
  --help                        Show this message and exit.
```

For multiple UDP destinations, create file *upd_destinations.json* in the same directory as the script with contents like this:

```
[
  ["192.168.1.3", 1371],
  ["192.168.1.11", 1371],
  ["data.aishub.net", 1235],
  ["localhost", 1371]
]
```

Note that this is overridden by using --udp-dest on the command line.

The dispatcher can be cleanly stopped with ctrl-c or `sudo kill -s SIGINT <pid>`

## As a systemd service

Typically a systemd service would look like this:

```
[Unit]
Description=AIS Dispatcher
After=network-online.target
Wants=network-online.target systemd-networkd-wait-online.service

StartLimitIntervalSec=500
StartLimitBurst=5

[Service]
Restart=on-failure
RestartSec=5s

StandardOutput=journal+console
ExecStart=/usr/bin/python3 /home/pi/AIS/dispatcher.py --host 192.168.1.4 1371 --serial-port /dev/serial0

[Install]
WantedBy=multi-user.target
```

For example - put this in file */usr/lib/systemd/system/ais-dispatcher.service* and enable with:

```
sudo systemctl enable /usr/lib/systemd/system/ais-dispatcher.service
sudo systemctl start ais-dispatcher.service
```

Status of the started unit can then be checked with either:
```
systemctl status ais-dispatcher.service
journalctl -u ais-dispatcher.service
```

At this point you should be able to get an AIS stream just by telnetting to port 1371 on the configured interface.
