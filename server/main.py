import sys, socket, sqlite3, keyboard, threading
import time
from messages import Message

# get local ip address
ip_local = socket.gethostbyname(socket.gethostname())
ip_local_sub = ip_local.split(".")[:3]
# open local journal file
sql_file = sqlite3.connect("server/server_db.db")
curs = sql_file.cursor()
# define number of rooms available to be booked
no_rooms = 2

# ****** UDP Settings ******

# port number to listen on
port = 6969
# initialize UDP socket on IPv4
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# bind to chosen port
sock.bind((socket.gethostname(), port))
# set socket to be non-blocking
sock.setblocking(0)

# store received messages
received = []


def main():
    # check if table exists. if not, make it
    curs.execute(''' SELECT count(name) FROM sqlite_master WHERE type='table' AND name='Bookings' ''')
    if curs.fetchone()[0] != 1:
        print("Creating table")
        create_table()

    # test = Message("REQUEST", "asd", "asd", "asdf")


    # create the listener and queue processor threads
    thread_udp = threading.Thread(target=listen, daemon=True)
    thread_queue = threading.Thread(target=queue, daemon=True)

    # start both threads
    thread_queue.start()
    thread_udp.start()
    
    # wait for user input
    print("Main Menu")
    print("q: quit")
    while True:
        if input() == "q":
            exit()


def queue():
    while True:
        time.sleep(0.25)
        while received:
            msg = received.pop()
            ip = msg[0].split(".")[:3]
            # disregard packet if not from same subnet
            if ip != ip_local_sub:
                continue
            print("Message received from:", msg[0])
            print("Message contents:", msg[1])


def listen():
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            received.append([addr[0], data.decode("utf-8")])
            # debug:
            print("Received:", data.decode("utf-8"), "from:", addr[0])
        except BlockingIOError:
            pass


def create_table():
    '''Create the necessary server-side SQL table if it doesn't exist'''
    curs.execute('''create table Bookings (id integer unique primary key not null, \
        date text not null unique, organizer text not null, participants text not null, \
        room integer not null)''')
    sql_file.commit()
    sql_file.close()


def booking(cmd = False):
    '''Function to load and store bookings. 0 => load, 1 => store'''
    if not cmd:
    # load
        pass
    else:
    # store
        pass



if __name__ == "__main__":
    main()
