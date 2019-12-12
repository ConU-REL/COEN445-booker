import sys, socket, sqlite3, keyboard, threading
import time
from messages import Message
from ast import literal_eval

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
timeouts = {'INVITE':5}
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
        if waiting:
            for i in waiting:
                i.timer.update()
            waiting.sort(key=lambda x: x.timer.time_left.seconds)
            while True:
                if not waiting:
                    break
                msg = waiting.pop(0)
                # if we reach a message that is still timed out, all the following ones will be too
                if not msg.timer.expired:
                    waiting.append(msg)
                    break
                # check if message has any retries left
                if msg.retries < retries.get(msg.header)-1:
                    msg.retries += 1
                    msg.timer.restart()
                    proc_curs.execute("SELECT participants FROM Bookings WHERE id=?", (msg.mt_id,))
                    res = proc_curs.fetchone()[0]
                    msg.ls_parts = literal_eval(res)
                    send_parts(msg)
                    waiting.append(msg)
                # if there are no retries left
                else:
                    # check if we have enough participants
                    proc_curs.execute("SELECT participants FROM Bookings WHERE id=?", (msg.mt_id,))
                    res = proc_curs.fetchone()[0]
                    msg.ls_parts = literal_eval(res)

                    if sum(msg.ls_parts.values()) >= int(msg.min_parts):
                        proc_curs.execute("UPDATE Bookings SET participants=? WHERE id=?", (str(msg.ls_parts), msg.mt_id))
                        proc_curs.execute("UPDATE Bookings SET tentative=0 WHERE id=?", (msg.mt_id,))
                        sql_file.commit()
                        
                        msg.header = "SCHEDULED"
                        
                        dest = ip_local_sub[0:]
                        dest.append(msg.source)
                        dest = ".".join(dest)
                        
                        # send confirmation to org that meeting is scheduled
                        sock.sendto(msg.encode(), (dest, port_send))
                        
                    # if we don't
                    else:
                        msg.header = "CANCEL"
                        msg.resp_reason = "PARTICIPANTS"
                        send_parts(msg, True)
                        
                        msg.header = "NOT SCHEDULED"
                        dest = ip_local_sub[0:]
                        dest.append(msg.source)
                        dest = ".".join(dest)
                        
                        # send confirmation to org that meeting is not scheduled
                        sock.sendto(msg.encode(), (dest, port_send))
                        
                        proc_curs.execute("DELETE FROM Bookings WHERE id=?", (msg.mt_id))
                        sql_file.commit()
                        

        if received and any(x.formed for x in received):
            # pop the first message in the queue
            rec = received.pop(0)
            
            # if REQUEST message
            if rec.header == "REQUEST":
                room = check_avail(proc_curs, rec.date, rec.time)
                if room != -1:
                    mt_id = booking(proc_curs, rec, room)
                    rec.mt_id = str(mt_id)
                    rec.room = room
                    sql_file.commit()
                    rec.unavailable = False
                    
                to_send.append(rec)
            # if CANCEL message
            elif rec.header == "CANCEL":
                # TODO test this
                proc_curs.execute("SELECT count(id) FROM Bookings WHERE id=?", (rec.mt_id))
                res = proc_curs.fetchone()[0]
                # if meeting doesn't exist, inform requestor
                if not res:
                    rec.header = "RESPONSE"
                    rec.resp_reason = "MEETING DNE"
                    rec.rq_id = rec.mt_id
                    
                    dest = ip_local_sub[0:]
                    dest.append(rec.source)
                    dest = ".".join(dest)
                    
                    sock.sendto(rec.encode(), (dest, port_send))
                # if the meeting exists, notify all confirmed participants
                else:
                    rec.resp_reason = "CANCELLED BY ORGANIZER"
                    proc_curs.execute("SELECT participants FROM Bookings WHERE id=?", (rec.mt_id))
                    res = proc_curs.fetchone()[0]
                    rec.ls_parts = literal_eval(res)
                    
                    send_parts(rec, True)
                    
                    rec.header = "RESPONSE"
                    rec.resp_reason = "CANCEL RECEIVED"
                    rec.rq_id = rec.mt_id
                    
                    dest = ip_local_sub[0:]
                    dest.append(rec.source)
                    dest = ".".join(dest)
                    
                    sock.sendto(rec.encode(), (dest, port_send))
                    proc_curs.execute("DELETE FROM Bookings WHERE id=?", (rec.mt_id,))
                    sql_file.commit()
                    
            elif rec.header == "ACCEPT":
                # TODO test this
                # check if meeting exists
                proc_curs.execute("SELECT count(id) FROM Bookings WHERE id=?", (rec.mt_id))
                res = proc_curs.fetchone()[0]
                # if meeting is not found
                if not res:
                    rec.header = "RESPONSE"
                    rec.resp_reason = "MEETING DNE"
                    
                    dest = ip_local_sub[0:]
                    dest.append(rec.source)
                    dest = ".".join(dest)
                    
                    sock.sendto(rec.encode(), (dest, port_send))
                else:
                    # get participants
                    proc_curs.execute("SELECT participants FROM Bookings WHERE id=?", (rec.mt_id))
                    res = proc_curs.fetchone()[0]
                    rec.ls_parts = literal_eval(res)
                    
                    # check if requestor is a participant
                    if int(rec.source) in list(rec.ls_parts.keys()):
                        # set participant to accepted
                        rec.ls_parts[rec.source] = 1
                        print(rec.ls_parts[rec.source])
                        # update sql entry
                        proc_curs.execute("UPDATE Bookings SET participants=? WHERE id=?", (str(rec.ls_parts), rec.mt_id))
                        sql_file.commit()
                        proc_curs.execute("SELECT room FROM Bookings WHERE id=?", (rec.mt_id,))
                        res = proc_curs.fetchone()[0]
                        rec.room = res
                        
                        # confirm with requestor
                        rec.header = "CONFIRM"
                        
                        dest = ip_local_sub[0:]
                        dest.append(rec.source)
                        dest = ".".join(dest)
                        
                        # send confirmation
                        sock.sendto(rec.encode(), (dest, port_send))
                    # if not participant
                    else:
                        rec.header = "RESPONSE"
                        rec.resp_reason = "NOT INVITED"
                        
                        dest = ip_local_sub[0:]
                        dest.append(rec.source)
                        dest = ".".join(dest)
                        
                        # send rude reply
                        sock.sendto(rec.encode(), (dest, port_send))
                
            elif rec.header == "REJECT":
                # do nothing (we assume invitation rejected until told otherwise)
                pass
            elif rec.header == "WITHDRAW":
                # TODO check meeting exists. check part invited, if yes to both send withdraw to org, update part status, re-check min part
                # TODO if min part not met, resend invs to all rejects
                # TODO if still not enough, send cancel to all parts. inc. org.
                # TODO update meeting as req'd
                
                # check if meeting exists
                proc_curs.execute("SELECT count(id) FROM Bookings WHERE id=?", (rec.mt_id))
                proc_curs.execute("SELECT tentative FROM Bookings WHERE id=?", (rec.mt_id))
                res[0] = proc_curs.fetchone()[0]
                res[1] = proc_curs.fetchone()[0]
                # if meeting is not found or is still tentative
                if (not res[0]) or res[1]:
                    rec.header = "CANCEL"
                    rec.resp_reason = "MEETING NOT SCHEDULED"
                    
                    dest = ip_local_sub[0:]
                    dest.append(rec.source)
                    dest = ".".join(dest)
                    
                    sock.sendto(rec.encode(), (dest, port_send))
                # if meeting is found/scheduled
                else:
                    # get participants
                    proc_curs.execute("SELECT participants FROM Bookings WHERE id=?", (rec.mt_id))
                    res = proc_curs.fetchone()[0]
                    rec.ls_parts = literal_eval(res)
                    
                    # check if requestor is a participant
                    if rec.source in rec.ls_parts.keys():
                        # set participant to rejected
                        rec[rec.source] = 0
                        # update sql entry
                        proc_curs.execute("UPDATE Bookings SET participants=? WHERE id=?", (str(rec.ls_parts), rec.mt_id))
                        sql_file.commit()
                        
                        # get organizer ip
                        proc_curs.execute("SELECT organizer FROM Bookings WHERE id=?", (rec.mt_id))
                        res = proc_curs.fetchone()[0]
                        
                        # inform organizer
                        rec.header = "WITHDRAW"
                        
                        dest = ip_local_sub[0:]
                        dest.append(rec.res)
                        dest = ".".join(dest)
                        
                        # send inform
                        sock.sendto(rec.encode(), (dest, port_send))
                        
                        proc_curs.execute("SELECT * FROM Bookings WHERE id=?", (rec.mt_id))
                        res = proc_curs.fetchone()
                        
                        parts = ",".join([str(x) for x in list(rec.ls_parts.keys())])
                        rereq = Message("REQUEST", -1, res[1], res[2], res[4], parts, res[8])
                        rereq.mt_id = rec.mt_id
                        rereq.decode(rec.source, rereq)
                        rereq.unavailable = False
                        
                        to_send.append(rereq)
                        
                    # if not invited
                    else:
                        rec.header = "RESPONSE"
                        rec.resp_reason = "NOT INVITED"
                        
                        dest = ip_local_sub[0:]
                        dest.append(rec.source)
                        dest = ".".join(dest)
                        
                        # send rude reply
                        sock.sendto(rec.encode(), (dest, port_send))
            elif rec.header == "ADD":
                # TODO test this
                # check if meeting exists
                proc_curs.execute("SELECT count(id) FROM Bookings WHERE id=?", (rec.mt_id))
                proc_curs.execute("SELECT tentative FROM Bookings WHERE id=?", (rec.mt_id))
                res[0] = proc_curs.fetchone()[0]
                res[1] = proc_curs.fetchone()[0]
                # if meeting is not found or is still tentative
                if (not res[0]) or res[1]:
                    rec.header = "CANCEL"
                    rec.resp_reason = "MEETING NOT SCHEDULED"
                    
                    dest = ip_local_sub[0:]
                    dest.append(rec.source)
                    dest = ".".join(dest)
                    
                    sock.sendto(rec.encode(), (dest, port_send))
                # if meeting is found/scheduled
                else:
                    # get participants
                    proc_curs.execute("SELECT participants FROM Bookings WHERE id=?", (rec.mt_id))
                    res = proc_curs.fetchone()[0]
                    rec.ls_parts = literal_eval(res)
                    
                    # check if requestor is a participant
                    if rec.source in rec.ls_parts.keys():
                        # set participant to accepted
                        rec[rec.source] = 1
                        # update sql entry
                        proc_curs.execute("UPDATE Bookings SET participants=? WHERE id=?", (str(rec.ls_parts), rec.mt_id))
                        sql_file.commit()
                        
                        # confirm with requestor
                        rec.header = "CONFIRM"
                        
                        dest = ip_local_sub[0:]
                        dest.append(rec.source)
                        dest = ".".join(dest)
                        
                        # send confirmation
                        sock.sendto(rec.encode(), (dest, port_send))
                        
                        # get organizer ip
                        proc_curs.execute("SELECT organizer FROM Bookings WHERE id=?", (rec.mt_id))
                        res = proc_curs.fetchone()[0]
                        
                        # inform organizer
                        rec.header = "ADDED"
                        
                        dest = ip_local_sub[0:]
                        dest.append(rec.res)
                        dest = ".".join(dest)
                        
                        # send inform
                        sock.sendto(rec.encode(), (dest, port_send))
                    # if not participant
                    else:
                        rec.header = "RESPONSE"
                        rec.resp_reason = "NOT INVITED"
                        
                        dest = ip_local_sub[0:]
                        dest.append(rec.source)
                        dest = ".".join(dest)
                        
                        # send rude reply
                        sock.sendto(rec.encode(), (dest, port_send))
            
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
            if snd.header == "REQUEST":
                # If the room isn't available
                if snd.unavailable == True:
                    # Construct the message
                    snd.header = "RESPONSE"
                    snd.resp_reason = "ROOM UNAVAILABLE"
                    # Construct the destination IP based on local subnet and ID
                    dest = ip_local_sub[0:]
                    dest.append(snd.source)
                    dest = ".".join(dest)
                    print(F"Sending {snd.encode()} to {dest}")
                    # Send the message to the requestor
                    sock.sendto(snd.encode(), (dest, port_send))
                # If the room is available
                else:
                    # Construct the invitation message
                    snd.header = "INVITE"
                    print(F"Sending {snd.encode()} to {snd.ls_parts}")
                    
                    # Send the messages
                    send_parts(snd)
                    
                    # set timout and retries
                    snd.timer.set_timeout(timeouts.get("INVITE"))
                    # start timer
                    snd.timer.change_status(True)
                    # add message to waiting list
                    waiting.append(snd)
                    
                    # update expiry state of all waiting messages
                    for i in waiting:
                        i.timer.update()
                    
                    # sort the list from soonest expiry to latest
                    waiting.sort(key=lambda x: x.timer.time_left.seconds)
                    resp = Message("RESPONSE", snd.source)
                    resp.resp_reason = "PROCESSING"
                    resp.rq_id = snd.rq_id
                    
                    # let the requestor know we are processing
                    dest = ip_local_sub[0:]
                    dest.append(snd.source)
                    dest = ".".join(dest)
                    sock.sendto(resp.encode(), (dest, port_send))

def send_parts(msg, group=0):
    # Send the messages
    #print(F"Message to be sent: {msg.encode()}")
    print("Sending to participants")
    for i in list(msg.ls_parts.keys()):
        if msg.ls_parts.get(i) != group:
            continue
        dest = ip_local_sub[0:]
        dest.append(str(i))
        dest = ".".join(dest)
        
        sock.sendto(msg.encode(), (dest, port_send))

def create_table():
    '''Create the necessary server-side SQL table if it doesn't exist'''
    curs.execute('''create table Bookings (id integer unique primary key not null, \
        date text not null, time text not null, organizer text not null, min_part integer not null, \
        participants text not null, room integer not null, tentative integer not null, topic text)''')
    sql_file.commit()
    sql_file.close()


def booking(cursor, msg, room, tentative=True, cmd=False):
    '''Function to load and store bookings. 0 => store, 1 => load'''
    if not cmd:
    # store
        params = (msg.date, msg.time, msg.source, msg.min_parts, str(msg.ls_parts), room, tentative, msg.topic)
        cursor.execute("INSERT INTO Bookings VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)", params)
        params = (msg.date, msg.time, room)
        cursor.execute("SELECT id FROM Bookings WHERE date=? AND time=? AND room=?", params)
        return cursor.fetchone()[0]


def check_avail(cursor, date, time):
    cursor.execute(''' SELECT count(room) FROM Bookings WHERE date='%s' AND time='%s' ''' % (date, time))
    res = cursor.fetchone()[0]
    if res >= no_rooms:
        return -1
    elif res < no_rooms:
        return res

if __name__ == "__main__":
    main()
