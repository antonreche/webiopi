#   Copyright 2012-2013 Eric Ptak - trouch.com
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os
import threading
import re
import codecs
import mimetypes as mime
import logging

from webiopi.utils import *

if PYTHON_MAJOR >= 3:
    import http.server as BaseHTTPServer
else:
    import BaseHTTPServer

try :
    import _webiopi.GPIO as GPIO
except:
    pass

WEBIOPI_DOCROOT = "/usr/share/webiopi/htdocs"

class HTTPServer(BaseHTTPServer.HTTPServer, threading.Thread):
    def __init__(self, host, port, handler, context, docroot, index, auth=None):
        BaseHTTPServer.HTTPServer.__init__(self, ("", port), HTTPHandler)
        threading.Thread.__init__(self, name="HTTPThread")
        self.host = host
        self.port = port

        if context:
            self.context = context
            if not self.context.startswith("/"):
                self.context = "/" + self.context
            if not self.context.endswith("/"):
                self.context += "/"
        else:
            self.context = "/"

        if docroot:
            self.docroot = docroot
        else:
            self.docroot = "."

        if index:
            self.index = index
        else:
            self.index = "index.html"
            
        self.handler = handler
        self.auth = auth

        self.running = True
        self.start()
            
    def run(self):
        info("HTTP Server binded on http://%s:%s%s" % (self.host, self.port, self.context))
        try:
            self.serve_forever()
        except Exception as e:
            if self.running == True:
                exception(e)
        info("HTTP Server stopped")

    def stop(self):
        self.running = False
        self.server_close()

class HTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    logger = logging.getLogger("HTTP")

    def log_message(self, format, *args):
        self.logger.debug(format % args)
    
    def log_error(self, format, *args):
        pass
        
    def version_string(self):
        return VERSION_STRING
    
    def checkAuthentication(self):
        if self.server.auth == None or len(self.server.auth) == 0:
            return True
        
        authHeader = self.headers.get('Authorization')
        if authHeader == None:
            return False
        
        if not authHeader.startswith("Basic "):
            return False
        
        auth = authHeader.replace("Basic ", "")
        if PYTHON_MAJOR >= 3:
            hash = hashlib.sha256(auth.encode()).hexdigest()
        else:
            hash = hashlib.sha256(auth).hexdigest()
            
        if hash == self.server.auth:
            return True
        return False

    def requestAuthentication(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="webiopi"')
        self.end_headers();
    
    def sendResponse(self, code, body=None, type="text/plain"):
        if code >= 400:
            if body != None:
                self.send_error(code, body)
            else:
                self.send_error(code)
        else:
            self.send_response(code)
            self.send_header("Cache-Control", "no-cache")
            if body != None:
                self.send_header("Content-Type", type);
                self.end_headers();
                self.wfile.write(body.encode())
            
    def serveFile(self, relativePath):
        if relativePath == "":
            relativePath = self.server.index

        path = self.server.docroot + os.sep + relativePath

        if not os.path.exists(path):
            path = relativePath;
            
        if not os.path.exists(path):
            path = WEBIOPI_DOCROOT + os.sep + relativePath;
            
        if not os.path.exists(path):
            return self.sendResponse(404, "Not Found")

        realPath = os.path.realpath(path)
        
        if realPath.endswith(".py"):
            return self.sendResponse(403, "Not Authorized")
        
        if not (realPath.startswith(self.server.docroot) 
                or realPath.startswith(os.getcwd())
                or realPath.startswith(WEBIOPI_DOCROOT)):
            return self.sendResponse(403, "Not Authorized")
        
        if os.path.isdir(realPath):
            realPath += os.sep + self.server.index;
            if not os.path.exists(realPath):
                return self.sendResponse(403, "Not Authorized")
            
        (type, encoding) = mime.guess_type(realPath)
        f = codecs.open(realPath, encoding=encoding)
        data = f.read()
        f.close()
        self.send_response(200)
        self.send_header("Content-Type", type);
#            self.send_header("Content-length", os.path.getsize(realPath))
        self.end_headers()
        self.wfile.write(data)
        
    def processRequest(self):
        if not self.checkAuthentication():
            return self.requestAuthentication()
        
        request = self.path.replace(self.server.context, "/").split('?')
        relativePath = request[0]
        if relativePath[0] == "/":
            relativePath = relativePath[1:]
            
        if relativePath == "webiopi" or relativePath == "webiopi/":
            self.send_response(301)
            self.send_header("Location", "/")
            self.end_headers()
            return

        params = {}
        if len(request) > 1:
            for s in request[1].split('&'):
                if s.find('=') > 0:
                    (name, value) = s.split('=')
                    params[name] = value
                else:
                    params[s] = None
        
        compact = False
        if 'compact' in params:
            compact = str2bool(params['compact'])

        try:
            result = (None, None, None)
            if self.command == "GET":
                result = self.server.handler.do_GET(relativePath, compact)
            elif self.command == "POST":
                length = 0
                length_header = 'content-length'
                if length_header in self.headers:
                    length = int(self.headers[length_header])
                result = self.server.handler.do_POST(relativePath, self.rfile.read(length), compact)
            else:
                result = (405, None, None)
                
            (code, body, type) = result
            
            if code > 0:
                self.sendResponse(code, body, type)
            else:
                if self.command == "GET":
                    self.serveFile(relativePath)
                else:
                    self.sendResponse(404)

        except (GPIO.InvalidDirectionException, GPIO.InvalidChannelException, GPIO.SetupException) as e:
            self.sendResponse(403, "%s" % e)
        except ValueError as e:
            self.sendResponse(403, "%s" % e)
        except Exception as e:
            self.sendResponse(500)
            raise e
            
    def do_GET(self):
        self.processRequest()

    def do_POST(self):
        self.processRequest()