

class Message:
    def __init__(self, msg=None, source=None, *args):
        self.msg = msg
        self.source = source
        self.args = args
        
        
    def __str__(self):
        return("Message received from: " + str(self.source) 
               + "\nMessage contents: " + str(self.msg))


    def decode(self, source, msg_recv):
        self.source = source.split(".")[-1]
        parts = msg_recv.split(",;,")
        self.msg = parts[0]
        self.args = parts[1:]
        
        