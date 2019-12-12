from timer import Timer


class Message:
    def __init__(self, msg=None, source=None, *args):
        # unpack arguments
        self.header = msg
        self.source = source
        self.args = list(args)
        self.formed = False
        
        # instantiate timer
        self.timer = Timer()
        # number of times retried
        self.retries = 0
        
        
    def decode(self, source, msg_recv):
        self.source = source.split(".")[-1]
        parts = msg_recv.split(",;,")
        self.header = parts[0]
        self.args = parts[1:]
        
        if self.header == "INVITE":
            self.mt_id = self.args[0]
            self.date = self.args[1]
            self.time = self.args[2]
            self.topic = self.args[3]
            self.org = self.args[4]
            
        self.formed = True
    
    def encode(self):
        if self.header == "REQUEST":
            concat = ",;,".join([self.header] + self.args)
            
        return concat.encode('utf-8')