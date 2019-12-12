import socket
import sqlite3
import sys
import threading
import re
from datetime import datetime, timedelta

from messages import Message

# get server ip address (localhost for now)
ip_server = socket.gethostbyname(socket.gethostname())
# get local id (from ip)
id_local = socket.gethostbyname(socket.gethostname()).split(".")[-1]
# open local journal file
sql_file = sqlite3.connect("client/local_db.db")
curs = sql_file.cursor()


# starting request id
request_id = 1

# ****** UDP Settings ******

# port number to listen on
port_bind = 6942
# port number to send on
port_send = 6969
# initialize UDP socket on IPv4
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# bind to chosen port
sock.bind((socket.gethostname(), port_bind))
# set socket to be non-blocking
sock.setblocking(0)
    
# store received messages (in objects)
received = []
# store messages waiting on timeout
waiting = []

# Timeouts
timeouts = {'REQUEST':15, 'CANCEL':15, 'RESPONSE':15}
retries = {'REQUEST':3, 'CANCEL':3, 'RESPONSE':3}
    
def main():
    curs.execute(''' SELECT count(name) FROM sqlite_master WHERE type='table' AND name='Bookings' ''')
    if curs.fetchone()[0] != 1:
        print("Creating table")
        create_table()
    
    

    thread_recv = threading.Thread(target=recv, daemon=True)
    thread_proc = threading.Thread(target=proc, daemon=True)
    thread_recv.start()
    thread_proc.start()

    
    while True:
        curs.execute("SELECT count(id) from Bookings")
        request_id = curs.fetchone()[0]+1
        main_menu()
        inp = input()
        if inp == "a":
            print("Enter Date (ex. YYYY-MM-DD): ", end="")
            date = input()
            if date == "q":
                exit()
            elif not bool(re.search(r'^\d{4}-\d{2}-\d{2}$', date)):
                continue
            tmp = [int(x) for x in date.split("-")]
            try:
                date = datetime(tmp[0], tmp[1], tmp[2])
            except ValueError:
                print("Bad input, try again.")
                continue

            print("Enter hour of meeting betwen 9h and 15h (ex. HH, 24h format): ", end="")
            time = input()
            dt = None
            if time == "q":
                exit()
            elif not bool(re.search(r'^\d{1,2}$', time)):
                continue
            elif any([int(time) < 9, int(time) > 17]):
                print("That time is outside 9h-17h")
                continue
            try:
                dt = datetime(date.year, date.month, date.day, int(time), 0, 0)
            except ValueError:
                print("Bad input, try again.")
                continue
            
            if dt <= datetime.now():
                print("Can't schedule meeting in the past.")
                continue
            
            print("Enter participants separated by commas: ", end="")
            parts = input()
            if parts == "q":
                exit()
            elif not bool(re.search(r'^(\d+,? ?)+$', parts)):
                continue
            
            parts = parts.replace(" ", "").split(",")      
            if not parts:
                print("Enter at least one participant.")
            
            print("Enter the minimum number of participants: ", end="")
            min_parts = input()
            if inp == "q":
                exit()
            elif not bool(re.search(r'^\d$', min_parts)):
                print("Bad input, try again.")
                continue
            if len(parts) < int(min_parts):
                print("Not enough participants to meet minimum.")
                continue
            
            print("Enter the topic: ", end="")
            topic = input()
            if topic == "q":
                exit()
                
            msg = Message("REQUEST", 0, str(request_id), date.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S"), min_parts, ",".join(parts), topic)
            msg.rq_id = str(request_id)
            params = (int(msg.rq_id), -1, msg.args[1], msg.args[2], id_local, -1, msg.args[5], -1)
            curs.execute("INSERT INTO Bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?)", params)
            sql_file.commit()
            request_id += 1
            
            msg.timer.set_timeout(timeouts.get(msg.header))
            
            sock.sendto(msg.encode(), (ip_server, port_send))
            msg.timer.change_status(True)
            waiting.append(msg)
        elif inp == "c":
            print("Confirmed bookings:")
            curs.execute("SELECT * FROM Bookings WHERE confirmed=? AND organizer=?", (1,id_local))
            res = curs.fetchall()
            print("RQ ID, MT ID, Date, Time, Organizer, Room, Topic, Confirmed")
            print(*res, sep="\n")
            print("Which booking would you like to cancel? ", end="")
            inp = input()
            if inp == "q":
                exit()
            elif not bool(re.search(r'^\d+$', inp)):
                continue
            curs.execute("SELECT mt_id FROM Bookings WHERE id=?", (inp,))
            mt_id = curs.fetchone()[0]
            msg = Message("CANCEL", "127.0.0.1", mt_id)
            sock.sendto(msg.encode(), (ip_server, port_send))
            msg.timer.set_timeout(timeouts.get(msg.header))
            msg.timer.change_status(True)
            waiting.append(msg)
        elif inp == "i":
            print("Enter server IP: ", end="")
            inp = input()
            if not bool(re.search(r'^\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}$', inp)):
                continue
            ip_server = inp
            print(ip_server)
        elif inp == "q":
            exit()

    sql_file.close()

def recv():
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            received.append(Message())
            received[-1].decode(addr[0], data.decode("utf-8"))
            print(F"Received {data} from {addr[0]}")
        except (BlockingIOError, ConnectionResetError):
            pass


def proc():
    while True:
        sql_file = sqlite3.connect("client/local_db.db")
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
                
                # check if message has been satisfied
                if msg.header == "REQUEST":
                    proc_curs.execute("SELECT confirmed FROM Bookings WHERE id=?", (msg.rq_id,))
                    res = proc_curs.fetchone()[0]
                    if not res:
                        continue
                elif msg.header == "CANCEL":
                    proc_curs.execute("SELECT count(id) FROM Bookings WHERE id=?", (msg.rq_id,))
                    res = proc_curs.fetchone()[0]
                    if not res:
                        continue
                
                    
                # if we reach a message that is still timed out, all the following ones will be too
                if not msg.timer.expired:
                    waiting.append(msg)
                    break
                
                # check if message has any retries left
                elif msg.retries < retries.get(msg.header)-1:
                    msg.retries += 1
                    msg.timer.restart()
                    print("RETRYING")
                    sock.sendto(msg.encode(), (ip_server, port_send))
                    waiting.append(msg)
                # if there are no retries left, do nothing
                
        if received and any(x.formed for x in received):
            # pop the first message in the queue
            rec = received.pop(0)
            if rec.header == "RESPONSE":
                if rec.resp_reason == "PROCESSING":
                    proc_curs.execute("UPDATE Bookings SET confirmed=? WHERE id=?", (0, rec.rq_id))
                elif rec.resp_reason == "CANCEL RECEIVED" or rec.resp_reason == "MEETING DNE":
                    print(rec.rq_id)
                    proc_curs.execute("DELETE FROM Bookings WHERE mt_id=?", (rec.rq_id,))
            
            elif rec.header == "SCHEDULED":
                proc_curs.execute("UPDATE Bookings SET confirmed=? WHERE id=?", (1, rec.rq_id))
                proc_curs.execute("UPDATE Bookings SET room=? WHERE id=?", (rec.room, rec.rq_id))
                proc_curs.execute("UPDATE Bookings SET mt_id=? WHERE id=?", (rec.mt_id, rec.rq_id))
            elif rec.header == "NOT SCHEDULED":
                proc_curs.execute("DELETE FROM Bookings WHERE id=?", (rec.rq_id,))
            
            sql_file.commit()
        
        sql_file.close()
                    
def main_menu():
    print("Main Menu")
    print("a: Add Booking", "c: Cancel Booking", "i: Enter Server IP", "q: quit", sep="\n")
    
    
def create_table():
    '''Create the necessary client-side SQL table if it doesn't exist'''
    curs.execute('''create table Bookings (id integer unique primary key not null, \
        mt_id integer unique not null, date text not null, time text not null, \
        organizer text not null, room integer not null, topic text, confirmed integer not null)''')
    sql_file.commit()
    
    
if __name__ == "__main__":
    main()
