import threading
import asyncio
import serial_asyncio
import logging
import functools
import sys

async_main_loop= None

class SerialConnection(asyncio.Protocol):
    def __init__(self, cb):
        super().__init__()
        self.cb = cb
        self.data_buffer = ''
        self.cnt= 0
        self.log = logging.getLogger() #.getChild('SerialConnection')
        self.log.info('SerialConnection: creating SerialCOnnection')
        self.queue = asyncio.Queue()
        self._ready = asyncio.Event()
        self.tsk= asyncio.async(self._send_messages())  # Or asyncio.ensure_future if using 3.4.3+

    @asyncio.coroutine
    def _send_messages(self):
        """ Send messages to the server as they become available. """
        yield from self._ready.wait()
        self.log.debug("SerialConnection: send_messages Ready!")
        while True:
            data = yield from self.queue.get()
            self.transport.write(data.encode('utf-8'))
            self.log.debug('Message sent: {!r}'.format(data))

    def connection_made(self, transport):
        self.transport = transport
        self.log.debug('SerialConnection: port opened: ' + str(transport))
        transport.serial.rts = False  # You can manipulate Serial object via transport
        self._ready.set()
        self.cb.connected(True)

    @asyncio.coroutine
    def send_message(self, data):
        """ Feed a message to the sender coroutine. """
        self.log.debug('SerialConnection: send_message')
        yield from self.queue.put(data)

    def data_received(self, data):
        #print('data received', repr(data))
        self.data_buffer += data.decode('utf-8')
        if '\n' in self.data_buffer:
            self.log.debug('SerialConnection: data buffer: ' + self.data_buffer)
            self.cb.incoming_data(self.data_buffer)
            # Reset the data_buffer!
            self.data_buffer = ''

    def connection_lost(self, exc):
        self.log.debug('SerialConnection: port closed')
        self.tsk.cancel() # stop the writer task
        self.cb.connected(False)
        # self.transport.loop.stop()
        async_main_loop.stop()

    def pause_writing(self):
        self.log.debug('SerialConnection: pause writing')
        self.log.debug('SerialConnection: ' + self.transport.get_write_buffer_size())

    def resume_writing(self):
        self.log.debug(self.transport.get_write_buffer_size())
        self.log.debug('SerialConnection: ' + 'resume writing')

class Comms():
    def __init__(self, app):
        self.app = app
        self.proto = None
        #logging.getLogger('asyncio').setLevel(logging.DEBUG)
        self.log = logging.getLogger() #.getChild('Comms')
        #logging.getLogger().setLevel(logging.DEBUG)

    def connect(self, port):
        ''' called from UI to connect to given port, runs the asyncio mainlopp in a separate thread '''
        self.port= port
        self.log.info('Comms: creating comms thread')
        threading.Thread(target=self.run_async_loop).start()

    def connected(self, b):
        ''' called by the serial connection to indicate when connectde and disconnected '''
        if b:
            self.app.root.connected()
        else:
            self.proto= None
            self.app.root.disconnected()

    def disconnect(self):
        ''' called by ui thread to disconnect '''
        if self.proto:
            async_main_loop.call_soon_threadsafe(self.proto.transport.close)

    def incoming_data(self, data):
        ''' called by Srial connection when incomign data is recieved '''
        self.app.root.display(data)

    def write(self, data):
        ''' Write to serial port, called from UI thread '''
        if self.proto and async_main_loop:
            self.log.debug('Comms: writing ' + data)
            async_main_loop.call_soon_threadsafe(self._write, data)
            #asyncio.run_coroutine_threadsafe(self.proto.send_message, async_main_loop)

    def _write(self, data):
        # calls the send_message in Serial Connection proto which is a queue
        #self.log.debug('Comms: _write ' + data)
        if self.proto:
           asyncio.async(self.proto.send_message(data))

    def stop(self):
        ''' called by ui thread when it is exiting '''
        if self.proto:
            async_main_loop.call_soon_threadsafe(self.proto.transport.close)
        else:
            if async_main_loop:
                async_main_loop.call_soon_threadsafe(async_main_loop.stop)

    def run_async_loop(self):
        ''' called by connect in a new thread to setup and start the asyncio loop '''
        global async_main_loop

        newloop = asyncio.new_event_loop()
        asyncio.set_event_loop(newloop)
        loop = asyncio.get_event_loop()
        async_main_loop = loop
        sc_factory = functools.partial(SerialConnection, cb=self) # uses partial so we can pass a parameter
        serial_conn = serial_asyncio.create_serial_connection(loop, sc_factory, self.port, baudrate=115200)
        try:
            _, self.proto = loop.run_until_complete(serial_conn) # sets up connection returning transport and protocol handler
            self._write('version\n') # issue a version command to get things started
            loop.run_forever()
        except Exception as err:
            self.log.error("Comms: Got serial error opening port: {0}".format(err))
            self.app.root.error_message("Connect failed: {0}".format(err))

        finally:
            loop.close()
            async_main_loop= None
            self.log.debug('Comms: asyncio thread Exiting...')

