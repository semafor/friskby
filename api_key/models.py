import uuid
from django.db.models import *


class ApiKey( Model ):
    external_key = UUIDField( default=uuid.uuid4 , unique = True )
    description = CharField( max_length = 256 )

    
    def __unicode__(self):
        return "%s: %s" % ( self.description , str(self.external_key))


    def access(self , external_key):
        if str(self.external_key) == external_key:
            return True
        else:
            return False
            
            
    def reset(self):
        self.external_key = uuid.uuid4( )
        self.save( )