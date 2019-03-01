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
fail_fast = False  # No error recovery if true. System exits immediately on exception.

# Client for Mega communications
class RpiMegaClient:
    def __init__(self, terminal="/dev/ttyAMA0", baudrate=115200):
        try:
            self.port = serial.Serial(terminal, baudrate, timeout=3)
            if self.port.is_open:
                logging.info("Serial port already open")
            else:
                self.port.open()
                logging.info("Successfully opened serial port:", terminal, "w/ baud rate:", baudrate)
        except serial.SerialException as e1:
            logging.debug("Error occured attempting to open Serial port on ", terminal, str(baudrate), str(baudrate))
            logging.debug("System error details:\n", str(e1))
            if fail_fast:
                sys.exit()

    def send_message(self, message):
        self.port.write((message + '\n').encode("utf-8"))
        return message

    def read_message(self):
        return self.port.read_until().decode("utf-8")

    def three_way_handshake(self):
        while True:
            self.send_message("H")
            logging.info("H sent")
            logging.info("Sleep for 1 second")
            time.sleep(1)
            if self.read_message() == "A\n":
                logging.info("A received")
                self.send_message("A")
                logging.info("A sent")
                logging.info("Entering sleep for 3 seconds")
                time.sleep(3)
                self.port.reset_input_buffer()
                logging.info("Buffer flushed")
                logging.info("Handshake complete")
                break


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
        # No error detection/handling implemented for now
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


def interactive_mode(args):
    """Interactive mode intended for convenient testing"""
    while True:
        print("Component to test: (1)Comms to server, (2)Comms to arduino (3)ML prediction")
        mode = input()

        # Socket communication to Server
        if mode == "1":
            server_client = RpiEvalServerClient(args.target_ip, args.target_port, args.key)
            print("Relay password to sever:", server_client.key, ", and wait for move prompt on GUI")
            while True:
                print("Enter input: action voltage current power cumulative_power // or E to exit")
                message = input()
                if message == "E":
                    break
                else:
                    server_client.send_message(format_results(*message.split()))

        # Serial communication to Mega
        elif mode == "2":
            mega_client = RpiMegaClient(baudrate=args.baud_rate)
            while True:
                print("Functionality to test: (1)Send 1 message, (2)Repeat read & print, (3)3-way-Handshake, (E)exit")
                mode = input()

                # Send 1 message
                if mode == "1":
                    print("Input message to send:")
                    print("Message sent: ", mega_client.send_message(input()))  # Note that input() strips newline chars

                # Repeat read & print
                elif mode == "2":
                    print("Enter any key to begin (keyboard interrupt required to exit this mode):")
                    input()
                    while True:
                        print("Waiting for message (3 sec timeout):")
                        print("Message received: ", mega_client.read_message())

                # Handshake Mode
                elif mode == "3":
                    print("Enter any key to initiate handshake mode:")
                    input()
                    mega_client.three_way_handshake()

                # Exit
                elif mode == "E":
                    break


def evaluation_mode(mega_client, server_client):
    # Loop Vars
    connection_unstable = True
    while True:
        # Blocks till handshake successful
        if connection_unstable:
            mega_client.three_way_handshake()

        



if __name__ == "__main__":
    args = fetch_script_arguments()
    logging.basicConfig(level=logging.DEBUG if args.logging_mode == "debug" else logging.INFO)
    mode = 0

    while mode != "1" and mode != "2":
        print("Select mode: (1)Interactive(Separate Testing), (2)Evaluation")
        mode = input()

    # Mode loops
    if mode == "1":
        interactive_mode(args)
    elif mode == "2":
        server_client = RpiEvalServerClient(args.target_ip, args.target_port, args.key)
        mega_client = RpiMegaClient(baudrate=args.baud_rate)
        evaluation_mode(mega_client, server_client)
