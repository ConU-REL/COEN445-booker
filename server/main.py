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

# store received messages (in objects)
received = []
# store messages to send
to_send = []
# store messages waiting on timeout
waiting = []


def main():
    # check if table exists. if not, make it
    curs.execute(''' SELECT count(name) FROM sqlite_master WHERE type='table' AND name='Bookings' ''')
    if curs.fetchone()[0] != 1:
        print("Creating table")
        create_table()

    # create the threads
    thread_udp = threading.Thread(target=listen, daemon=True)       # listener thread
    thread_proc = threading.Thread(target=processing, daemon=True)      # processing thread

    # start threads
    thread_proc.start()
    thread_udp.start()
    
    # received.append(Message())
    # received[-1].decode("127.0.0.1", "REQUEST,;,0,;,2019-12-11,;,13:50:10,;,3,;,asdf,asdf,asdf,asdf,;,topic")
    # print(received[-1])
    # print(received[-1].encode())
    
    
    # wait for user input (i.e. to quit)
    print("Main Menu")
    print("q: quit")
    while True:
        if input() == "q":
            exit()


def processing():
    while True:
        # process all messages waiting on timeout first (list sorted by soonest first)
        while waiting:
            pass
        if received and any(x.formed for x in received):
            rec = received.pop(0)
            
            if rec.msg == "REQUEST":
                sql_file = sqlite3.connect("server/server_db.db")
                proc_curs = sql_file.cursor()
                room = check_avail(proc_curs, rec.date, rec.time)
                if room != -1:
                    booking(proc_curs, rec, room)
                sql_file.commit()
                sql_file.close()
            elif rec.msg == "CANCEL":
                pass
            elif rec.msg == "ACCEPT":
                pass
            elif rec.msg == "REJECT":
                pass
            elif rec.msg == "WITHDRAW":
                pass
            elif rec.msg == "ADD":
                pass


def listen():
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            ip_sub = addr[0].split(".")[:3]
            # disregard packet if not from same subnet
            if ip_sub != ip_local_sub:
                continue
            received.append(Message())
            received[-1].decode(addr[0], data.decode("utf-8"))
            print(received[-1])
        except BlockingIOError:
            pass


def create_table():
    '''Create the necessary server-side SQL table if it doesn't exist'''
    curs.execute('''create table Bookings (id integer unique primary key not null, \
        date text not null unique, time text not null unique, organizer text not null, participants text not null, \
        room integer not null, tentative integer not null)''')
    sql_file.commit()
    sql_file.close()


def booking(cursor, msg, room, tentative=True, cmd=False):
    '''Function to load and store bookings. 0 => store, 1 => load'''
    if not cmd:
    # store
        params = (msg.date, msg.time, msg.source, ",".join(msg.ls_parts), room, tentative)
        cursor.execute("INSERT INTO Bookings VALUES (NULL, ?, ?, ?, ?, ?, ?)", params)
    else:
    # load
        pass


def check_avail(cursor, date, time):
    cursor.execute(''' SELECT count(room) FROM Bookings WHERE date='%s' AND time='%s' ''' % (date, time))
    res = cursor.fetchone()
    if len(res) == no_rooms:
        return -1
    elif len(res) <= no_rooms:
        return len(res)

if __name__ == "__main__":
    main()
