import uuid
import json
import datetime
import pytz

from django.conf import settings
from django.utils import dateparse
from django.db.models import *
from django.core.validators import RegexValidator

from api_key.models import ApiKey


class RawData(Model):
    apikey = CharField(max_length=128)
    sensor_id = CharField(max_length=128)
    timestamp_recieved = DateTimeField(  ) 
    timestamp_data = DateTimeField( )
    value = CharField( max_length = 128 )
    extra_data = TextField( null = True , blank = True )
    parsed = BooleanField(default = False)

    
    def save(self,*args, **kwargs):
        if self.timestamp_recieved is None:
            self.timestamp_recieved = datetime.datetime.now( pytz.utc )
        super(RawData , self).save(*args , **kwargs)
        


    @classmethod
    def is_valid(cls , data):
        valid = True
        if data is None:
            valid = False
        
        if valid:
            for key in ["key" , "sensorid" , "value" , "timestamp"]:
                if not key in data:
                    valid = False
        
        if valid:
            ts = TimeStamp.parse_datetime( data["timestamp"] )
            if ts is None:
                valid = False

        if valid and settings.FORCE_VALID_KEY:
            valid = ApiKey.valid( data["key"] )
            
        return valid

    
    @classmethod
    def error(cls , data ):
        if data is None:
            return "Error: empty payload"
        
        missing_keys = []
        for key in ["key" , "sensorid" , "value" , "timestamp"]:
            if not key in data:
                missing_keys.append( key )
        if missing_keys:
            return "Error: missing fields in payload: %s" % missing_keys

        ts = TimeStamp.parse_datetime( data["timestamp"] )
        if ts is None:
            return "Error: invalid timestamp - expected: YYYY-MM-DDTHH:MM:SS+zz"

        if settings.FORCE_VALID_KEY:
            if not ApiKey.valid( data["key"] ):
                return "Error: invalid key"


        return None


    @classmethod
    def create(cls , data):
        if cls.is_valid(data):
            rd = RawData( apikey = data["key"],
                          sensor_id = data["sensorid"],
                          timestamp_data = TimeStamp.parse_datetime( data["timestamp"]),
                          value = data["value"] )
            del data["key"]
            del data["sensorid"]
            del data["value"]
            del data["timestamp"]
            if data:
                rd.extra_data = json.dumps( data )
            rd.save()
            
            return rd
        else:
            raise ValueError("Invalid input data")


class Location( Model ):
    name = CharField("Location" , max_length = 60 )
    latitude = FloatField("Latitude")
    longitude = FloatField("Longitude")
    altitude = FloatField("Altitude" , null = True)

    def __unicode__(self):
        return self.name


class DataType( Model ):
    id = CharField("DataType" , max_length = 60 , primary_key = True)

    def __unicode__(self):
        return self.id


class Company( Model ):
    name = CharField("Device manufacturer" , max_length = 60)

    def __unicode__(self):
        return self.name


class DeviceType( Model ):
    name = CharField("Name of the device" , max_length = 60 )
    company = ForeignKey( Company )

    def __unicode__(self):
        return self.name


class Device( Model ):
    IDPattern = "[-_:a-zA-Z0-9]+"

    id = CharField("Device ID" , max_length = 60 , primary_key = True , validators = [RegexValidator(regex = "^%s$" % IDPattern)])
    location = ForeignKey( Location , null = True )
    device_type = ForeignKey( DeviceType )
    description = CharField("Description" , max_length = 256 )

    def __unicode__(self):
        return self.id


class MeasurementType( Model ):
    name = CharField("Type of measurement" , max_length = 60)
    
    def __unicode__(self):
        return self.name


class TimeStamp( Model ):
    # When parsing a string the format should be as: "2015-10-10T10:10:00+01";
    # i.e. yyyy-mm-ddTHH:MM:SS+zz
    # Where the +zz is a timezone shift relative to UTC; i.e. +01 for Central European Time.

    timestamp = DateTimeField("timestamp")

    def __unicode__(self):
        return str(self.timestamp)


    @classmethod
    # This takes a time_string which is supposed to be in the time
    # zone given by the settings.TIME_ZONE variable. The resulting
    # dt variable is a time zone aware datetime instance.
    def parse_datetime(cls , time_string ):
        dt = dateparse.parse_datetime( time_string )
        return dt

    


class SensorType( Model ):
    product_name = CharField( "Product name" , max_length = 256 )
    company = ForeignKey( Company )
    short_description = CharField("Short description" , max_length = 40)
    measurement_type = ForeignKey( MeasurementType )
    description = CharField("Description" , max_length = 256 )
    unit = CharField("Unit" , max_length = 60 )
    min_value = FloatField("Minimum value")
    max_value = FloatField("Maximum value")

    def __unicode__(self):
        return self.short_description
        

    def valid_input(self , value):
        if not isinstance(value,float):
            try:
                value = float(value)
            except:
                return False
                
        if self.min_value <= value <= self.max_value:
            return True

        return False




class Sensor( Model ):
    IDPattern = "[-_:a-zA-Z0-9]+"

    id = CharField("Sensor ID" , max_length = 60 , primary_key = True , validators = [RegexValidator(regex = "^%s$" % IDPattern)])
    sensor_type = ForeignKey( SensorType )
    location = ForeignKey( Location , null = True )
    parent_device = ForeignKey( Device )
    data_type = ForeignKey( DataType , default = "TEST" )
    description = CharField("Description" , max_length = 256 )
    post_key = ForeignKey( ApiKey )

    def __unicode__(self):
        return self.id
        

    def valid_input(self , input_value):
        return self.sensor_type.valid_input( input_value )


    def get_ts(self, data_type = None):
        if data_type is None:
            data_type = self.data_type

        ts = []
        for data_value in DataValue.objects.filter( data_type = data_type , data_info__sensor = self).order_by('data_info__timestamp__timestamp'):
            ts.append( (data_value.data_info.timestamp.timestamp , data_value.value))

        return ts

    def valid_post_key( self , key_string):
        return self.post_key.access( key_string )



class DataInfo( Model ):
    location = ForeignKey( Location )
    timestamp = ForeignKey( TimeStamp )
    sensor = ForeignKey( Sensor )

    
    def __unicode__(self):
        return "%s @ %s" % ( self.sensor , self.timestamp )

    
    def save(self , *args, **kwargs):
        # If the sensor indeed has a location you should not supply an
        # extra location with the DataInfo() object. In case you the
        # location from the sensor will override anyway.
        if not self.sensor.location is None:
            self.location = self.sensor.location
        super(DataInfo , self).save(*args , **kwargs)




class DataValue( Model ):
    data_type = ForeignKey( DataType )
    data_info = ForeignKey( DataInfo )
    value = FloatField( )
    
    def __unicode__(self):
        return "%s: %s" % (str(self.data_info) , str(self.value))

    def save(self , *args , **kwargs):
        if self.data_info.sensor.valid_input( self.value ):
            super(DataValue , self).save(*args , **kwargs)
        else:
            raise ValueError("Tried to save invalid value:%s for sensor:%s" % (self.value , self.data_info.sensor))
        
