from timer import Timer


class Message:
    def __init__(self, msg=None, source=None, *args):
        # unpack arguments
        self.header = msg
        self.source = source
        self.args = list(args)
        self.formed = False
        self.resp_reason = ""
        self.rq_id = -1
        
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
            
        elif self.header == "RESPONSE":
            self.rq_id = self.args[0]
            self.resp_reason = self.args[1]
            
        elif self.header == "SCHEDULED":
            self.rq_id = self.args[0]
            self.mt_id = self.args[1]
            self.room = self.args[2]
            self.ls_parts = self.args[3]
            
        elif self.header == "NOT SCHEDULED":
            self.rq_id = self.args[0]
            self.date = self.args[1]
            self.time = self.args[2]
            self.min_parts = self.args[3]
            self.ls_parts = self.args[4]
            self.topic = self.args[5]
        self.formed = True
    
    def encode(self):
        if self.header == "REQUEST":
            concat = ",;,".join([self.header] + self.args)
        if self.header == "CANCEL":
            concat = ",;,".join([self.header, str(self.args[0])])

        return concat.encode('utf-8')