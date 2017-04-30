import threading
import asyncio
import serial_asyncio
import logging
import functools
import sys
import re
import traceback

async_main_loop= None

class SerialConnection(asyncio.Protocol):
    def __init__(self, cb):
        super().__init__()
        self.cb = cb
        self.cnt= 0
        self.log = logging.getLogger() #.getChild('SerialConnection')
        self.log.info('SerialConnection: creating SerialCOnnection')
        self.queue = asyncio.Queue(maxsize=100)
        self.hipri_queue = asyncio.Queue()
        self._ready = asyncio.Event()
        self._msg_ready = asyncio.Semaphore(value=0)
        self.tsk= asyncio.async(self._send_messages())  # Or asyncio.ensure_future if using 3.4.3+

    @asyncio.coroutine
    def _send_messages(self):
        ''' Send messages to the board as they become available. '''
        # checks high priority queue first
        yield from self._ready.wait()
        self.log.debug("SerialConnection: send_messages Ready!")
        while True:
            # every message added to one of the queues increments the semaphore
            yield from self._msg_ready.acquire()

            # see which queue, try hipri queue first
            if not self.hipri_queue.empty():
                data = self.hipri_queue.get_nowait()
                self.transport.write(data.encode('utf-8'))
                self.log.debug('hipri message sent: {!r}'.format(data))

            elif not self.queue.empty():
                # see if anything on normal queue and send it
                data = self.queue.get_nowait()
                self.transport.write(data.encode('utf-8'))
                self.log.debug('normal message sent: {!r}'.format(data))

    def connection_made(self, transport):
        self.transport = transport
        self.log.debug('SerialConnection: port opened: ' + str(transport))
        transport.serial.rts = False  # You can manipulate Serial object via transport
        self._ready.set()
        self.cb.connected(True)

    @asyncio.coroutine
    def send_message(self, data, hipri=False):
        """ Feed a message to the sender coroutine. """
        self.log.debug('SerialConnection: send_message - hipri: ' + str(hipri))
        self._msg_ready.release()
        if hipri:
            yield from self.hipri_queue.put(data)
        else:
            yield from self.queue.put(data)

    def data_received(self, data):
        #print('data received', repr(data))
        try:
            # FIXME this is a problem when it splits utf-8, may need to get whole lines here anyway
            self.cb.incoming_data(data.decode('utf-8'))

        except Exception as err:
            self.log.error("SerialConnection: Got decode error on data {}: {}".format(repr(data), err))
            self.cb.incoming_data(repr(data)) # send it upstream anyway


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
        self.okcnt= 0
        self.timer= None
        self._fragment= None

        #logging.getLogger('asyncio').setLevel(logging.DEBUG)
        self.log = logging.getLogger() #.getChild('Comms')
        #logging.getLogger().setLevel(logging.DEBUG)

    def connect(self, port):
        ''' called from UI to connect to given port, runs the asyncio mainloop in a separate thread '''
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

    def write(self, data):
        ''' Write to serial port, called from UI thread '''
        if self.proto and async_main_loop:
            #self.log.debug('Comms: writing ' + data)
            async_main_loop.call_soon_threadsafe(self._write, data)
            #asyncio.run_coroutine_threadsafe(self.proto.send_message, async_main_loop)
        else:
            self.log.warning('Comms: Cannot write to closed connection: ' + data)

    def _write(self, data):
        # calls the send_message in Serial Connection proto which is a queue
        #self.log.debug('Comms: _write ' + data)
        if self.proto:
           asyncio.async(self.proto.send_message(data))

    def _get_reports(self):
        # calls the send_message in Serial Connection proto which is a queue
        if self.proto:
           asyncio.async(self.proto.send_message('M105\n', True))
           asyncio.async(self.proto.send_message('?', True))
           self.timer = async_main_loop.call_later(5, self._get_reports)

    def stop(self):
        ''' called by ui thread when it is exiting '''
        if self.proto:
            async_main_loop.call_soon_threadsafe(self.proto.transport.close)
        else:
            if async_main_loop:
                if self.timer:
                    self.timer.cancel()
                async_main_loop.call_soon_threadsafe(async_main_loop.stop)


    def run_async_loop(self):
        ''' called by connect in a new thread to setup and start the asyncio loop '''
        global async_main_loop

        if async_main_loop:
            self.log.error("Comms: Already running cannot connect again")
            return

        newloop = asyncio.new_event_loop()
        asyncio.set_event_loop(newloop)
        loop = asyncio.get_event_loop()
        async_main_loop = loop
        sc_factory = functools.partial(SerialConnection, cb=self) # uses partial so we can pass a parameter
        serial_conn = serial_asyncio.create_serial_connection(loop, sc_factory, self.port, baudrate=115200)
        try:
            _, self.proto = loop.run_until_complete(serial_conn) # sets up connection returning transport and protocol handler
            self._write('version\n') # issue a version command to get things started
            self.timer = loop.call_later(5, self._get_reports)
            loop.run_forever()
        except Exception as err:
            self.log.error("Comms: Got serial error opening port: {0}".format(err))
            self.app.root.async_display(">>> Connect failed: {0}".format(err))

        finally:
            if self.timer:
                self.timer.cancel()
            loop.close()
            async_main_loop= None
            self.log.debug('Comms: asyncio thread Exiting...')

    # Handle incoming data, see if it is a report and parse it otherwise just display it on the console log
    # Note the data could be a line fragment and we need to only process complete lines terminated with \n
    tempreading_exp = re.compile("(^T:| T:)")
    def incoming_data(self, data):
        ''' called by Serial connection when incoming data is received '''
        l= data.splitlines(1)

        for s in l:
            if self._fragment:
                # handle line fragment
                s= ''.join( (self._fragment, s) )
                self._fragment= None

            if not s.endswith('\n'):
                # this is the last line and is a fragment
                self._fragment= s
                break

            # process a complete line
            s= s.rstrip() # strip off \n

            if s in 'ok':
                self.okcnt += 1

            elif "ok C:" in s:
                self.handle_position(s)

            elif "ok T:" in s or self.tempreading_exp.findall(s):
                self.handle_temperature(s)

            elif s.startswith('<'):
                self.handle_status(s)

            else:
                self.app.root.async_display('{}'.format(s))

    # Handle parsing of temp readings (Lifted mostly from Pronterface)
    tempreport_exp = re.compile("([TB]\d*):([-+]?\d*\.?\d*)(?: ?\/)?([-+]?\d*\.?\d*)")
    def parse_temperature(self, s):
        matches = self.tempreport_exp.findall(s)
        return dict((m[0], (m[1], m[2])) for m in matches)

    def handle_temperature(self, s):
        # ok T:19.8 /0.0 @0 B:20.1 /0.0 @0
        hotend_setpoint= None
        bed_setpoint= None
        hotend_temp= None
        bed_temp= None

        try:
            temps = self.parse_temperature(s)
            if "T" in temps and temps["T"][0]:
                hotend_temp = float(temps["T"][0])

            if "T" in temps and temps["T"][1]:
                hotend_setpoint = float(temps["T"][1])

            bed_temp = float(temps["B"][0]) if "B" in temps and temps["B"][0] else None
            if "B" in temps and temps["B"][1]:
                bed_setpoint = float(temps["B"][1])

            self.log.debug('Comms: got temps hotend:{}, bed:{}, hotend_setpoint:{}, bed_setpoint:{}'.format(hotend_temp, bed_temp, hotend_setpoint, bed_setpoint))
            self.app.root.update_temps(hotend_temp, hotend_setpoint, bed_temp, bed_setpoint)

        except:
            self.log.error(traceback.format_exc())

    def handle_position(self, s):
        # ok C: X:0.0000 Y:0.0000 Z:0.0000
        l= s.split(' ')
        if len(l) >= 5:
            x= float(l[2][2:])
            y= float(l[3][2:])
            z= float(l[4][2:])
            self.log.debug('Comms: got pos: X {}, Y {} Z {}'.format(x, y, z))
            #self.app.root.update_position(x, y, z)

    def handle_status(self, s):
        #<Idle,MPos:68.9980,-49.9240,40.0000,WPos:68.9980,-49.9240,40.0000>
        sl= s.split(',')
        if len(sl) >= 7:
            # strip off status
            status= sl[0]
            status= status[1:]
            # strip off mpos
            mpos= (float(sl[1][5:]), float(sl[2]), float(sl[3]))
            # strip off wpos
            wpos= (float(sl[4][5:]), float(sl[5]), float(sl[6][:-1]))
            self.log.debug('Comms: got status:{}, mpos:{},{},{}, wpos:{},{},{}'.format(status, mpos[0], mpos[1], mpos[2], wpos[0], wpos[1], wpos[2]))
            #self.app.root.update_status(status, mpos, wpos)
