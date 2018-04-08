import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import logging
from kivy.logger import Logger
import traceback
import threading

def make_request_handler_class(app):
    class MyRequestHandler(BaseHTTPRequestHandler):
        m_app= app

        def _set_headers(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

        def do_GET(self):
            self._set_headers()
            # TODO query comms for linecnt and say if printing or not and what the progress is
            status= MyRequestHandler.m_app.status
            if MyRequestHandler.m_app.main_window.is_printing:
                eta= MyRequestHandler.m_app.main_window.eta
                self.wfile.write("{} - ETA: {}".format(status, eta).encode("utf-8"))
            else:
                self.wfile.write("{} - Not Printing".format(status).encode("utf-8"))


        def do_POST(self):
            # Doesn't do anything with posted data
            self._set_headers()
            self.wfile.write("not handled".encode("utf-8"))

    return MyRequestHandler

class ProgressServer(object):
    def start(self, app, port):
        self.port= port
        self.app= app
        t= threading.Thread(target=self._start)
        t.start()

    def _start(self):
        RequestHandlerClass = make_request_handler_class(self.app)
        self.myServer = HTTPServer(("", self.port), RequestHandlerClass)
        Logger.info("ProgressServer: Web Server Starting - %s:%s" % ("", self.port))

        try:
    	    self.myServer.serve_forever()
        except:
            Logger.warn('ProgressServer: Exception: {}'.format(traceback.format_exc()))
        finally:
            self.myServer.server_close()
            Logger.info("ProgressServer: Web Server Stopping - %s:%s" % ("", self.port))
            self.myServer= None

    def stop(self):
        if self.myServer:
            self.myServer.shutdown()

if __name__ == "__main__":

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    s= ProgressServer()
    s.start(8000)

