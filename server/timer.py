from datetime import datetime, timedelta


class Timer:
    def __init__(self, timeout=0, status=False):
        '''
        timeout:    in seconds
        status:     running or paused
        '''
        self.time = timedelta(seconds=timeout)
        self.state = False
        self.time_left = timedelta(seconds=timeout)
        self.expires_at = None
        self.expired = False
        
        
        
    def change_status(self, cmd=0):
        '''
        Start/stop timer
        
        :cmd: 0 stops the timer, 1 starts it
        
        '''
            
        if not cmd:
        # stop timer
            self.state = False
        else:
        # start timer
            self.expires_at = datetime.now() + self.time
            self.state = True
        
            
    def update(self):
        '''
        Updates the timer
        Returns 1 if expired, 0 otherwise
        '''
        if self.state:
            self.time_left = self.expires_at - datetime.now()
            self.expired = self.time_left.seconds == 0
            self.state = not self.expired
        
        return self.expired
    
    
    def is_running(self):
        return self.state
    
    def set_timeout(self, time=0):
        self.time = timedelta(seconds=time)
        
    def restart(self):
        self.time_left = self.time
        self.expired = self.time_left.seconds == 0
        self.expires_at = datetime.now() + self.time
        self.state = True