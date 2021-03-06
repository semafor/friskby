import json

from django.urls import reverse
from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from rest_framework import status

from sensor.models import *
from .context import TestContext


class DeviceTest(TestCase):
    def setUp(self):
        self.context = TestContext( )


    def test_get_config(self):
        client = Client( )
        response = client.get( reverse("sensor.device_config" , args = ["XXX"]))
        self.assertEqual( response.status_code , status.HTTP_404_NOT_FOUND )

        url = reverse( "sensor.device_config" , args = [ self.context.dev.id ])
        response = client.get( url )
        self.assertEqual( response.status_code , status.HTTP_200_OK )

        data = json.loads(response.content)
        self.assertTrue( "client_config" in data )

        client_config = data["client_config"]
        self.assertFalse( "post_key" in client_config )

        self.assertEqual( len(self.context.dev.sensorList( )) , 2 )
        sensor_list = client_config["sensor_list"]
        self.assertEqual( len(sensor_list) , 2 )

        self.assertTrue( "TEMP:XX" in sensor_list )
        self.assertTrue( "HUM:XX" in sensor_list )

        self.assertFalse( "git_repo" in client_config )
        self.assertFalse( "git_ref" in client_config )
        self.assertFalse( "git_follow" in client_config )

        self.context.dev.git_version = self.context.git_version
        self.context.dev.save(  )
        response = client.get("/sensor/api/device/%s/" % self.context.dev.id)
        data = json.loads(response.content)
        client_config = data["client_config"]

        self.assertEqual( client_config["git_repo"] , self.context.git_version.repo )
        self.assertEqual( client_config["git_ref"] , self.context.git_version.ref )
        self.assertEqual( client_config["git_follow"] , self.context.git_version.follow_head )
        self.assertTrue( "post_path" in client_config )
        self.assertTrue( "config_path" in client_config )
        self.assertEqual( client_config["device_id"] , self.context.dev.id )



    def test_get_open_config(self):
        device = Device.objects.get( pk = self.context.dev.id )
        device.locked = False
        device.save( )

        client = Client( )
        url = reverse( "sensor.device_config" , args = [ self.context.dev.id ])
        response = client.get( url )
        data = json.loads(response.content)
        client_config = data["client_config"]
        self.assertTrue( self.context.dev.valid_post_key( client_config["post_key"] ))
        device.locked = True
        device.save( )


    def test_get_closed_config(self):
        device = Device.objects.get( pk = self.context.dev.id )

        # Invalid key supplied - closed device
        client = Client( )
        url = reverse( "sensor.device_config" , args = [ self.context.dev.id ])
        response = client.get( url , {"key" : "Invalid"})
        self.assertEqual( response.status_code , status.HTTP_403_FORBIDDEN )

        response = client.get( url , {"key" : device.post_key.external_key})
        data = json.loads(response.content)
        client_config = data["client_config"]
        self.assertTrue( self.context.dev.valid_post_key( client_config["post_key"] ))




    def test_post_version(self):
        client = Client( )
        device_id = self.context.dev.id

        # Invalid key -> 403
        data = {"key" : "Invalid key" , "git_ref" : "abcdef"}
        url = reverse( "sensor.device_config" , args = [ self.context.dev.id ])
        response = client.put( url,
                               data = json.dumps( data ) ,
                               content_type = "application/json")
        self.assertEqual( response.status_code , status.HTTP_403_FORBIDDEN )

        # Missing key -> 403
        data = {"git_ref" : "abcdef"}
        response = client.put(url,
                              data = json.dumps( data ) ,
                              content_type = "application/json")
        self.assertEqual( response.status_code , status.HTTP_403_FORBIDDEN )


        # Invalid sensor -> 404
        data = {"key" : "Invalid key" , "git_ref" : "abcdef"}
        invalid_url = reverse( "sensor.device_config" , args = [ "NOXXX" ])
        response = client.put( invalid_url,
                               data = json.dumps( data ) ,
                               content_type = "application/json")
        self.assertEqual( response.status_code , status.HTTP_404_NOT_FOUND )


        # No data -> 204
        data = {"key" : str(self.context.dev.post_key.external_key)}
        response = client.put( url,
                               data = json.dumps( data ) ,
                               content_type = "application/json")
        self.assertEqual( response.status_code , status.HTTP_204_NO_CONTENT )

        # All good -> 200
        data = {"key" : str(self.context.dev.post_key.external_key) , "git_ref" : "abcdef"}
        response = client.put(url,
                              data = json.dumps( data ) ,
                              content_type = "application/json")
        self.assertEqual( response.status_code , status.HTTP_200_OK )

        device = Device.objects.get( pk = device_id )
        self.assertEqual( device.client_version , "abcdef")


    def test_post_log(self):
        client = Client( )
        device_id = self.context.dev.id

        # Invalid key -> 403
        data = {"device_id" : device_id , "key" : "Invalid key" , "msg" : "Msg"}
        url = reverse("sensor.api.client_log")
        response = client.post(url,
                               data = json.dumps( data ) ,
                               content_type = "application/json")
        self.assertEqual( response.status_code , status.HTTP_403_FORBIDDEN )


        # Invalid device_id -> 400
        data = {"device_id" : "invalid_device" ,
                "key" : str(self.context.dev.post_key.external_key) ,
                "msg" : "Msg"}

        response = client.post(url,
                               data = json.dumps( data ) ,
                               content_type = "application/json")
        self.assertEqual( response.status_code , status.HTTP_400_BAD_REQUEST )

        data = {"device_id" : "invalid_device" ,
                "key" : str(self.context.dev.post_key.external_key) ,
                "msg" : "Msg"}

        response = client.post(url,
                               data = json.dumps( data ) ,
                               content_type = "application/json")
        self.assertEqual( response.status_code , status.HTTP_400_BAD_REQUEST )


        # All good : 201
        data = {"device_id" : device_id,
                "key" : str(self.context.dev.post_key.external_key) ,
                "msg" : "Msg"}

        response = client.post(url,
                               data = json.dumps( data ) ,
                               content_type = "application/json")
        self.assertEqual( response.status_code , 201 )


        # All good with long_msg: 201
        data = {"device_id" : device_id,
                "key" : str(self.context.dev.post_key.external_key) ,
                "msg" : "Msg",
                "long_msg" : "LONG"}

        response = client.post(url,
                               data = json.dumps( data ) ,
                               content_type = "application/json")
        self.assertEqual( response.status_code , 201 )


        # Get : 200
        response = client.get(url)
        self.assertEqual( len(response.data) , 2 )
        last = response.data[1]
        self.assertEqual( last["long_msg"] , "LONG")
