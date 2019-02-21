import serial

if __name__ == "__main__":
    port = serial.Serial("/dev/ttyAMA0", baudrate=115200, timeout=3.0)
    #port.open()   
    print("serial port openeed\n")

    while True:
        print("1: send, 2: receive")
        mode = input()
        if mode == "1":
            while True:
                print("enter text to send")
                message = (input() + '\n').encode()
                port.write(message)
        if mode == "2":
            while True:
                print("enter any key to readline")
                temp = input()
                while True:
#                    t = port.readline().decode()
                    print(port.in_waiting)
                    print("spacing\n")



