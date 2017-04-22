import threading
import asyncio
import serial_asyncio

async_main_loop= None

class SerialConnection(asyncio.Protocol):
    def __init__(self, cb):
        self.cb = cb
        self.data_buffer = ''
        self.cnt= 0

    def connection_made(self, transport):
        self.transport = transport
        print('port opened', transport)
        transport.serial.rts = False  # You can manipulate Serial object via transport
        transport.write(b'version\n')  # Write serial data via transport
        self.cb.connected(True, transport)

    def data_received(self, data):
        #print('data received', repr(data))
        self.data_buffer += data.decode('utf-8')
        if '\n' in self.data_buffer:
            print('data buffer: ' + self.data_buffer)
            self.cb.incoming_data(self.data_buffer)
            # Reset the data_buffer!
            self.data_buffer = ''

    def connection_lost(self, exc):
        print('port closed')
        # self.transport.loop.stop()
        self.cb.connected(False)
        async_main_loop.stop()

    def pause_writing(self):
        print('pause writing')
        print(self.transport.get_write_buffer_size())

    def resume_writing(self):
        print(self.transport.get_write_buffer_size())
        print('resume writing')

class Comms():
    def __init__(self, app):
        self.app = app
        self.transport = None

    def connect(self, port):
        self.port= port
        threading.Thread(target=self.run_async_loop).start()

    def connected(self, b, transport=None):
        if b:
            self.transport= transport
            self.app.root.connected()
        else:
            self.transport= None
            self.app.root.disconnected()

    def disconnect(self):
        if self.transport:
            async_main_loop.call_soon_threadsafe(self.transport.close)

    def incoming_data(self, data):
        self.app.root.display(data)

    def write(self, data):
        if self.transport:
            print('writing ' + data)
            async_main_loop.call_soon_threadsafe(self.transport.write, data.encode('utf-8'))

    def stop(self):
        if self.transport:
            async_main_loop.call_soon_threadsafe(self.transport.close)
        else:
            if async_main_loop:
                async_main_loop.call_soon_threadsafe(async_main_loop.stop)

    def run_async_loop(self):
        global async_main_loop
        newloop = asyncio.new_event_loop()
        asyncio.set_event_loop(newloop)
        loop = asyncio.get_event_loop()
        async_main_loop = loop
        serial_conn = serial_asyncio.create_serial_connection(loop, lambda: SerialConnection(self), self.port, baudrate=115200)
        try:
            loop.run_until_complete(serial_conn)
            loop.run_forever()
        except:
            print("Got serial error opening port")
            self.app.root.error_message("Connect failed")

        finally:
            loop.close()
            async_main_loop= None
            print('asyncio thread Exiting...')

