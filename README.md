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
  --host <TEXT INTEGER>...      Host <ip> <port>  [required]
  --serial-port TEXT            Serial port device
  --serial-rate INTEGER         Serial port baudrate
  --udp-src <TEXT INTEGER>...   UDP source <ip> <port>
  --udp-dest <TEXT INTEGER>...  UDP destination <ip> <port>
  --help                        Show this message and exit.
```

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
