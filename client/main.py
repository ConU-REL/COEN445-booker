import sys, socket, sqlite3, threading


# get server ip address (localhost for now)
ip_server = socket.gethostbyname(socket.gethostname())
# open local journal file
sql_file = sqlite3.connect("server_db.db")

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
    
    
def main():
    test_req = b"REQUEST,;,0,;,2019-12-12,;,13:50:10,;,3,;,1,2,3,4,;,topic"

    thread_recv = threading.Thread(target=recv, daemon=True)
    thread_recv.start()
    
    
    print("Main Menu")
    print("q: quit")
    print("s: send message")
    while True:
        inp = input()
        if inp == "s":
            sock.sendto(test_req, (ip_server, port_send))
        elif inp == "q":
            exit()


def recv():
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            print(F"Received {data} from {addr}")
        except (BlockingIOError, ConnectionResetError):
            pass
                


if __name__ == "__main__":
    main()