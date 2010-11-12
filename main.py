from google.appengine.ext.webapp.util import run_wsgi_app
import wsgi

application = wsgi.SimpledavApplication(admin_password='foobar',debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
