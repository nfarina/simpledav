from base64 import b64decode
from google.appengine.ext import webapp
from views import DAVHandler
import cgi
import logging
import sys
import traceback

class WSGIApplication(object):
    def __init__(self, prefix=None, debug=False):
        """Initializes this application with the given URL mapping.

        Args:
            debug: if true, we send Python stack traces to the browser on errors
        """
        self.__debug = debug
        self.handler = DAVHandler(prefix)

    def __call__(self, environ, start_response):
        """Called by WSGI when a request comes in."""
        request = webapp.Request(environ)
        response = webapp.Response()

        method = environ['REQUEST_METHOD']

        try:
            if self.authentication_valid(request):
                #response.out.write("Hello WSGI World! You want us to %s?" % method)
                self.handler.initialize(request, response)
                handler_method = getattr(self.handler,method.lower())
                handler_method()
                
                response.headers['DAV'] = '1,2'
                response.headers['MS-Author-Via'] = 'DAV'
            else:
                self.request_authentication(response)
        except Exception, e:
            self.handle_exception(response, e, self.__debug)

        response.wsgi_write(start_response)
        return ['']
    
    def authentication_valid(self, request):
        auth_header = request.headers.get('Authorization')

        if auth_header:
            (scheme, base64_raw) = auth_header.split(' ')
            
            if scheme == 'Basic':
                (username, password) = b64decode(base64_raw).split(':')
                if username == 'admin' and password == 'foobar':
                    return True
    
    def handle_request(self):
        pass
    
    def request_authentication(self, response):
        response.set_status(401, message='Authorization Required')
        response.headers['WWW-Authenticate'] = 'Basic realm="Secure Area"'
    
    def error(self, response, code):
        response.clear()
        response.set_status(code)

    def handle_exception(self, response, exception, debug_mode):
        """Called if this handler throws an exception during execution.

        The default behavior is to call self.error(500) and print a stack trace
        if debug_mode is True.

        Args:
            exception: the exception that was thrown
            debug_mode: True if the web application is running in debug mode
        """
        self.error(response, 500)
        logging.exception(exception)
        if debug_mode:
            lines = ''.join(traceback.format_exception(*sys.exc_info()))
            response.clear()
            response.out.write('<pre>%s</pre>' % (cgi.escape(lines, quote=True)))
