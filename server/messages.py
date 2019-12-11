from timer import Timer

class Message:
    def __init__(self, msg=None, source=None, *args):
        # unpack arguments
        self.msg = msg
        self.source = source
        self.args = args
        self.formed = False
        
        # instantiate timer
        self.timer = Timer()


    def __str__(self):
        data = f"Message received from ID {self.source}, contents:\n" \
            f"\tCommand: {self.msg}\n" \
            f"\tDetails: {self.args}"
        return(data)


    def decode(self, source, msg_recv):
        self.source = source.split(".")[-1]
        parts = msg_recv.split(",;,")
        self.msg = parts[0]
        self.args = parts[1:]
        
        if self.msg == "REQUEST":
            self.rq_id = self.args[0]
            self.date = self.args[1]
            self.time = self.args[2]
            self.min_parts = self.args[3]
            self.ls_parts = self.args[4].split(",")
            self.topic = self.args[5]
            
        self.formed = True
    
    def encode(self):
        concat = ",;,".join([self.msg] + self.args)
        return concat
        
