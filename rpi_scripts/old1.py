import socket
import base64
import serial
import sys
import time
from Crypto.Cipher import AES
from Crypto import Random

# global
targetServerIp = "127.0.0.1"
targetServerPort = 1337
secretKey = b"1616161616161616"

# RPi Socket client
class RpiSocketClient:
    """Opens connection to remote host socket, provides a send API"""
    def __init__(self):
        self.sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        try:
            print("Attempting to connect to evaluation server ...")
            self.sock.connect((targetServerIp, targetServerPort))
        except (OSError, ValueError):
            print("OS/Value Error occurred while trying to connect to:", targetServerIp, "(", targetServerPort, ")")
        else:
            print("Successfully connected to:", targetServerIp, "(", targetServerPort, ")")

    def send_message(self, message):
        self.sock.sendall(encode_encrypt_message(message))


# RPi client for Arduino
class RpiArduinoClient:
    def __init__(self, terminal="/dev/ttyAMA0", baudrate=115200, timeout=3.0):
        try:
            self.port = serial.Serial(terminal, baudrate=115200, timeout=3.0)
            self.port.open()
            if self.port.is_open:
                print("Serial port is open")
        except serial.SerialException as se:
            print(se)
        else:
            print("Successfully opened serial port:", terminal, "w/ baud rate:", baudrate)

    def send_message(self, message):
        """Prepends CR+LF to message, before writing it to the serial port"""
        self.port.write(message.encode())

    def read_message(self):
        """Returns line read up till carriage return or empty char"""
        return self.port.readline()
        
        '''
        rv = ""
        while True:
            ch = self.port.read()
            rv += ch
            if ch == '\r' or ch == '' or ch =='\n':
                return rv
        '''
    def three_way_handshake(self):
        self.send_message("hello")
        print("Handshake: hello sent")
        rv = ""
        while rv != "ack":
            print("Handshake: waiting for ack")
            time.sleep(0.5)
            rv = self.read_message()
        self.send_message("ack")
        print("Handshake: complete")


def encode_encrypt_message(message):
    """Pads message to nearest multiple of 16 bytes, encrypt with AES, then encoded in base64"""
    bytes_for_padding = 16 - (len(message) % 16)
    padding_str = "0" * bytes_for_padding
    padded_msg = (message + padding_str).encode()
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(secretKey, AES.MODE_CBC, iv)
    msg = base64.b64encode(iv + cipher.encrypt(padded_msg))
    return msg


def format_results(action, voltage, current, power, cumulative_power):
    """Format results to: ‘#action | voltage | current | power | cumulativepower|’"""
    return '#' + action + '|' + str(voltage) + '|' + str(current) + '|' + str(power) + '|' + str(cumulative_power)

if __name__ == "__main__":
    # Control Flags

    # Initialization (1) - Connect to Eval Server
    # rpi_socket_client = RpiSocketClient()

    # Initialization (2) - Connect to Arduino
    # rpi_arduino_client = RpiArduinoClient()
    # rpi_arduino_client.three_way_handshake()

    while True:
        print("Enter Mode: (1)Comms to server, (2)Comms to arduino")
        mode = input()
        if mode == "1":
            rpi_socket_client = RpiSocketClient()
            print("Relay password to sever: 16161616161616")
            print("Wait for server prompt\n")
            while True:
                print("Enter input: action voltage current power cumulative_power")
                test = input()
                rpi_socket_client.send_message(format_results(*test.split()))
        elif mode == "2":
            print("Enter any key to start serial port")
            input()
            rpi_arduino_client = RpiArduinoClient()
            while True:
                print("Functionality to test: (1)Send One, (2)Receive One, (3)Initiate Handshake, (E)exit")
                mode = input()
                if mode == "1":
                    while True:
                        print("Input message to send:")
                        message = input()
                        if message == "E":
                            break
                        else:
                            print("Message Sent:", message)
                            rpi_arduino_client.send_message(input())
                elif mode == "2":
                    while True:
                        print("Enter any key to receive:")
                        message = input()
                        if message == "E":
                            break
                        else:
                            print("Waiting for data")
                            print(rpi_arduino_client.read_message())
                elif mode == "3":
                    while True:
                        print("Enter any key to initiate handshake")
                        input()
                        rpi_arduino_client.three_way_handshake()

    # Data Reading

    # Data Processing

    # Reporting to server
