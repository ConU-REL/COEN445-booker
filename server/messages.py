

class Message:
    def __init__(self, msg=None, *args):
        self.msg = msg
        self.args = args
        print(len(self.args))
        print(self.args)

    def decode(self, msg_recv):
        parts = msg_recv.split(",;,")
        self.msg = parts[0]
        self.args = parts[1:]
