import socket
import base64
import serial
import sys
import time
from Crypto.Cipher import AES
from Crypto import Random

# global
targetServerIp = "127.0.0.1"
targetServerPort = 8888
secretKey = "1616161616161616"

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
            self.port = serial.Serial(terminal, baudrate=baudrate, timeout=timeout)
        except serial.SerialException as se:
            print(se)
        else:
            print("Successfully opened serial port:", terminal, "w/ baud rate:", baudrate)

    def send_message(self, message):
        """Prepends CR+LF to message, before writing it to the serial port"""
        self.port.write("\r\n" + message)

    def read_message(self):
        """Returns line read up till carriage return or empty char"""
        rv = ""
        while True:
            ch = self.port.read()
            rv += ch
            if ch == '\r' or ch == '':
                return rv

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
    padded_msg = message + padding_str
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
    rpi_socket_client = RpiSocketClient()

    # Initialization (2) - Connect to Arduino
    rpi_arduino_client = RpiArduinoClient()
    # rpi_arduino_client.three_way_handshake()

    while True:
        pass
    # Data Reading

    # Data Processing

    # Reporting to server
