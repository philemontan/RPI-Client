from tkinter import *
from tkinter.ttk import *

class rpi_client_gui:
    def __init__(self):
        self.root = Tk()
        self.root.title("CG3002 - Group 04 - Pi Masher")
        self.setup()

    def start(self):
        self.root.mainloop()

    def setup(self):
        self.root.geometry("800x600")
        SERVER_CONFIG_HEADER = Label(self.root, text="Server Configuration:", font='Arial 14 bold')
        SERVER_CONFIG_ENTRY_IP_LABEL = Label(self.root, text="IP:", font = 'Arial 10 bold')
        SERVER_CONFIG_ENTRY_IP = Entry(self.root, exportselection=0)
        SERVER_CONFIG_ENTRY_PORT_LABEL = Label(self.root, text="PORT:", font = 'Arial 10 bold')
        SERVER_CONFIG_ENTRY_PORT = Entry(self.root, exportselection=0)



        SERVER_CONFIG_HEADER.grid(padx=10, pady=10, column=0, row=0, columnspan=3, sticky='N')

        SERVER_CONFIG_ENTRY_IP_LABEL.grid(padx=10, pady=10, column=0, row=1, sticky='W')
        SERVER_CONFIG_ENTRY_IP.grid(padx=10, pady=10, column=1, row=1, sticky='W')

        SERVER_CONFIG_ENTRY_PORT_LABEL.grid(padx=10, pady=10, column=2, row=1, sticky='W')
        SERVER_CONFIG_ENTRY_PORT.grid(padx=10, pady=10, column=3, row=1, sticky='W')

if __name__ == '__main__':
    gui = rpi_client_gui()
    gui.start()



