from google.appengine.ext import db
from xml.etree import ElementTree as ET
import os
import mimetypes
from urllib import pathname2url

class ResourceData(db.Model):
    blob = db.BlobProperty()

class Resource(db.Model):
    path = db.StringProperty() # full path, not just the name, no trailing slash
    parent_resource = db.SelfReferenceProperty(collection_name="children")
    is_collection = db.BooleanProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    modified = db.DateTimeProperty(auto_now=True)
    content_language = db.StringProperty()
    content_length = db.IntegerProperty()
    content_type = db.StringProperty()
    etag = db.StringProperty()
    data = db.ReferenceProperty(ResourceData)

    @classmethod
    def root(cls):
        root = Resource.all().filter('parent_resource', None).get()
        
        if not root:
            root = Resource(path='',is_collection=True)
            root.put()
        
        return root
    
    @classmethod
    def exists_with_path(cls,path,is_collection=None):
        query = Resource.all(keys_only=True).filter('path', path)
        
        if is_collection != None:
            query = query.filter('is_collection',True)
        
        return query.get() != None
    
    @classmethod
    def get_by_path(cls,path):
        return Resource.all().filter('path', path).get() if path else Resource.root()
    
    @property
    def display_name(self):
        return os.path.basename(self.path)
    
    @property
    def path_as_url(self):
        return pathname2url(self.path)
    
    @property
    def content_type_or_default(self):
        if self.is_collection:
            return 'httpd/unix-directory'
        else:
            mimetype = mimetypes.guess_type(self.path,strict=False)[0]
            return mimetype if mimetype else 'application/octet-stream'
    
    def move_to_path(self, destination_path):
        """Moves this resource and all its children (if applicable) to a new path.
           Assumes that the new path is free and clear."""

        if self.is_collection:
            for child in self.children:
                child_name = os.path.basename(child.path)
                child_path = os.path.join(destination_path,child_name)
                child.move_to_path(child_path)
        
        self.path = destination_path
        self.put()
    
    def delete(self):
        """Override delete to delete our associated ResourceData entity automatically."""
        if self.data:
            self.data.delete()
        super(Resource, self).delete()
    
    def delete_recursive(self):
        """Deletes this entity plus all of its children and other descendants."""
        if self.is_collection:
            for child in self.children:
                child.delete_recursive()
        self.delete()

    def export_response(self,href=None):
        datetime_format = '%Y-%m-%dT%H:%M:%SZ'
        
        response = ET.Element('response')
        ET.SubElement(response, 'href').text = href
        propstat = ET.SubElement(response,'propstat')
        prop = ET.SubElement(propstat,'prop')
        
        ET.SubElement(prop, 'creationdate').text = self.created.strftime(datetime_format)
        ET.SubElement(prop, 'displayname').text = self.display_name
        ET.SubElement(prop, 'getcontentlanguage').text = str(self.content_language)
        ET.SubElement(prop, 'getcontentlength').text = str(self.content_length)
        ET.SubElement(prop, 'getcontenttype').text = str(self.content_type_or_default)

        ET.SubElement(prop, 'getlastmodified').text = self.modified.strftime(datetime_format)

        resourcetype = ET.SubElement(prop,'resourcetype')
        
        if self.is_collection:
            ET.SubElement(resourcetype, 'collection')

        ET.SubElement(propstat,'status').text = "HTTP/1.1 200 OK"
        return response
