from base64 import b64decode
from google.appengine.ext import webapp
from views import DAVHandler
import cgi
import logging
import sys
import traceback

class WSGIApplication(object):
    def __init__(self, prefix=None, admin_password=None, debug=False):
        """Initializes this application with the given URL mapping.

        Args:
            debug: if true, we send Python stack traces to the browser on errors
        """
        self._debug = debug
        self._admin_password = admin_password
        self._handler = DAVHandler(prefix)

    def __call__(self, environ, start_response):
        """Called by WSGI when a request comes in."""
        request = webapp.Request(environ)
        response = webapp.Response()
        response.headers['DAV'] = '1,2' # These headers seem to be required for some clients.
        response.headers['MS-Author-Via'] = 'DAV'

        try:
            self.handle_request(environ, request, response)
        except Exception, e:
            self.handle_exception(response, e)

        response.wsgi_write(start_response)
        return ['']
    
    def get_credentials(self, request):
        """Extracts and returns the tuple (username,password) from the given request's HTTP Basic 'Authentication' header."""
        auth_header = request.headers.get('Authorization')

        if auth_header:
            (scheme, base64_raw) = auth_header.split(' ')
            
            if scheme == 'Basic':
                return b64decode(base64_raw).split(':')
        
        return (None, None)
    
    def handle_request(self, environ, request, response):
        """Handles a single incoming request. If admin_password was given to our initializer, we'll check your password and kick you out if it doesn't match."""
        
        if self._admin_password:
            (username,password) = self.get_credentials(request)
            if username != 'admin' or password != self._admin_password:
                return self.request_authentication(response)

        method = environ['REQUEST_METHOD']

        self._handler.initialize(request, response)
        handler_method = getattr(self._handler,method.lower())
        handler_method()
    
    def request_authentication(self, response):
        response.set_status(401, message='Authorization Required')
        response.headers['WWW-Authenticate'] = 'Basic realm="Secure Area"'
    
    def error(self, response, code):
        response.clear()
        response.set_status(code)

    def handle_exception(self, response, exception):
        """Called if this handler throws an exception during execution.

        The default behavior is to call self.error(500) and print a stack trace
        if self._debug is True.

        Args:
            exception: the exception that was thrown
        """
        self.error(response, 500)
        logging.exception(exception)
        if self._debug:
            lines = ''.join(traceback.format_exception(*sys.exc_info()))
            response.clear()
            response.out.write('<pre>%s</pre>' % (cgi.escape(lines, quote=True)))
