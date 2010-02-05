#!/usr/bin/python
# -*- coding: utf-8 -*-

""" This file is part of B{Domogik} project (U{http://www.domogik.org}).

License
=======

B{Domogik} is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

B{Domogik} is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Domogik. If not, see U{http://www.gnu.org/licenses}.

Module purpose
==============

REST support for Domogik project

Implements
==========

- RestHandler.do_GET
- RestHandler.do_POST
- RestHandler.do_OPTIONS
- RestHandler.rest_command
- RestHandler.rest_xpl_cmnd
- RestHandler.send_http_response_ok
- RestHandler.send_http_response_error

- XmlRpcDbHelper


@author: Friz <fritz.smh@gmail.com>
@copyright: (C) 2007-2009 Domogik project
@license: GPL(v3)
@organization: Domogik
"""
from domogik.xpl.lib.xplconnector import *
from domogik.xpl.common.xplmessage import XplMessage
from domogik.xpl.lib.module import *
from domogik.common import logger
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from domogik.common.database import DbHelper
from domogik.common.configloader import Loader
from xml.dom import minidom
import json
import time
import urllib




################################################################################
class Rest(xPLModule):

    def __init__(self, ip, port):
        xPLModule.__init__(self, name = 'rest')

        # logging initialization
        l = logger.Logger('REST')
        self._log = l.get_logger()
        self._log.info("Rest Server initialisation...")

        # DB Helper
        self._db = DbHelper()

        # Congig
        cfg = Loader('domogik')
        config = cfg.load()
        db = dict(config[1])
        self._xml_directory = "%s/xml/rest/" % db['cfg_path']


        # Start HTTP server
        server = HTTPServerWithParam((ip, int(port)), RestHandler, handler_params = [self])
        print 'Start REST server on port %s...' % port
        server.serve_forever()


    def get_helper(self):
        return self._db


################################################################################
class HTTPServerWithParam(HTTPServer):
    """ Extends HTTPServer to allow send params to the Handler.
    """

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True, handler_params = []):
        HTTPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.handler_params = handler_params






################################################################################
class RestHandler(BaseHTTPRequestHandler):


######
# GET/POST/OPTIONS processing
######

    def do_GET(self):
        """ Process GET requests
        """
        print "==== GET ============================================"
        self.do_FOR_ALL_METHODS()

    def do_POST(self):
        """ Process POST requests
        """
        print "==== POST ==========================================="
        self.do_FOR_ALL_METHODS()

    def do_OPTIONS(self):
        """ Process OPTIONS requests
        """
        print "==== OPTIONS ==========================================="
        self.do_FOR_ALL_METHODS()

    def do_FOR_ALL_METHODS(self):
        request = ProcessRequest(self.server.handler_params, self.path, self.send_http_response_ok, self.send_http_response_error)
        request.do_FOR_ALL_METHODS()




######
# HTTP return
######

    def send_http_response_ok(self, data = ""):
        self.send_response(200)
        self.send_header('Content-type',  'application/json')
        self.send_header('Expires', '-1')
        self.send_header('Cache-control', 'no-cache')
        self.end_headers()
        if data:
            self.wfile.write(data.encode("utf-8"))
        ### TODO : log this


    def send_http_response_error(self, errCode, errMsg, jsonp, jsonp_cb):
        self.send_response(200)
        self.send_header('Content-type',    'text/html')
        self.end_headers()
        json = JSonHelper("ERROR", errCode, errMsg)
        json.set_jsonp(jsonp, jsonp_cb)
        self.wfile.write(json.get())
        ### TODO : log this




################################################################################
class ProcessRequest():

######
# init namespace
######


    def __init__(self, handler_params, path, cb_send_http_response_ok, cb_send_http_response_error):
        """ Create shorter access : self.server.handler_params[0].* => self.*
            First processing on url given
        """

        self.handler_params = handler_params
        self.path = path
        self.send_http_response_ok = cb_send_http_response_ok
        self.send_http_response_error = cb_send_http_response_error

        # shorter access
        self._db = self.handler_params[0]._db
        self._myxpl = self.handler_params[0]._myxpl
        self._log = self.handler_params[0]._log
        self._xml_directory = self.handler_params[0]._xml_directory

        # global init
        self.jsonp = False
        self.jsonp_cb = ""

        # url processing
        print "====DEBUGPATH======"
        self.path = str(urllib.unquote(self.path))
        self.path = unicode(self.path, "utf-8")
        print "===================="

        tab_url = self.path.split("?")
        self.path = tab_url[0]
        if len(tab_url) > 1:
            self.parameters = tab_url[1]
            self._parse_options()

        if self.path[-1:] == "/":
            self.path = self.path[0:len(self.path)-1]
        print "PATH : " + self.path
        tab_path = self.path.split("/")

        # Get type of request : /command, /xpl-cmnd, /base, etc
        if len(tab_path) < 2:
            self.rest_type = None
            self.send_http_response_error(999, "No type given", self.jsonp, self.jsonp_cb)
            return
        self.rest_type = tab_path[1].lower()
        if len(tab_path) > 2:
            self.rest_request = tab_path[2:]
        else:
            self.rest_request = []
        print "TYPE    : " + self.rest_type
        print "Request : " + str(self.rest_request)





    def do_FOR_ALL_METHODS(self):
        if self.rest_type == "command":
            self.rest_command()
        elif self.rest_type == "xpl-cmnd":
            self.rest_xpl_cmnd()
        elif self.rest_type == "base":
            self.rest_base()
        else:
            self.send_http_response_error(999, "Type [" + str(self.rest_type) + "] is not supported", self.jsonp, self.jsonp_cb)
            return



    def _parse_options(self):
        """Take parameters in count 
           Or do debug stuff in function of parameters given
        """

        # for each debug option
        for opt in self.parameters.split("&"):
            print "OPT :" + opt
            tab_opt = opt.split("=")
            opt_key = tab_opt[0]
            if len(tab_opt) > 1:
                opt_value = tab_opt[1]
            else:
                opt_value = None

            # call json specific options
            if opt_key == "callback" and opt_value != None:
                self.jsonp = True
                self.jsonp_cb = opt_value

            # call debug functions
            elif opt_key == "debug-sleep" and opt_value != None:
                self._debug_sleep(opt_value)



    def _debug_sleep(self, duration):
        """ Sleep process for 15 seconds
        """
        print "DEBUG : start sleeping for " + str(duration)
        time.sleep(float(duration))
        print "DEBUG : end sleeping"




######
# /command processing
######

    def rest_command(self):
        print "Call rest_command"

        # parse data in URL
        if len(self.rest_request) >= 3:
            techno = self.rest_request[0]
            address = self.rest_request[1]
            order = self.rest_request[2]
            if len(self.rest_request) > 3:
                others = self.rest_request[3:]
            else:
                others = None
        else:
            json = JSonHelper("ERROR", 999, "Url too short for /command")
            json.set_jsonp(self.jsonp, self.jsonp_cb)
            self.send_http_response_ok(json.get())
            return
        print "Techno    : %s" % techno
        print "Address   : %s" % address
        print "Order     : %s" % order
        print "Others    : %s" % str(others)

        # open xml file
        #xml_file = "%s/%s.xml" % (self._xml_directory, techno)
        xml_file = "%s/%s.xml" % ("../xml/", techno)
        # process xml
        message = self._parse_xml(xml_file, techno, address, order, others)
        if message == None:
            return

        print "Send message : %s" % message
        self._myxpl.send(message)

        # REST processing finished and OK
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        self.send_http_response_ok(json.get())

        





    def _parse_xml(self, xml_file, techno, address, order, others):
        try:
            xml_doc = minidom.parse(xml_file)
        except:
            json = JSonHelper("ERROR", 999, "Error while reading xml file : " + xml_file)
            json.set_jsonp(self.jsonp, self.jsonp_cb)
            self.send_http_response_ok(json.get())
            return None

        mapping = xml_doc.documentElement
        if mapping.getElementsByTagName("technology")[0].attributes.get("name").value != techno:
            self.send_http_response_error(999, "'technology' attribute must be the same as file name !", self.jsonp, self.jsonp_cb)
            return
        
        #Schema
        schema = mapping.getElementsByTagName("schema")[0].firstChild.nodeValue

        #Device key name
        device = mapping.getElementsByTagName("device")[0]
        if device.getElementsByTagName("key") != []:
            device_address_key = device.getElementsByTagName("key")[0].firstChild.nodeValue
        else:
            device_address_key = None

        #Orders
        orders = mapping.getElementsByTagName("orders")[0]
        order_key = orders.getElementsByTagName("key")[0].firstChild.nodeValue

        #Get the good order bloc :
        the_order = None
        for an_order in orders.getElementsByTagName("order"):
            if an_order.getElementsByTagName("name")[0].firstChild.nodeValue == order:
                the_order = an_order
        if the_order == None:
            self.send_http_response_error(999, "Order can't be found", self.jsonp, self.jsonp_cb)
            return

        #Parse the order bloc
        order_value = the_order.getElementsByTagName("value")[0].firstChild.nodeValue
        #mandatory parameters
        mandatory_parameters_value = {}
        optional_parameters_value = {}
        if the_order.getElementsByTagName("parameters")[0].hasChildNodes():
            mandatory_parameters = the_order.getElementsByTagName("parameters")[0].getElementsByTagName("mandatory")[0]
            count_mandatory_parameters = len(mandatory_parameters.getElementsByTagName("parameter"))
            mandatory_parameters_from_url = others[3:3+count_mandatory_parameters]
            for mandatory_param in mandatory_parameters.getElementsByTagName("parameter"):
                key = mandatory_param.attributes.get("key").value
                value = mandatory_parameters_from_url[int(mandatory_param.attributes.get("location").value) - 1]
                mandatory_parameters_value[key] = value
            #optional parameters
            if the_order.getElementsByTagName("parameters")[0].getElementsByTagName("optional") != []:
                optional_parameters =  the_order.getElementsByTagName("parameters")[0].getElementsByTagName("optional")[0]
                for opt_param in optional_parameters.getElementsByTagName("parameter"):
                    ind = others.index(opt_param.getElementsByTagName("name")[0])
                    optional_parameters_value[url[ind]] = url[ind + 1]

        return self._forge_msg(schema, device_address_key, address, order_key, order_value, mandatory_parameters_value, optional_parameters_value)








    def _forge_msg(self, schema, device_address_key, address, order_key, order_value, mandatory_parameters_value, optional_parameters_value):
        msg = """xpl-cmnd
{
hop=1
source=rest
target=*
}
%s
{
%s=%s
%s=%s
""" % (schema, device_address_key, address, order_key, order_value)
        for m_param in mandatory_parameters_value.keys():
            msg += "%s=%s\n" % (m_param, mandatory_parameters_value[m_param])
        for o_param in optional_parameters_value.keys():
            msg += "%s=%s\n" % (o_param, optional_parameters_value[o_param])
        msg += "}"
        return msg





        



######
# /xpl-cmnd processing
######

    def rest_xpl_cmnd(self):
        """ Send xPL message given in REST url
            1/ Decode and check URL
            2/ Send message
        """

        print "Call rest_xpl_cmnd"
        if len(self.rest_request) == 0:
            self.send_http_response_error(999, "Target not given", self.jsonp, self.jsonp_cb)
            return
        self.xpl_target = self.rest_request[0]
        if len(self.rest_request) == 1:
            self.send_http_response_error(999, "Schema not given", self.jsonp, self.jsonp_cb)
            return
        self.xpl_cmnd_schema = self.rest_request[1]

        # Init xpl message
        message = XplMessage()
        message.set_type('xpl-cmnd')
        if self.xpl_target.lower() != "all":
            message.set_header(target=self.xpl_target)
        message.set_schema(self.xpl_cmnd_schema)
  
        ii = 0
        for val in self.rest_request:
            # We pass target and schema
            if ii > 1:
                # Parameter
                if ii % 2 == 0:
                    param = val
                # Value
                else:
                    value = val
                    message.add_data({param : value})
            ii = ii + 1

        # no parameters
        if ii == 2:
            self.send_http_response_error(999, "No parameters specified", self.jsonp, self.jsonp_cb)
            return
        # no value for last parameter
        if ii % 2 == 1:
            self.send_http_response_error(999, "Value missing for last parameter", self.jsonp, self.jsonp_cb)
            return

        print "Send message : %s" % message
        self._myxpl.send(message)

        # REST processing finished and OK
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        self.send_http_response_ok(json.get())




######
# /base processing
######

    def rest_base(self):
        """ get data in database
            1/ Decode and check URL
            2/ call the good fonction to get data
        """
        print "Call rest_base_get"
        self.parameters = {}
        if len(self.rest_request) < 2:
            self.send_http_response_error(999, "Url too short", self.jsonp, self.jsonp_cb)
            return

        ### area #####################################
        if self.rest_request[0] == "area":

            ### list
            if self.rest_request[1] == "list":
                if len(self.rest_request) == 2:
                    self._rest_base_area_list()
                elif len(self.rest_request) == 3:
                    self.send_http_response_error(999, "Wrong syntax for " + self.rest_request[1], self.jsonp, self.jsonp_cb)
                else:
                    if self.rest_request[2] == "by-id":
                        self._rest_base_area_list(id=self.rest_request[3])

            ### add
            elif self.rest_request[1] == "add":
                offset = 2
                if self.set_parameters(offset):
                    self._rest_base_area_add(self.parameters)
                else:
                    self.send_http_response_error(999, "No parameters given", self.jsonp, self.jsonp_cb)

            ### update
            elif self.rest_request[1] == "update":
                offset = 2
                if self.set_parameters(offset):
                    self._rest_base_area_update(self.parameters)
                else:
                    self.send_http_response_error(999, "No parameters given", self.jsonp, self.jsonp_cb)

            ### del
            elif self.rest_request[1] == "del":
                if len(self.rest_request) == 3:
                    self._rest_base_area_del(id=self.rest_request[2])
                else:
                    self.send_http_response_error(999, "Wrong syntax for " + self.rest_request[1], self.jsonp, self.jsonp_cb)

            ### others
            else:
                self.send_http_response_error(999, self.rest_request[1] + " not allowed for " + self.rest_request[0], self.jsonp, self.jsonp_cb)
                return

        ### room #####################################
        elif self.rest_request[0] == "room":

            ### list
            if self.rest_request[1] == "list":
                if len(self.rest_request) == 2:
                    self._rest_base_room_list()
                elif len(self.rest_request) == 3:
                    self.send_http_response_error(999, "Wrong syntax for " + self.rest_request[1], self.jsonp, self.jsonp_cb)
                else:
                    if self.rest_request[2] == "by-id":
                        self._rest_base_room_list(id=self.rest_request[3])
                    elif self.rest_request[2] == "by-area":
                        self._rest_base_room_list(area_id=self.rest_request[3])

            ### add
            elif self.rest_request[1] == "add":
                offset = 2
                if self.set_parameters(offset):
                    self._rest_base_room_add(self.parameters)
                else:
                    self.send_http_response_error(999, "No parameters given", self.jsonp, self.jsonp_cb)

            ### update
            elif self.rest_request[1] == "update":
                offset = 2
                if self.set_parameters(offset):
                    self._rest_base_room_update(self.parameters)
                else:
                    self.send_http_response_error(999, "No parameters given", self.jsonp, self.jsonp_cb)

            ### del
            elif self.rest_request[1] == "del":
                if len(self.rest_request) == 3:
                    self._rest_base_room_del(id=self.rest_request[2])
                else:
                    self.send_http_response_error(999, "Wrong syntax for " + self.rest_request[1], self.jsonp, self.jsonp_cb)

            ### others
            else:
                self.send_http_response_error(999, self.rest_request[1] + " not allowed for " + self.rest_request[0], self.jsonp, self.jsonp_cb)
                return

        ### ui_config ################################
        elif self.rest_request[0] == "ui_config":

            ### list
            if self.rest_request[1] == "list":
                if len(self.rest_request) == 2:
                    self._rest_base_ui_config_list()
                elif len(self.rest_request) == 3 or len(self.rest_request) == 4:
                    self.send_http_response_error(999, "Wrong syntax for " + self.rest_request[1], self.jsonp, self.jsonp_cb)
                else:
                    if self.rest_request[2] == "by-item":
                        if len(self.rest_request) == 5:
                            self._rest_base_ui_config_list(item_type=self.rest_request[3], item_id=self.rest_request[4])
                        else:
                            if len(self.rest_request) == 6:
                                self.send_http_response_error(999, "Wrong syntax for " + self.rest_request[1], self.jsonp, self.jsonp_cb)
                            else:
                                if self.rest_request[5] == "by-key":
                                    self._rest_base_ui_config_list(item_type=self.rest_request[3], item_id=self.rest_request[4], item_key=self.rest_request[6])
                                else:
                                    self.send_http_response_error(999, "Wrong syntax for " + self.rest_request[1], self.jsonp, self.jsonp_cb)

            ### add
            elif self.rest_request[1] == "add":
                offset = 2
                if self.set_parameters(offset):
                    self._rest_base_ui_config_add(self.parameters)
                else:
                    self.send_http_response_error(999, "No parameters given", self.jsonp, self.jsonp_cb)

            ### update
            elif self.rest_request[1] == "update":
                offset = 2
                if self.set_parameters(offset):
                    self._rest_base_ui_config_update(self.parameters)
                else:
                    self.send_http_response_error(999, "No parameters given", self.jsonp, self.jsonp_cb)

            ### delete
            elif self.rest_request[1] == "del":
                offset = 2
                if self.set_parameters(offset):
                    self._rest_base_ui_config_del(self.parameters)
                else:
                    self.send_http_response_error(999, "No parameters given", self.jsonp, self.jsonp_cb)

            ### others
            else:
                self.send_http_response_error(999, self.rest_request[1] + " not allowed for " + self.rest_request[0], self.jsonp, self.jsonp_cb)
                return


        ### device #####################################
        elif self.rest_request[0] == "device":
            print "TODO !!"

        ### others ###################################
        else:
            self.send_http_response_error(999, self.rest_request[0] + " not allowed", self.jsonp, self.jsonp_cb)
            return






    def set_parameters(self, offset):
        ii = 0
        while offset + ii < len(self.rest_request):
            key = self.rest_request[offset + ii]
            if offset + ii + 1 < len(self.rest_request):
                value = self.rest_request[offset + ii + 1]
            else:
                self.send_http_response_error(999, "Value missing for " + key, self.jsonp, self.jsonp_cb)
                return
            self.parameters[key] = value
            ii += 2
        if ii == 0:
            return False
        else:
            return True







    def get_parameters(self, name):
        try:
            return self.parameters[name]
        except KeyError:
            return None







######
# /base/area processing
######

    def _rest_base_area_list(self, id = None):
        """ list areas
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("area")
        if id == None:
            for area in self._db.list_areas():
                json.add_data(area)
        else:
            area = self._db.get_area_by_id(id)
            if area is not None:
                json.add_data(area)
        self.send_http_response_ok(json.get())



    def _rest_base_area_add(self, params):
        """ add areas
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("area")
        try:
            area = self._db.add_area(self.get_parameters("name"), self.get_parameters("description"))
            json.add_data(area)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())



    def _rest_base_area_update(self, params):
        """ update areas
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("area")
        try:
            area = self._db.update_area(self.get_parameters("id"), self.get_parameters("name"), self.get_parameters("description"))
            json.add_data(area)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())




    def _rest_base_area_del(self, id=None):
        """ delete areas
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("area")
        try:
            area = self._db.del_area(id)
            json.add_data(area)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())



######
# /base/room processing
######

    def _rest_base_room_list(self, id = None, area_id = None):
        """ list rooms
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("room")
        if id == None and area_id == None:
            for room in self._db.list_rooms():
                json.add_data(room)
        elif id != None:
            room = self._db.get_room_by_id(id)
            if room is not None:
                json.add_data(room)
        elif area_id != None:
            if area_id == "null":
                area_id = None
            for room in self._db.get_all_rooms_of_area(area_id):
                json.add_data(room)
        self.send_http_response_ok(json.get())



    def _rest_base_room_add(self, params):
        """ add rooms
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("room")
        try:
            room = self._db.add_room(self.get_parameters("name"), self.get_parameters("area_id"), self.get_parameters("description"))
            json.add_data(room)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())



    def _rest_base_room_update(self, params):
        """ update rooms
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("room")
        try:
            room = self._db.update_room(self.get_parameters("name"), self.get_parameters("area_id"), self.get_parameters("description"))
            json.add_data(room)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())



    def _rest_base_room_del(self, id=None):
        """ delete rooms
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("room")
        try:
            room = self._db.del_room(id)
            json.add_data(room)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())


######
# /base/ui_config processing
######

    def _rest_base_ui_config_list(self, item_type = None, item_id = None, item_key = None):
        """ list ui_config
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("ui_config")
        if item_id == None:
            for ui_config in self._db.list_all_item_ui_config():
                json.add_data(ui_config)
        elif item_key == None:
            print "list_item_ui_config : " + str(item_id) + ", " + str(item_type)
            for ui_config in self._db.list_item_ui_config(item_id, item_type):
                json.add_data(ui_config)
        else:
            ui_config = self._db.get_item_ui_config(item_id, item_type, item_key)
            if ui_config is not None:
                json.add_data(ui_config)
        self.send_http_response_ok(json.get())



    def _rest_base_ui_config_add(self, params):
        """ add ui_config
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("ui_config")
        try:
            ui_config = self._db.add_item_ui_config(self.get_parameters("item_id"), self.get_parameters("item_type"), {self.get_parameters("key") : self.get_parameters("value")})
            json.add_data(ui_config)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())


    def _rest_base_ui_config_update(self, params):
        """ update ui_config
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("ui_config")
        try:
            ui_config = self._db.update_item_ui_config(self.get_parameters("item_id"), self.get_parameters("item_type"), self.get_parameters("key"), self.get_parameters("value"))
            json.add_data(ui_config)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())


    def _rest_base_ui_config_del(self, params):
        """ del ui_config
        """
        json = JSonHelper("OK")
        json.set_jsonp(self.jsonp, self.jsonp_cb)
        json.set_data_type("ui_config")
        try:
            if self.get_parameters("key") == None:
                ui_config = self._db.delete_all_item_ui_config(self.get_parameters("item_id"), self.get_parameters("item_type"))
            else:
                ui_config = self._db.delete_item_ui_config(self.get_parameters("item_id"), self.get_parameters("item_type"), self.get_parameters("key"))
            json.add_data(ui_config)
        except:
            json.set_error(code = 999, description = str(sys.exc_info()[1]).replace('"', "'"))
        self.send_http_response_ok(json.get())






################################################################################
class JSonHelper():

    def __init__(self, status = "OK", code = 0, description = ""):
        if status == "OK":
            self.set_ok()
        else:
            self.set_error(code, description)
        self._data_type = ""
        self._data_values = ""
        self._nb_data_values = 0

    def set_jsonp(self, jsonp, jsonp_cb):
        self._jsonp = jsonp
        self._jsonp_cb = jsonp_cb

    def set_ok(self):
        self._status = '"status" : "OK", "code" : 0, "description" : "",'

    def set_error(self, code=0, description=None):
        self._status = '"status" : "ERROR", "code" : ' + str(code) + ', "description" : "' + description + '",'

    def set_data_type(self, type):
        self._data_type = type

    def add_data(self, data):
        data_out = "{"
        self._nb_data_values += 1

        # dirty issue to force data not to be in cache
        if hasattr(data, 'id'):    # for all
            pass
        if hasattr(data, 'area'):  # for room
            pass

        if data == None:
            return
        print "=== DATA ==="
        #print str(data)
        print "============"
        for key in data.__dict__:
            #print data.__dict__[key]
            type_data = type(data.__dict__[key]).__name__
            if type_data == "int" or type_data == "float":
                data_out += '"' + key + '" : ' + str(data.__dict__[key]) + ','
            elif type_data == "unicode":
                data_out += '"' + key + '" : "' + data.__dict__[key] + '",'
            elif type_data == "Area" or type_data == "Room":
                data_out += '"' + key + '" : {'
                for key_dmg in data.__dict__[key].__dict__:
                    type_data_dmg = type(data.__dict__[key].__dict__[key_dmg]).__name__
                    if type_data_dmg == "int" or type_data_dmg == "float":
                        data_out += '"' + key_dmg + '" : ' + str(data.__dict__[key].__dict__[key_dmg]) + ','
                    elif type_data_dmg == "unicode":
                        data_out += '"' + key_dmg + '" : "' + data.__dict__[key].__dict__[key_dmg] + '",'
                data_out = data_out[0:len(data_out)-1] + '},'
        self._data_values += data_out[0:len(data_out)-1] + '},'
            

        

    def get(self):
        if self._jsonp is True and self._jsonp_cb != "":
            json = "%s (" % self._jsonp_cb
        else:
            json = ""

        if self._data_type != "":
            json += '{' + self._status + '"' + self._data_type + '" : [' + \
                   self._data_values[0:len(self._data_values)-1] + ']' + '}'
        else:
            json += '{' + self._status[0:len(self._status)-1] + '}'

        if self._jsonp is True and self._jsonp_cb != "":
            json += ")"
        print json
        return json
        
    



def main():
    try:
        port = 8080
        server = HTTPServer(('', port), RestHandler)
        print 'Start REST server on port %s...' % port
        server.serve_forever()
    except KeyboardInterrupt:
        print '^C received, shutting down server'
        server.socket.close()

if __name__ == '__main__':
    #main()
    serv = Rest("127.0.0.1", "8080")
    #serv = Rest("192.168.0.10", "80")



