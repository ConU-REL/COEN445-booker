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
port_bind = 6969
# port number to send to
port_send = 6942
# initialize UDP socket on IPv4
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# bind to chosen port
sock.bind((socket.gethostname(), port_bind))
# set socket to be non-blocking
sock.setblocking(0)

# store received messages (in objects)
received = []
# store messages to send
to_send = []
# store messages waiting on timeout
waiting = []

# Timeouts
timeouts = {'INVITE':15}
retries = {'INVITE':3}


def main():
    # check if table exists. if not, make it
    curs.execute(''' SELECT count(name) FROM sqlite_master WHERE type='table' AND name='Bookings' ''')
    if curs.fetchone()[0] != 1:
        print("Creating table")
        create_table()

    # create the threads
    thread_listen = threading.Thread(target=listen, daemon=True)       # listener thread
    thread_proc = threading.Thread(target=processing, daemon=True)      # processing thread
    thread_send = threading.Thread(target=send, daemon=True)

    # start threads
    thread_proc.start()
    thread_listen.start()
    thread_send.start()
    
    # wait for user input (i.e. to quit)
    print("Main Menu")
    print("q: quit")
    while True:
        if input() == "q":
            exit()


def processing():
    while True:
        sql_file = sqlite3.connect("server/server_db.db")
        proc_curs = sql_file.cursor()
        # process all messages waiting on timeout first (list sorted by soonest first)
        while waiting:
            for i in waiting:
                i.timer.update()
            waiting.sort(key=lambda x: x.timer.time_left.seconds)
            
            for msg in waiting:
                # if we reach a message that is still timed out, all the following ones will be too
                if not msg.timer.expired:
                    break
                # check if message has any retries left
                if msg.retries < retries.get(msg.msg):
                    msg.retries += 1
                    msg.timer.restart()
                    send_msg(msg)
                # if there are no retries left
                else:
                    
                    # check if all participants have responded
                    if all(msg.ls_parts.values()):
                        msg.retries = retries.get(msg.msg)
                        
                        
        if received and any(x.formed for x in received):
            rec = received.pop(0)
            
            if rec.msg == "REQUEST":
                
                
                room = check_avail(proc_curs, rec.date, rec.time)
                if room != -1:
                    mt_id = booking(proc_curs, rec, room)
                    rec.mt_id = str(mt_id)
                    sql_file.commit()
                    rec.unavailable = False
                    
                to_send.append(rec)
                
            elif rec.msg == "CANCEL":
                # TODO check if meeting exists. If no, inform org, if yes send cancel to all parts. and remove from sql
                pass
            elif rec.msg == "ACCEPT":
                # TODO check if meeting exists. If yes, update participant status, if no drop
                pass
            elif rec.msg == "REJECT":
                # do nothing
                pass
            elif rec.msg == "WITHDRAW":
                # TODO check meeting exists. check part invited, if yes to both send withdraw to org, update part status, re-check min part
                # TODO if min part not met, resend invs to all rejects
                # TODO if still not enough, send cancel to all parts. inc. org.
                # TODO update meeting as req'd
                pass
            elif rec.msg == "ADD":
                # TODO check meeting exists. check part invited. if no, reply with cancel, if yes send confirm, send added to org, update part status
                pass
            
        sql_file.close()

def update_meeting(msg):
    pass


def listen():
    '''
    Listen on the UDP socket for messages, then process them into a Message object 
    and add them to the queue to be handled in another thread
    '''
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            ip_sub = addr[0].split(".")[:3]
            # disregard packet if not from same subnet
            if ip_sub != ip_local_sub:
                continue
            received.append(Message())
            received[-1].decode(addr[0], data.decode("utf-8"))
        except (BlockingIOError, ConnectionResetError):
            pass


def send():
    '''
    Send any messages in the send queue
    '''
    while True:
        if to_send:
            snd = to_send.pop(0)
            # If the message to deal with is a booking request
            if snd.msg == "REQUEST":
                # If the room isn't available
                if snd.unavailable == True:
                    # Construct the message
                    msg = Message("RESPONSE", snd.source, snd.rq_id, "ROOM UNAVAILABLE")
                    # Construct the destination IP based on local subnet and ID
                    dest = ip_local_sub[0:]
                    dest.append(msg.source)
                    dest = ".".join(dest)
                    print(F"Sending {msg.encode()} to {dest}")
                    # Send the message to the requestor
                    sock.sendto(msg.encode(), (dest, port_send))
                # If the room is available
                else:
                    # Construct the invitation message
                    msg = Message("INVITE", snd.source, snd.mt_id, snd.date, snd.time, snd.topic, snd.source)
                    msg.ls_parts = snd.ls_parts
                    print(F"Sending {msg.encode()} to {msg.ls_parts}")
                    
                    # Send the messages
                    send_msg(msg)
                    
                    # set timout and retries
                    msg.timer.set_timeout(timeouts.get("INVITE"))
                    msg.retries = retries.get("INVITE")
                    # start timer
                    msg.timer.change_status(True)
                    # add message to waiting list
                    waiting.append(msg)
                    
                    # update expiry state of all waiting messages
                    for i in waiting:
                        i.timer.update()
                    
                    # sort the list from soonest expiry to latest
                    waiting.sort(key=lambda x: x.timer.time_left.seconds)
                    

def send_msg(msg):
    # Send the messages
    for i in list(msg.ls_parts.keys()): 
        if msg.ls_parts.get(i):
            continue
        dest = ip_local_sub[0:]
        dest.append(str(i))
        dest = ".".join(dest)
        
        print(F"Sending to {dest}")
        sock.sendto(msg.encode(), (dest, port_send))

def create_table():
    '''Create the necessary server-side SQL table if it doesn't exist'''
    curs.execute('''create table Bookings (id integer unique primary key not null, \
        date text not null, time text not null, organizer text not null, participants text not null, \
        room integer not null, tentative integer not null)''')
    sql_file.commit()
    sql_file.close()


def booking(cursor, msg, room, tentative=True, cmd=False):
    '''Function to load and store bookings. 0 => store, 1 => load'''
    if not cmd:
    # store
        params = (msg.date, msg.time, msg.source, str(msg.ls_parts), room, tentative)
        cursor.execute("INSERT INTO Bookings VALUES (NULL, ?, ?, ?, ?, ?, ?)", params)
        params = (msg.date, msg.time, room)
        cursor.execute("SELECT id FROM Bookings WHERE date=? AND time=? AND room=?", params)
        return cursor.fetchone()[0]
    else:
    # load
        pass


def check_avail(cursor, date, time):
    cursor.execute(''' SELECT count(room) FROM Bookings WHERE date='%s' AND time='%s' ''' % (date, time))
    res = cursor.fetchone()[0]
    if res >= no_rooms:
        return -1
    elif res < no_rooms:
        return res

if __name__ == "__main__":
    main()
