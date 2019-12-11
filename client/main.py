import sys, socket, sqlite3

def main():
    # get server ip address (localhost for now)
    ip_local = socket.gethostbyname(socket.gethostname())
    # open local journal file
    sql_file = sqlite3.connect("server_db.db")

    # ****** UDP Settings ******

    # port number to listen on
    port = 6969
    # initialize UDP socket on IPv4
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # bind to chosen port
    # sock.bind((ip_local, port))

    msg = b'test msg'
    sock.sendto(msg, (ip_local, port))



if __name__ == "__main__":
    main()