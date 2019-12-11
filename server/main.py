import sys, socket, sqlite3, keyboard, threading
import time

# get local ip address
ip_local = socket.gethostbyname(socket.gethostname())
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
sock.bind((ip_local, port))
sock.setblocking(0)
# # timeout
# timeout = 1
# # set socket timeout
# sock.settimeout(timeout)

# store received messages
received = []


def main():
    print("Local IPv4 address:", ip_local)

    curs.execute(''' SELECT count(name) FROM sqlite_master WHERE type='table' AND name='Bookings' ''')
    if curs.fetchone()[0] != 1:
        print("Creating table")
        create_table()

    thread_udp = threading.Thread(target=listen)
    thread_queue = threading.Thread(target=queue)

    thread_queue.start()
    thread_udp.start()
    

def queue():
    while True:
        time.sleep(0.25)
        while received:
            msg = received.pop()
            print("Message received from:", msg[0])
            print("Message contents:", msg[1])
        if keyboard.is_pressed('q'):
            break   


def listen():
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            received.append([addr[0], data.decode("utf-8")])
            # debug:
            print("Received:", data.decode("utf-8"), "from:", addr[0])
        except BlockingIOError:
            if keyboard.is_pressed('q'):
                break
        

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
        pass
    else:
        pass




if __name__ == "__main__":
    main()
