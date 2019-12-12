from timer import Timer

class Message:
    def __init__(self, msg=None, source=None, *args):
        # unpack arguments
        self.msg = msg
        self.source = source
        self.args = list(args)
        self.formed = False
        
        # instantiate timer
        self.timer = Timer()
        

    def __str__(self):
        data = f"Message received from ID {self.source}, contents:\n" \
            f"\tCommand: {self.msg}\n" \
            f"\tDetails: {self.args}"
        return data


    def decode(self, source, msg_recv):
        self.source = source.split(".")[-1]
        parts = msg_recv.split(",;,")
        self.msg = parts[0]
        self.args = parts[1:]
        
        if self.msg == "REQUEST":
            self.unavailable = True
            self.retries = 0
            self.rq_id = self.args[0]
            self.date = self.args[1]
            self.time = self.args[2]
            self.min_parts = self.args[3]
            tmp = self.args[4].split(",")
            tmp = [int(i) for i in tmp]
            self.ls_parts = dict(zip(tmp,[0 for i in tmp]))
            self.args[4] = ",".join([str(x) for x in list(self.ls_parts.keys())])
            self.topic = self.args[5]
        elif self.msg == "RESPONSE":
            pass            
        self.formed = True
    
    def encode(self):
        concat = ",;,".join([self.msg] + self.args)
        return concat.encode('utf-8')
        
