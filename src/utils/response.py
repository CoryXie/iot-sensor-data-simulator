class Response:
    '''Helper class to return a response from a function'''

    def __init__(self, success, message="", object=None):
        '''Initializes the response'''
        self.success = success
        self.message = message
        self.object = object