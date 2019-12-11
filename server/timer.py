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
        '''Start/stop timer'''
            
        if not cmd:
        # stop timer
            self.state = False
        else:
        # start timer
            self.expires_at = datetime.now() + self.time_left
            self.state = True
        
            
    def update(self):
        '''
        Updates the timer
        Returns 1 if expired, 0 otherwise
        '''
        self.time_left = self.expires_at - datetime.now()
        self.expired = self.time_left.seconds == 0
        
        return self.expired
    
    
    def is_running(self):
        return self.state