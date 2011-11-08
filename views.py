from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from models import Resource, ResourceData
from urllib import url2pathname, pathname2url
from urlparse import urlparse
from xml.etree import ElementTree as ET
import logging
import os

class DAVHandler(webapp.RequestHandler):
    def initialize(self,request,response):
        super(DAVHandler, self).initialize(request,response)
        
        self.request_path = self.url_to_path(self.request.path) if request else ""

    def set_prefix(self,prefix):
        self._prefix = '/%s/' % prefix.strip('/') if prefix else '/' # normalize

    def url_to_path(self,path):
        """Accepts a relative url string and converts it to our internal relative path (minux prefix) used in our Resource entities."""
        return url2pathname( # decode '%20's and such 
            path[len(self._prefix):] # chop off prefix
        ).strip('/')
    
    def options(self):
        self.response.headers['Allow'] = 'GET, PUT, DELETE, MKCOL, OPTIONS, COPY, MOVE, PROPFIND, PROPPATCH, LOCK, UNLOCK, HEAD'
        self.response.headers['Content-Type'] = 'httpd/unix-directory'
    
    def propfind(self):
        path = self.request_path
        self.propfind_resource(Resource.get_by_path(path))
    
    def propfind_resource(self, resource, children=None):
        depth = self.request.headers.get('depth','0')
        
        if depth != '0' and depth != '1':
            return self.response.set_status(403,'Forbidden')
        
        if not resource:
            return self.response.set_status(404,"Not Found")
        
        root = ET.Element('multistatus',{'xmlns':'DAV:'})
        root.append(resource.export_response(href=self.request.path)) # first response's href contains exactly what you asked for (relative path)
        
        if resource.is_collection and depth == '1':
            if children is None: # you can give us children if you don't want us to ask the resource
                children = resource.children
                
            for child in children:
                abs_path = pathname2url(self._prefix + child.path)
                root.append(child.export_response(href=abs_path))

        self.response.headers['Content-Type'] = 'text/xml; charset="utf-8"'
        self.response.set_status(207,'Multi-Status')
        ET.ElementTree(root).write(self.response.out, encoding='utf-8')
    
    def mkcol(self):
        """Creates a subdirectory, given an absolute path."""
        path = self.request_path
        parent_path = os.path.dirname(path)
        
        # check for duplicate
        if Resource.exists_with_path(path):
            return self.response.set_status(405,"Method Not Allowed")
        
        # fetch parent
        if parent_path:
            parent = Resource.get_by_path(parent_path)
            if not parent:
                return self.response.set_status(409,"Conflict") # must create parent folder first
        else:
            parent = Resource.root()
        
        logging.info("Creating dir at %s" % path)
        collection = Resource(path=path,parent_resource=parent,is_collection=True)
        collection.put()
        
        self.response.set_status(201,'Created')
    
    def delete(self):
        """Deletes a resource at a url. If it's a collection, it must be empty."""
        path = self.request_path
        resource = Resource.get_by_path(path)

        if not resource:
            return self.response.set_status(404,"Not Found")
        
        resource.delete_recursive()
    
    def move(self):
        """Moves a resource from one path to another."""
        path = self.request_path
        resource = Resource.get_by_path(path)
        
        if not resource:
            return self.response.set_status(404,"Not Found")

        overwrite = self.request.headers.get('Overwrite','T')
        destination = self.request.headers['Destination'] # exception if not present
        
        destination_path = self.url_to_path(urlparse(destination).path)
        parent_path = os.path.dirname(destination_path)
        
        if path == destination_path:
            return self.response.set_status(403,"Forbidden")
        
        # anything at this path already?
        existing_resource = Resource.get_by_path(destination_path)
        
        if existing_resource:
            if overwrite == 'T':
                existing_resource.delete_recursive()
            else:
                return self.response.set_status(412,"Precondition Failed")
        
        # fetch parent
        if parent_path:
            parent = Resource.get_by_path(parent_path)
            if not parent or not parent.is_collection:
                return self.response.set_status(409,"Conflict") # must create parent folder first
        else:
            parent = Resource.root()
        
        resource.parent_resource = parent # reparent this node
        resource.move_to_path(destination_path)
        
        self.response.set_status(204 if existing_resource else 201)
    
    def put(self):
        """Uploads a file."""
        path = self.request_path
        parent_path = os.path.dirname(path)

        # anything at this path already?
        existing_resource = Resource.get_by_path(path)
        
        if existing_resource:
            existing_resource.delete_recursive()

        # fetch parent
        if parent_path:
            parent = Resource.get_by_path(parent_path)
            if not parent or not parent.is_collection:
                return self.response.set_status(409,"Conflict") # must create parent folder first
        else:
            parent = Resource.root()
        
        logging.info("Creating resource at %s" % path)
        data = ResourceData(blob=self.request.body)
        data.put()
        
        resource = Resource(path=path,parent_resource=parent,data=data)
        resource.content_length = len(self.request.body)
        resource.put()

        self.response.set_status(201,'Created')
    
    def head(self):
        """Gets information about a resource sans the data itself."""
        self.get() # app engine will chop off the body for us, this is the only way to make Google send a Content-Length header without the actual body being that length.
        
    def get(self):
        """Downloads a file."""
        path = self.request_path
        
        resource = Resource.get_by_path(path)
        
        if not resource:
            return self.response.set_status(404,"Not Found")
        
        if resource.is_collection:
            template_values = {
                'path': path,
                'prefix': self._prefix,
                'resources': [child for child in resource.children if not child.display_name.startswith('.')]
            }

            template_path = os.path.join(os.path.dirname(__file__), 'templates/collection.html')
            self.response.out.write(template.render(template_path, template_values))
        else:
            # deliver the file data
            self.response.headers['Content-Type'] = resource.content_type_or_default
            self.response.out.write(resource.data.blob)
    
    def lock(self):
        """Locks a resource. We don't actually support this so we'll just send the expected 'success!' response."""
        depth = self.request.headers.get('depth','0')
        timeout = self.request.headers.get('Timeout',None)
        
        root = ET.Element('prop',{'xmlns':'DAV:'})
        lockdiscovery = ET.SubElement(root, 'lockdiscovery')
        activelock = ET.SubElement(lockdiscovery, 'activelock')
        ET.SubElement(activelock, 'lockscope')
        ET.SubElement(activelock, 'locktype')
        ET.SubElement(activelock, 'depth').text = depth
        ET.SubElement(activelock, 'owner')
        ET.SubElement(activelock, 'timeout').text = timeout
        
        locktoken = ET.SubElement(activelock, 'locktoken')
        ET.SubElement(locktoken, 'href').text = 'opaquelocktoken:' # copying box.net
        
        self.response.headers['Content-Type'] = 'text/xml; charset="utf-8"'
        ET.ElementTree(root).write(self.response.out, encoding='utf-8')
    
    def unlock(self):
        """We don't actually support locking so we'll just pretent it worked, OK?"""
        self.response.set_status(204,"No Content")






