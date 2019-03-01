# Standard library imports
import argparse
import logging
import sys

# Third party imports
import serial
import socket
import base64
import time
from Crypto.Cipher import AES
from Crypto import Random

#Global Flags
fail_fast = False

# Client for Mega communications
class RpiMegaClient:
    def __init__(self, terminal="/dev/ttyAMA0", baudrate=115200):
        try:
            self.port = serial.Serial(terminal, baudrate, timeout=3)
            self.port.open()
            if self.port.is_open:
                logging.info("Serial port is open")
        except serial.SerialException as e1:
            logging.info("An error occurred, system exiting")
            logging.debug("Attempted to open Serial port on /dev/ttyAMA0, baudrate:" + str(baudrate) + str(e1))
            if fail_fast:
                sys.exit()
        else:
            logging.info("Successfully opened serial port:", terminal, "w/ baud rate:", baudrate)

    def send_message(self, message):
        self.port.write((message + '\n').encode())

    def read_message(self):
        a = 1
        while True:
            time.sleep(1)
            print("Read: ", self.port.read(1).decode("utf-8"))
            print("In waiting: ", self.port.in_waiting)
            print("Spacer ", a)
            a += 1
        '''message = ""
        string_complete = False
        while True:
            if string_complete:
                return message
            while self.port.in_waiting:
                ch = self.port.read()
                message += ch
                if ch == '\n':
                    string_complete = True
                    break'''

    def three_way_handshake(self):
        self.send_message("hello")
        logging.info("Three-way-handshake: hello sent")
        message = ""
        while message != "ack":
            logging.info("Three-way-handshake: waiting for ack")
            time.sleep(2)
            message = self.read_message()
        self.send_message("ack")
        logging.info("Three-way-handshake: complete")


# Client for Server communication
class RpiEvalServerClient:
    """Opens connection to remote host socket, provides a send API"""
    def __init__(self, target_ip, target_port, key):
        self.key = key
        self.sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        try:
            logging.info("Attempting to connect to evaluation server ...")
            self.sock.connect((target_ip, int(target_port)))
        except OSError as e1:
            logging.info("An error occurred, system exiting")
            logging.debug("Attempted to connect to: " + target_ip + "(" + target_port + ")" + '\n' + str(e1))
            if fail_fast:
                sys.exit()
        except ValueError as e2:
            logging.info("An error occurred, system exiting")
            logging.debug("Attempted to connect to: " + target_ip + "(" + target_port + ")" + '\n' + str(e2))
            if fail_fast:
                sys.exit()
        else:
            logging.info("Successfully connected to:" + target_ip + "(" + target_port + ")")

    def send_message(self, message):
        self.sock.sendall(encode_encrypt_message(message, self.key))


def encode_encrypt_message(message, key):
    """Pads message to nearest multiple of 16 bytes, encrypt with AES, then encoded in base64"""
    bytes_for_padding = 16 - (len(message) % 16)
    padding_str = "0" * bytes_for_padding
    padded_msg = (message + padding_str).encode()
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key.encode(), AES.MODE_CBC, iv)
    msg = base64.b64encode(iv + cipher.encrypt(padded_msg))
    return msg


def format_results(action, voltage, current, power, cumulative_power):
    """Format results to: ‘#action | voltage | current | power | cumulativepower|’"""
    return '#' + action + '|' + str(voltage) + '|' + str(current) + '|' + str(power) + '|' + str(cumulative_power) + '|'


def fetch_script_arguments():
    """Fetches command line arguments, all are required"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--target_ip', help="Target Server IP Address", required=True)
    parser.add_argument('-p', '--target_port', help="Target Server TCP port number", required=True)
    parser.add_argument('-k', '--key', help="16 / 24 / 32 character key", required=True)
    parser.add_argument('-b', '--baud_rate', help="Serial Baud Rate (4800/9600/14400/19200/28800/38400/57600/115200)"
                        , required=True)
    parser.add_argument('-l', '--logging_mode', help="Enables debug printing (debug/none)", required=True)
    return parser.parse_args()


def interactive_mode():
    """Interactive mode intended for convenient testing"""
    while True:
        print("Enter Mode: (1)Comms to server, (2)Comms to arduino")
        mode = input()

        # Socket communication to Server
        if mode == "1":
            server_client = RpiEvalServerClient()
            print("Relay password to sever:", server_client.key, ", and remember to wait for move prompt on GUI!")
            while True:
                print("Enter input: action voltage current power cumulative_power // or E to exit")
                message = input()
                if message == "E":
                    break
                else:
                    server_client.send_message(format_results(*message.split()))

        # Serial communication to Mega
        elif mode == "2":
            mega_client = RpiMegaClient()
            while True:
                print("Functionality to test: (1)Send One, (2)Receive One, (3)Initiate Handshake, (E)exit")
                mode = input()

                # Send Mode
                if mode == "1":
                    print("Input message to send:")
                    message = input()
                    mega_client.send_message(message)

                # Receive Mode
                elif mode == "2":
                    print("Enter any key to readline:")
                    input()
                    print("Waiting for message:")
                    while True:
                        mega_client.read_message()

                # Handshake Mode
                elif mode == "3":
                    print("Enter any key to initiate handshake")
                    input()
                    mega_client.three_way_handshake()

                # Exit
                elif mode == "E":
                    break


if __name__ == "__main__":
    args = fetch_script_arguments()

    # Setup & Configuration
    logging.basicConfig(level=logging.DEBUG if args.logging_mode == "debug" else logging.INFO)
#    server_client = RpiEvalServerClient(target_ip=args.target_ip, target_port=args.target_port, key=args.key)
#    mega_client = RpiMegaClient(baudrate=args.baud_rate)

    # Launch mode loops
    interactive_mode()
