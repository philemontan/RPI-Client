# Standard library imports
import argparse
import logging
import sys
from enum import Enum

# Third party imports
import serial
import socket
import base64
import time
import datetime
from Crypto.Cipher import AES
from Crypto import Random
import numpy
from sklearn.externals import joblib


#Global Flags
fail_fast = True  # No error recovery if true. System exits immediately on exception.

candidates_required = 3
frame_length = 10  # 1 frame per prediction
sampling_interval = 0.05  # frames per second = frame_length / (1 / sampling interval) ==> 1 frame per second
overlap_ratio = 0.5


# Client for ML prediction, training data generation
class RpiMLClient:
    def __init__(self):
        self.model = joblib.load("trained_models/trained_model.joblib")
        pass

    # Expects frame as a list of lists, 50 rows, 12 cols
    def temp_predict(self, input_frame):
        return "cowboy"

    def predict(self, input_frame):
  #      self.model.predict(input_frame)
        return "cowboy"


# Client for Mega communications
class RpiMegaClient:
    def __init__(self, terminal="/dev/ttyAMA0", baudrate=115200):
        try:
            self.port = serial.Serial(terminal, baudrate, timeout=None)
            if self.port.is_open:
                logging.debug("Serial port already open")
            else:
                self.port.open()
                logging.info("Successfully opened serial port:" + terminal + "w/ baud rate:" + baudrate)
        except serial.SerialException as e1:
            logging.debug("Error occurred attempting to open Serial port on " + terminal + str(baudrate) + str(baudrate))
            logging.debug("System error details:\n" + str(e1))
            if fail_fast:
                sys.exit()

    def send_message(self, message):
        self.port.write((message + '\n').encode("utf-8"))
        return message

    def read_message(self):
        return self.port.read_until().decode("utf-8")  # \n is not removed

    def discard_till_sentinel(self):
        self.port.read_until()  # Discards first chunk till \n, bare read may fail on decode

    def three_way_handshake(self):
        logging.info("Entered handshake mode")
        while True:
            self.send_message("H")
            logging.debug("H sent")
            logging.debug("Sleep for 1 second")
            time.sleep(1)
            if self.read_message() == "A\n":
                logging.debug("A received")
                self.send_message("A")
                logging.debug("A sent")
                logging.debug("Entering sleep for 3 seconds")
                time.sleep(3)
                self.port.reset_input_buffer()
                logging.debug("Buffer flushed")
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
            logging.debug("An error occurred, system exiting")
            logging.debug("Attempted to connect to: " + target_ip + "(" + target_port + ")" + '\n' + str(e1))
            logging.debug(repr(e1))
            if fail_fast:
                sys.exit()
        except ValueError as e2:
            logging.debug("An error occurred, system exiting")
            logging.debug("Attempted to connect to: " + target_ip + "(" + target_port + ")" + '\n' + str(e2))
            logging.debug(repr(e2))
            if fail_fast:
                sys.exit()
        else:
            logging.info("Successfully connected to:" + target_ip + "(" + target_port + ")")

    def send_message(self, message):
        # No error detection/handling implemented for now
        self.sock.sendall(encode_encrypt_message(message, self.key))


# Enums
class Move(Enum):
    FINAL = 0
    HUNCHBACK = 1
    RAFFLES = 2
    CHICKEN = 3
    CRAB = 4
    COWBOY = 5
    RUNNINGMAN = 6
    JAMESBOND = 7
    SNAKE = 8
    DOUBLEPUMP = 9
    MERMAID = 10


class MessageType(Enum):
    MOVEMENT = "M"
    POWER = "P"


class GeneralMessageIndex(Enum):
    MESSAGE_NUMBER = 0
    MESSAGE_TYPE = 1


class MovementMessageIndex(Enum):
    LEFT_ACCEL_X = 3
    LEFT_ACCEL_Y = 4
    LEFT_ACCEL_Z = 5
    LEFT_GYRO_X = 6
    LEFT_GYRO_Y = 7
    LEFT_GYRO_Z = 8
    RIGHT_ACCEL_X = 9
    RIGHT_ACCEL_Y = 10
    RIGHT_ACCEL_Z = 11
    RIGHT_GYRO_X = 12
    RIGHT_GYRO_Y = 13
    RIGHT_GYRO_Z = 14
    CHECKSUM = 15


class PowerMessageIndex(Enum):
    VOLTAGE = 2
    CURRENT = 3
    CHECKSUM = 4


class InteractiveModeIndex(Enum):
    SERVER_COMMS = "1"
    MEGA_COMMS = "2"
    TRAINING_GROUP = "3"
    TRAINING_SOLO = "4"


class Message:
    def __init__(self, serial_number, message_type, readings):
        self.serial_number = serial_number  # String Type
        self.type = message_type  # Enum Type
        self.readings = readings  # List of floats in the order: left accel, gyro, right accel ,gyro; x,y,z


# Message Parser
class MessageParser:
    """Parses readings messages sent from the Mega, not intended for general message parsing"""
    @staticmethod
    def parse(message_string):
        message_string = message_string[1:]    # TODO; FIND OUT WHY MEGA IS PRE-PENDING 0x00
        if MessageParser.validity_check(message_string):
            logging.debug("Validity check success")

            # Reference message: "[SN,T,....,CS]\n" -- Remove: []\n, fill list of string
            message_readings = message_string[1:len(message_string)-2].split(",")
            serial_number = message_readings[0]
            message_type = message_readings[GeneralMessageIndex.MESSAGE_TYPE.value]

            # Remove Serial Number, Type, Checksum, convert remaining strings to float w/ 2 decimal points
            message_readings = [round(float(i), 2) for i in (message_readings[2:len(message_readings)-1])]

            return Message(serial_number, MessageType.MOVEMENT if message_type == MessageType.MOVEMENT.value
                           else MessageType.POWER, message_readings)
        else:
            raise Exception("Message validity check failed. Received: " + message_string)

    @staticmethod
    def validity_check(message_string):
        message_length = len(message_string)

        # String length check
        if len(message_string) < 6:
            logging.debug("message received too short")
            return False

        # Sentinel framing check
        if message_string[0] != '[' or message_string[message_length-1] != '\n' or message_string[message_length-2] != ']':
            logging.debug("Sentinel framing error")
            return False

        message_arr = message_string[1:message_length - 2].split(",")

        # Quick length check
        if len(message_arr) < 5:  # Shortest valid message: [23,P,0.2,0.3,CHECKSUM]
            logging.debug("Short message error")
            return False

        # Unknown type check
        message_type = message_arr[GeneralMessageIndex.MESSAGE_TYPE.value]
        if message_type not in [MessageType.MOVEMENT.value, MessageType.POWER.value]:
            logging.debug("Invalid message type error:" + message_type)
            return False

        # Number of elements check
        if message_type == MessageType.MOVEMENT.value and len(message_arr) != 15:
            logging.debug("Incorrect number of elements error (movement message)")
            return False

        if message_type == MessageType.POWER.value and len(message_arr) != 5:
            logging.debug("Incorrect number of elements error (power message)")
            return False

        # Checksum validation
        end_index = len(message_string) - 5 if message_string[len(message_string) - 5] == ',' \
            else len(message_string) - 4
        for i, c in enumerate(message_string[0:end_index]):  # checksum itself removed from the string
            checksum = ord(c) if i == 0 else (checksum ^ ord(c))
        message_arr = message_string[0:len(message_string)-2].split(',')

        if checksum != int(message_arr[len(message_arr)-1]):
            logging.debug("Checksum error-" + "Calculated:" + str(checksum))
            return False
        return True


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
        print("Component to test: (1)Comms to server, (2)Comms to arduino (3)Training - group (4) Training - solo")
        mode = input()

        # Socket communication to Server
        if mode == InteractiveModeIndex.SERVER_COMMS.value:
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
        elif mode == InteractiveModeIndex.MEGA_COMMS.value:
            global frame_length
            global sampling_interval
            mega_client = RpiMegaClient(baudrate=args.baud_rate)
            while True:
                print("Functionality to test: (1)Send one message, (2)Repeat read-print for 5 seconds, \
                        (3)Three way handshake," "(4)Speed test (E)Exit")
                mode = input()

                # Send 1 message
                if mode == "1":
                    print("Input message to send:")
                    print("Message sent: ", mega_client.send_message(input()))  # Note that input() strips newline chars

                # Repeat read & print
                elif mode == "2":
                    print("Enter any key to begin:")
                    input()
                    start_time = int(time.time())
                    while True:
                        print("Message received: ", mega_client.read_message())
                        if int(time.time()) - start_time > 5:
                            break

                # Handshake Mode
                elif mode == "3":
                    print("Enter any key to begin handshake:")
                    input()
                    mega_client.three_way_handshake()

                # Speed Test
                elif mode == "4":
                    mega_client.three_way_handshake()
                    iteration = 1
                    buffer = []
                    timings = []
                    mega_client.send_message("S")
                    print("S sent to mega")
                    while iteration < 4:
                        mega_client.port.reset_input_buffer()
                        mega_client.discard_till_sentinel()

                        start_time = int(time.time())
                        while len(buffer) != 50:
                            buffer.append(MessageParser.parse(mega_client.read_message()))
                        end_time = int(time.time())
                        timings.append(end_time-start_time)
                        iteration += 1
                        buffer.clear()
                    time_for_150 = round(float(timings[0] + timings[1] + timings[2])/150.0, 6)
                    print("Average time taken to process a data point:", time_for_150, " seconds")
                    print("Data points per second:", round(1.0/time_for_150, 2))
                    print("Exiting speed test")
                # Exit
                elif mode == "E":
                    break

        # TODO ML INTERACTIVE MODE w/ training loops -- pend testing
        elif mode == InteractiveModeIndex.TRAINING_GROUP.value:
            mega_client = RpiMegaClient(baudrate=args.baud_rate)

            # Prompt training parameters
            print("Order of moves to train: (0)Final (1)Hunchback, (2)Raffles, (3)Chicken, (4)Crab, (5)Cowboy")
            print("Enter training parameters: number of people, frames to collect per move, frame length, data points per second")
            params = [int(i) for i in input().split()]
            num_people = params[0]
            frames_per_move = params[1]
            suggested_sampling_interval = 1.0/params[3]
            if frame_length != params[2]:
                print("Warning! Temporarily overwriting default global frame length of", frame_length, "with", params[2])
                frame_length = params[2]
            if sampling_interval != suggested_sampling_interval:
                print("Warning! Temporarily overwriting default global sampling interval of", sampling_interval, "with", suggested_sampling_interval)
                print("Default global rate:", 1.0/sampling_interval, "|| Current sample rate", 1.0/suggested_sampling_interval)
                sampling_interval = suggested_sampling_interval
                
            print("Expect " + str(int((6*frames_per_move*frame_length*(2.0/3.0))/60)) + " minutes "
                  + str(int((6.0*frames_per_move*frame_length*(2.0/3.0)) % 60)) + " seconds of dancing per person")

            # Persistence setup
            time_str = str(int(time.time()))
            training_data = [[], [], [], [], [], []]  # [move_num][frame_num][data_point_num][sensor_readings_index]
            data_buffer = []  # list of reading sets

            # Handshake
            mega_client.three_way_handshake()

            # Training loop
            error_count = 0
            # One iteration one person
            for i in range(num_people):
                # One iteration one move
                for j in range(6):  # 5 moves +  End Move; Order: Final, Hunchback, Raffles, Chicken, Crab, Cowboy
                    print("Person", i, "get ready to dance move:", Move(j+1).name)  # Note: enums start from 1
                    print("Press any key to start dancing")
                    input()
                    if i == 0 and j == 0:
                        mega_client.send_message("S")  # Inform mega to start sending data

                    # Fill the data buffer; Note: frame_length, sampling_interval defined as global var
                    current_number_of_frames = 0
                    while current_number_of_frames < frames_per_move:
                        # Fill frame
                        while len(data_buffer) < frame_length:
                            try:
                                time.sleep(sampling_interval)
                                mega_client.port.reset_input_buffer()  # flush input
                                mega_client.discard_till_sentinel()  # flush is likely to cut off a message
                                message = MessageParser.parse(mega_client.read_message())
                            except Exception as err:
                                logging.debug(repr(err))
                                if fail_fast:
                                    sys.exit()
                                error_count += 1
                                if error_count == 3:
                                    error_count = 0
                                    data_buffer.clear()
                                    mega_client.three_way_handshake()
                            else:
                                error_count = 0
                                # Acknowledge the message
                                #logging.debug("Message No:" + message.serial_number + "received") # TODO reininstate ack for messages
                                #mega_client.send_message("A," + message.serial_number + "\n")
                                logging.info(
                                    "m:" + message.serial_number + "(" + message.type.value + ")=" + str(message.readings))
                                # Add readings set to buffer
                                if message.type == MessageType.MOVEMENT:
                                    data_buffer.append(message.readings)
                                else:
                                    pass  # No need for power values
                        current_number_of_frames += 1

                        # Partial buffer flush based on overlap
                        training_data[j].append(data_buffer.copy())  # training_data[0] should be empty
                        data_buffer = data_buffer[int(frame_length*(1-overlap_ratio)):]
                    data_buffer.clear()  # Full buffer flush before next move

            # Write data gathered to files
            print("Data gathering complete")
            for i in range(6):
                print("Data collected for " + Move(i+1).name + ":")
                for j in training_data[i]:
                    print(str(j))
                temp_arr = numpy.array(training_data[i].copy())
                current_date = datetime.date.today()
                timestamp = str(current_date.day) + "-" + str(current_date.month) + "-" + str(current_date.year)[2:] \
                    + "-" + time_str[5:]
                temp_file_name = "training_data/" + timestamp + "_" + Move(i+1).name + "_" + "P" + str(num_people) \
                    + "F" + str(frames_per_move) + "FL" + str(frame_length)
                numpy.save(temp_file_name, temp_arr)
                print("Data saved in:" + temp_file_name)

        elif mode == InteractiveModeIndex.TRAINING_SOLO.value:
            mega_client = RpiMegaClient(baudrate=args.baud_rate)
            mega_client.three_way_handshake()

            print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            print("Generate data (frames) for one move at a time")
            print("Parameters: L - Frame length, X - Number of frames, R - Overlap Ratio")
            print("Relation: X frames require L+(X-1)(1-R)(L) data points => we save on roughly (R*100)% data points")
            print("--Autosaves every 100 frames => ~100s for frame length of 20")
            print("--System max data points per second is ~20 => 0.05s sampling interval")
            print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n")
            print("Move numbers:(0)FINAL, (1)HUNCHBACK, (2)RAFFLES, (3)CHICKEN, (4)CRAB, (5)COWBOY, (6)RUNNINGMAN")
            print("Enter: move number, frame length, sampling interval")

            params = input().split()
            input_move_number = int(params[0])
            input_frame_length = int(params[1])
            input_sampling_interval = round(float(params[2]), 2)

            if input_frame_length != frame_length:
                print("Warning! Temporarily overwriting default global frame length of", frame_length, "with", input_frame_length)
                frame_length = input_frame_length
            if sampling_interval != input_sampling_interval:
                print("Warning! Temporarily overwriting default global sampling interval of", sampling_interval, "with", suggested_sampling_interval)
                sampling_interval = input_sampling_interval
            else:
                print("No change to default sample interval of", sampling_interval)

            mega_client.send_message("S") # Inform mega to start sending data
            print("-\nPrepare to dance move:", Move(input_move_number).name, "(press any key to start dancing -- Ctrl + C to interrupt)")
            input()
            mega_client.port.reset_input_buffer()
            mega_client.discard_till_sentinel()

            # Persistence setup
            current_date = datetime.date.today()
            time_str = str(int(time.time()))
            data_buffer = [] # List of data points
            training_data = [] # List of frames
            session_chunk_number = 0

            try:
                while True:
                    while len(data_buffer) < frame_length:
                        if sampling_interval > 0:
                            time.sleep(sampling_interval)
                            mega_client.port.reset_input_buffer()
                            mega_client.discard_till_sentinel()
                        message = MessageParser.parse(mega_client.read_message()) # TODO error correction if fail to parse
                        logging.info("m:" + message.serial_number + "(" + message.type.value + ")=" + str(message.readings))
                        # Add readings set to buffer
                        if message.type == MessageType.MOVEMENT:
                            data_buffer.append(message.readings)
                        else:
                            pass  # No need for power values
                    training_data.append(data_buffer.copy())
                    data_buffer = data_buffer[int(frame_length*(1-overlap_ratio)):]  # Partial buffer flush

                    # Autosave
                    if len(training_data) == 50:
                        temp_arr = numpy.array(training_data.copy())
                        timestamp = str(current_date.day) + "-" + str(current_date.month) + "-" + str(current_date.year)[2:]\
                            + "-" + time_str[5:]
                        temp_file_name = "training_data/" + timestamp + "_" + Move(input_move_number).name\
                            + "L" + str(frame_length) + "SI" + str(input_sampling_interval) + "R" + str(overlap_ratio)\
                            + "(" + str(session_chunk_number) + ")"
                        numpy.save(temp_file_name, temp_arr)
                        training_data.clear()
                        session_chunk_number += 1
                        print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
                        print("File generated:", temp_file_name)
                        print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")

            except KeyboardInterrupt:
                print("Session manually interrupted")
                time_str = str(int(time.time()))
                temp_arr = numpy.array(training_data.copy())
                timestamp = str(current_date.day) + "-" + str(current_date.month) + "-" + str(current_date.year)[2:]\
                        + "-" + time_str[5:]
                temp_file_name = "training_data/" + timestamp + "_" + Move(input_move_number).name\
                        + "L" + str(frame_length) + "SI" + str(input_sampling_interval) + "R" + str(
                        overlap_ratio) + "(" + str(session_chunk_number) + "_incomplete" + ")"
                numpy.save(temp_file_name, temp_arr)
                print("Remaining data saved as", temp_file_name)
                print("System exiting")
                sys.exit(0)


def evaluation_mode(mega_client, server_client, ml_client):
    # Loop Vars
    temp_cumulative_power = 0.0
    evaluation_start_time = int(time.time())

    # (Blocking)Initial Handshake
    mega_client.three_way_handshake()

    # Pause; Wait for server to present challenge move
    print("Wait for server to prompt the first challenge move, then press any key to begin.")
    input()

    # Inform Mega to start sending data
    mega_client.send_message("S")
    logging.info("S sent")

    # Generate unlimited predictions
    while True:
        time.sleep(0.5)  # human reaction time
        mega_client.port.reset_input_buffer()  # flush input
        mega_client.discard_till_sentinel()  # flush is likely to cut off a message

        # Per result loop vars
        candidates_generated = 0
        error_count = 0
        move_start_time = int(time.time())  # 1-second precision of seconds since epoch
        candidates = []
        data_buffer = []

        # Per prediction loop -- 3 predictions for 1 result
        while candidates_generated != 3:

            # Fill frame
            while len(data_buffer) < frame_length:
                try:
                    time.sleep(sampling_interval)
                    mega_client.port.reset_input_buffer()  # flush input
                    mega_client.discard_till_sentinel()  # flush is likely to cut off a message
                    message = MessageParser.parse(mega_client.read_message())
                except Exception as err:
                    logging.debug(repr(err))
                    if fail_fast:
                        sys.exit()
                    error_count += 1
                    if error_count == 3:
                        error_count = 0
                        data_buffer.clear()
                        mega_client.three_way_handshake()
                else:
                    error_count = 0
                    # Acknowledge the message
                    #mega_client.send_message("A," + message.serial_number + "\n")  # TODO reinstate ACK

                    logging.info("m:" + message.serial_number + "(" + message.type.value + ")=" + str(message.readings))
                    # Add readings set to buffer
                    if message.type == MessageType.MOVEMENT:
                        data_buffer.append(message.readings)
                    else:
                        move_power_readings = message.readings  # We only store 1 power reading set per move

            # Frame full; Generate candidate prediction from frame data
            candidate_action = ml_client.temp_predict(data_buffer)  # TODO this function call currently returns a dummy
            logging.info("Frame completed. Generated candidate:" + candidate_action)
            candidates.append(candidate_action)
            candidates_generated += 1

            # Partial clear of frame buffer based on overlap
            data_buffer = data_buffer[int(frame_length*(1-overlap_ratio)):]

            if candidates_generated == 3:
                # Match predictions
                match_0_1 = candidates[0] == candidates[1]
                match_0_2 = candidates[0] == candidates[2]
                match_1_2 = candidates[1] == candidates[2]

                # Check for 2/3
                if match_0_1 or match_0_2 or match_1_2:
                    # Power calculations TODO: Mechanism to detect if power readings have been read ornot
                    move_end_time = int(time.time())
                    move_time_elapsed = move_end_time - move_start_time
                    total_time_elapsed = move_end_time - evaluation_start_time
                    temp_voltage = move_power_readings[0]
                    temp_current = move_power_readings[1]
                    temp_current_power = round(temp_voltage * temp_current, 2)
                    temp_cumulative_power = temp_current_power \
                        if temp_cumulative_power == 0.0\
                        else (((temp_cumulative_power * total_time_elapsed) +
                               (temp_current_power * move_time_elapsed))/total_time_elapsed)

                    # Sending result
                    result_string = format_results(action=candidates[0] if (match_0_1 or match_0_2)
                                                   else candidates[1],
                                                   voltage=temp_voltage, current=temp_current,
                                                   power=temp_current_power,
                                                   cumulative_power=temp_cumulative_power)
                    server_client.send_message(result_string)
                    move_power_readings = []  # Clear power readings
                    logging.info("Prediction accepted. Matched candidates >= 2/3")
                    logging.info("Result sent to server: " + result_string)

                # Unacceptable results, all 3 candidates differ; dump the first 2
                else:
                    candidates_generated -= 2
                    candidates = candidates[2:]
                    logging.info("Prediction rejected. Matched candidates < 2/3")


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
        ml_client = RpiMLClient()
        evaluation_mode(mega_client, server_client, ml_client)
