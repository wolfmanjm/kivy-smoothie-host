import threading
import asyncio
import serial_asyncio
import aiofiles
import logging
import functools
import sys
import re
import traceback
import serial.tools.list_ports
import subprocess

async_main_loop= None

class SerialConnection(asyncio.Protocol):
    def __init__(self, cb, f):
        super().__init__()
        self.cb = cb
        self.f= f
        self.cnt= 0
        self.log = logging.getLogger() #.getChild('SerialConnection')
        self.log.info('SerialConnection: creating SerialCOnnection')
        self.queue = asyncio.Queue(maxsize=100)
        self.hipri_queue = asyncio.Queue()
        self._ready = asyncio.Event()
        self._msg_ready = asyncio.Semaphore(value=0)
        self.tsk= asyncio.async(self._send_messages())  # Or asyncio.ensure_future if using 3.4.3+
        self.flush= False

    @asyncio.coroutine
    def _send_messages(self):
        ''' Send messages to the board as they become available. '''
        # checks high priority queue first
        yield from self._ready.wait()
        self.log.debug("SerialConnection: send_messages Ready!")
        while True:
            # every message added to one of the queues increments the semaphore
            yield from self._msg_ready.acquire()

            if self.flush:
                while not self.hipri_queue.empty():
                    self.hipri_queue.get_nowait()
                while not self.queue.empty():
                    self.queue.get_nowait()
                self.flush= False
                continue

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
        #transport.serial.rts = False  # You can manipulate Serial object via transport
        self._ready.set()

    def flush_queue(self):
        self.flush= True
        self._msg_ready.release()

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
        self.transport.close()
        self.f.set_result('Disconnected')

    def pause_writing(self):
        self.log.debug('SerialConnection: pause writing')
        self.log.debug('SerialConnection: ' + self.transport.get_write_buffer_size())

    def resume_writing(self):
        self.log.debug(self.transport.get_write_buffer_size())
        self.log.debug('SerialConnection: ' + 'resume writing')

class Comms():
    def __init__(self, app, reports=True):
        self.app = app
        self.proto = None
        self.timer= None
        self._fragment= None
        self.reports= reports
        self.abort_stream= False
        self.pause_stream= False #asyncio.Event()
        self.okcnt= None
        self.ping_pong= True # ping pong protocol for streaming
        self.file_streamer= None
        self.report_rate= 1 # TODO make configurable

        self.log = logging.getLogger() #.getChild('Comms')
        #logging.getLogger().setLevel(logging.DEBUG)

    def connect(self, port):
        ''' called from UI to connect to given port, runs the asyncio mainloop in a separate thread '''
        self.port= port
        self.log.info('Comms: creating comms thread')
        t= threading.Thread(target=self.run_async_loop)
        t.start()
        return t

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
           self.timer = async_main_loop.call_later(self.report_rate, self._get_reports)

    def stop(self):
        ''' called by ui thread when it is exiting '''
        if self.proto:
            # abort any streaming immediately
            self._stream_pause(False, True)
            if self.file_streamer:
                self.file_streamer.cancel()

            # we need to close the transport, this will cause mailopp to stop and thread to exit as well
            async_main_loop.call_soon_threadsafe(self.proto.transport.close)

        # else:
        #     if async_main_loop and async_main_loop.is_running():
        #         async_main_loop.call_soon_threadsafe(async_main_loop.stop)

    def get_ports(self):
        return [port for port in serial.tools.list_ports.comports() if port[2] != 'n/a']

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
        f = asyncio.Future()
        sc_factory = functools.partial(SerialConnection, cb=self, f= f) # uses partial so we can pass a parameter
        serial_conn = serial_asyncio.create_serial_connection(loop, sc_factory, self.port, baudrate=115200)
        try:
            _, self.proto = loop.run_until_complete(serial_conn) # sets up connection returning transport and protocol handler
            self.log.debug('Comms: serial connection task completed')

            # this is when we are really setup and ready to go, notify upstream
            self.app.root.connected()

            if self.reports:
                # issue a version command to get things started
                self._write('version\n')
                # start a timer to get the reports
                self.timer = loop.call_later(self.report_rate, self._get_reports)

            # wait until we are disconnected
            self.log.debug('Comms: waiting until disconnection')
            loop.run_until_complete(f)

            # clean up and notify upstream we have been disconnected
            self.proto= None # no proto now
            self._stream_pause(False, True) # abort the stream if one is running
            if self.timer: # stop the timer if we have one
                self.timer.cancel()
                self.timer= None

            self.app.root.disconnected() # tell upstream we disconnected

            # we wait until all tasks are complete
            pending = asyncio.Task.all_tasks()
            self.log.debug('Comms: waiting for all tasks to complete: {}'.format(pending))
            loop.run_until_complete(asyncio.gather(*pending))
            #loop.run_forever()

        except asyncio.CancelledError:
            pass

        except Exception as err:
            #self.log.error('Comms: {}'.format(traceback.format_exc()))
            self.log.error("Comms: Got serial error opening port: {0}".format(err))
            self.app.root.async_display(">>> Connect failed: {0}".format(err))
            self.app.root.disconnected()

        finally:
            loop.close()
            async_main_loop= None
            self.log.debug('Comms: asyncio thread Exiting...')

    # Handle incoming data, see if it is a report and parse it otherwise just display it on the console log
    # Note the data could be a line fragment and we need to only process complete lines terminated with \n
    tempreading_exp = re.compile("(^T:| T:)")
    def incoming_data(self, data):
        ''' called by Serial connection when incoming data is received '''
        l= data.splitlines(1)
        self.log.debug('Comms: incoming_data: {}'.format(l))

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
                if self.ping_pong:
                    if self.okcnt:
                        self.okcnt.release()
                else:
                    self.okcnt += 1

            elif "error" in s or "!!" in s or "ALARM" in s or "ERROR" in s:
                self.handle_alarm(s)

            elif "ok C:" in s:
                self.handle_position(s)

            elif "ok T:" in s or self.tempreading_exp.findall(s):
                self.handle_temperature(s)

            elif s.startswith('<'):
                self.handle_status(s)

            elif s.startswith('//'):
                # ignore comments but display them
                # TODO handle // action:pause etc
                pos= s.find('action:')
                if pos >= 0:
                    act= s[pos+7:].strip() # extract action command
                    if act in 'pause':
                        self.app.root.async_display('>>> Smoothie requested Pause')
                        self._stream_pause(True, False)
                    elif act in 'resume':
                        self.app.root.async_display('>>> Smoothie requested Resume')
                        self._stream_pause(False, False)
                    elif act in 'disconnect':
                        self.app.root.async_display('>>> Smoothie requested Disconnect')
                        self.disconnect()
                    else:
                        self.log.warning('Comms: unknown action command: {}'.format(act))

                else:
                    self.app.root.async_display('{}'.format(s))

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
            self.app.root.update_status(status, mpos, wpos)

    def handle_alarm(self, s):
        ''' handle case where smoothie sends us !! or an error of some sort '''
        self.log.warning('Comms: got error: {}'.format(s))
        # abort any streaming immediately
        self._stream_pause(False, True)
        if self.proto:
            self.proto.flush_queue()

        # call upstream after we have allowed stream to stop
        async_main_loop.call_soon(self.app.root.alarm_state, s)

    def stream_gcode(self, fn, progress=None):
        ''' called from external thread to start streaming a file '''
        self.progress= progress
        if self.proto and async_main_loop:
            async_main_loop.call_soon_threadsafe(self._stream_file, fn)
        else:
            self.log.warning('Comms: Cannot print to a closed connection')

    def _stream_file(self, fn):
        self.file_streamer= asyncio.async(self.stream_file(fn))

    def stream_pause(self, pause, do_abort= False):
        ''' called from external thread to pause or kill in process streaming '''
        async_main_loop.call_soon_threadsafe(self._stream_pause, pause, do_abort)

    def _stream_pause(self, pause, do_abort):
        if do_abort:
            self.abort_stream= True # aborts stream
            if self.ping_pong and self.okcnt:
                self.okcnt.release() # release it in case it is waiting for ok so it can abort
        elif pause:
            self.pause_stream= True #.clear() # pauses stream
        else:
            self.pause_stream= False #.set() # releases pause on stream

    @asyncio.coroutine
    def stream_file(self, fn):

        self.log.info('Comms: Streaming file {} to port'.format(fn))

        self.abort_stream= False
        self.pause_stream= False #.set() # start out not paused
        if self.ping_pong:
            self.okcnt= asyncio.Semaphore(1)
        else:
            self.okcnt= 0

        f= None
        success= False
        linecnt= 0
        try:
            f = yield from aiofiles.open(fn, mode='r')
            while True:
                #yield from self.pause_stream.wait() # wait for pause to be released
                # needed to do it this way as the Event did nto seem to work it would pause but not unpause
                while self.pause_stream:
                   yield from asyncio.sleep(1)

                line = yield from f.readline()

                if not line:
                    # EOF
                    break

                l= line.strip()
                if l.startswith(';') or len(l) == 0:
                    continue

                if self.abort_stream:
                    break

                # wait for ok... (Note we interleave read from file with wait for ok)
                if self.ping_pong and self.okcnt:
                    try:
                        yield from self.okcnt.acquire()
                    except:
                        self.log.debug('Comms: okcntr wait cancelled')
                        break

                if self.abort_stream:
                    break

                # send the line
                self._write(line)
                linecnt += 1
                if self.progress:
                    if self.ping_pong:
                        # number of lines sent
                        self.progress(linecnt)
                    else:
                        # number of lines ok'd
                        self.progress(self.okcnt)

            success= not self.abort_stream

        except Exception as err:
                self.log.error("Comms: Stream file exception: {}".format(err))

        finally:
            self.log.info('Comms: Streaming complete: {}'.format(success))
            if f:
                yield from f.close()

            if success and not self.ping_pong:
                self.log.debug('Comms: Waiting for okcnt to catch up: {} vs {}'.format(self.okcnt, linecnt))
                # we have to wait for all lines to be ack'd
                while self.okcnt < linecnt:
                    if self.progress:
                        self.progress(self.okcnt)
                    if self.abort_stream:
                        success= False
                        break

                    yield from asyncio.sleep(1)

            self.file_streamer= None
            self.progress= None

            # notify upstream that we are done
            self.app.root.stream_finished(success)

        return success

    @staticmethod
    def file_len(fname):
        ''' use external process to quickly find total number of G/M lines in file '''
        p = subprocess.Popen(['grep', '-c', "^[GM]", fname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, err = p.communicate()
        if p.returncode != 0:
            raise IOError(err)
        return int(result.strip().split()[0])

if __name__ == "__main__":
    import datetime

    ''' a standalone streamer to test it with '''
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

    class CommsApp(object):
        """ Standalone app callbacks """
        def __init__(self):
            super(CommsApp, self).__init__()
            self.root= self
            self.log = logging.getLogger()
            self.start_event= threading.Event()
            self.end_event= threading.Event()
            self.is_connected= False
            self.ok= False

        def connected(self):
            self.log.debug("CommsApp: Connected...")
            self.is_connected= True
            self.start_event.set()

        def disconnected(self):
            self.log.debug("CommsApp: Disconnected...")
            self.is_connected= False
            self.start_event.set()

        def async_display(self, data):
            print(data)

        def stream_finished(self, ok):
            self.log.debug('CommsApp: stream finished: {}'.format(ok))
            self.ok= ok
            self.end_event.set()

        def alarm_state(self, s):
            self.ok= False
            # in this case we do want to disconnect
            comms.proto.transport.close()

    if len(sys.argv) < 3:
        print("Usage: {} port file".format(sys.argv[0]));
        exit(0)

    app= CommsApp()
    comms= Comms(app, False) # Don't start the report query timer when streaming
    if len(sys.argv) > 3:
        comms.ping_pong= False
        print('Fast Stream')


    try:
        nlines= Comms.file_len(sys.argv[2]) # get number of lines so we can do progress and ETA
        print('number of lines: {}'.format(nlines))
    except:
        print('Exception: {}'.format(traceback.format_exc()))
        nlines= None

    start= None
    def display_progress(n):
        global start, nlines
        if not start:
            start= datetime.datetime.now()
            print("Print started at: {}".format(start.strftime('%x %X')))

        if nlines:
            now=datetime.datetime.now()
            d= (now-start).seconds
            if n > 10 and d > 10:
                # we have to wait a bit to get reasonable estimates
                lps= n/d
                eta= (nlines-n)/lps
            else:
                eta= 0
            et= datetime.timedelta(seconds=int(eta))
            print("progress: {}/{} {:.1%} ETA {}".format(n, nlines, n/nlines, et))

    try:
        t= comms.connect(sys.argv[1])
        if app.start_event.wait(5): # wait for connected as it is in a separate thread
            if app.is_connected:
                comms.stream_gcode(sys.argv[2], progress=lambda x: display_progress(x))
                app.end_event.wait() # wait for streaming to complete

                print("File sent: {}".format('Ok' if app.ok else 'Failed'))
                now=datetime.datetime.now()
                print("Print ended at : {}".format(now.strftime('%x %X')))
                et= datetime.timedelta(seconds= int((now-start).seconds))
                print("Elapsed time: {}".format(et))

            else:
                print("Error: Failed to connect")

        else:
            print("Error: Connection timed out")

    except KeyboardInterrupt:
        print("Interrupted")

    finally:
        # now stop the comms if it is connected or running
        comms.stop()
        t.join()
