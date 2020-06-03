import threading
import asyncio
import aiofiles
import logging
import functools
import sys
import re
import os
import traceback
import serial.tools.list_ports
import subprocess
import socket
import time
from notify import Notify

# my version
import libs.serial_asyncio.serial_asyncio

async_main_loop = None


class SerialConnection(asyncio.Protocol):
    def __init__(self, cb, f, is_net=False):
        super().__init__()
        self.log = logging.getLogger()  # getChild('SerialConnection')
        self.log.debug('SerialConnection: creating SerialConnection')
        self.cb = cb
        self.f = f
        self.cnt = 0
        self.is_net = is_net
        self._paused = False
        self._drain_waiter = None
        self._connection_lost = False
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.log.debug('SerialConnection: port opened: {}'.format(transport))
        if self.is_net:
            # we don't want to buffer the entire file on the host
            transport.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)
            self.log.info("SerialConnection: Setting net tx buf to 2048")
            # for net we want to limit how much we queue up otherwise the whole file gets queued
            # this also gives us more progress more often
            transport.set_write_buffer_limits(high=1024, low=256)
            self.log.info('SerialConnection: Buffer limits: {} - {}'.format(transport._high_water, transport._low_water))
        else:
            transport.set_write_buffer_limits(high=1024, low=64)
            self.log.info('SerialConnection: Buffer limits: {} - {}'.format(transport._high_water, transport._low_water))
            # transport.serial.rts = False  # You can manipulate Serial object via transport
            transport.serial.reset_input_buffer()
            transport.serial.reset_output_buffer()
            # transport.serial.set_low_latency_mode(True)
            # print(transport.serial)

    def flush_queue(self):
        if not self.is_net and self.transport:
            self.transport.flush()

    def send_message(self, data, hipri=False):
        """ Feed a message to the sender coroutine. """
        self.log.debug('SerialConnection: send_message: {}'.format(data.strip()))
        self.transport.write(data.encode('latin1'))
        # print(self.transport.get_write_buffer_size())

    def data_received(self, data):
        # print('data received', repr(data))
        str = ''
        try:
            str = data.decode(encoding='latin1', errors='ignore')
        except Exception as err:
            self.log.error("SerialConnection: Got decode error on data {}: {}".format(repr(data), err))
            # send it upstream anyway
            self.cb.incoming_data(repr(data), True)
            return

        self.cb.incoming_data(str)

    def connection_lost(self, exc):
        self.log.debug('SerialConnection: port closed')
        self._connection_lost = True

        # Wake up the writer if currently paused.
        if self._paused:
            waiter = self._drain_waiter
            if waiter:
                self._drain_waiter = None
                if not waiter.done():
                    if exc is None:
                        waiter.set_result(None)
                    else:
                        waiter.set_exception(exc)

        # if not self.is_net:
        #     self.transport.serial.reset_output_buffer()

        self.transport.close()
        self.f.set_result('Disconnected')

    async def _drain_helper(self):
        if self._connection_lost:
            raise ConnectionResetError('Connection lost')
        if not self._paused:
            return
        waiter = self._drain_waiter
        assert waiter is None or waiter.cancelled()
        waiter = asyncio.Future()
        self._drain_waiter = waiter
        await waiter

    def pause_writing(self):
        self.log.debug('SerialConnection: pause writing: {}'.format(self.transport.get_write_buffer_size()))
        # if not self.is_net:
        #     return
        # we only do this pause stream stuff for net
        assert not self._paused
        self._paused = True

    def resume_writing(self):
        self.log.debug('SerialConnection: resume writing: {}'.format(self.transport.get_write_buffer_size()))
        # if not self.is_net:
        #     return
        # we only do this pause stream stuff for net
        assert self._paused
        self._paused = False
        waiter = self._drain_waiter
        if waiter is not None:
            self._drain_waiter = None
            if not waiter.done():
                waiter.set_result(None)


class Comms():
    def __init__(self, app, reportrate=1):
        self.app = app
        self.proto = None
        self.timer = None
        self._fragment = None
        self.abort_stream = False
        self.pause_stream = False  # asyncio.Event()
        self.okcnt = None
        self.ping_pong = True  # ping pong protocol for streaming
        self.file_streamer = None
        self.report_rate = reportrate
        self._reroute_incoming_data_to = None
        self._restart_timer = False
        self.is_streaming = False
        self.do_query = False
        self.last_tool = None
        self.is_suspend = False
        self.m0 = None
        self.net_connection = False
        self.log = logging.getLogger()  # .getChild('Comms')
        # logging.getLogger().setLevel(logging.DEBUG)

    def connect(self, port):
        ''' called from UI to connect to given port, runs the asyncio mainloop in a separate thread '''
        self.port = port
        self.log.info('Comms: creating comms thread')
        self.comms_thread = threading.Thread(target=self.run_async_loop)
        self.comms_thread.start()
        return self.comms_thread

    def disconnect(self):
        ''' called by ui thread to disconnect '''
        if self.proto:
            async_main_loop.call_soon_threadsafe(self.proto.transport.close)

    def write(self, data):
        ''' Write to serial port, called from UI thread '''
        if self.proto and async_main_loop:
            async_main_loop.cabll_soon_threadsafe(self._write, data)
            # asyncio.run_coroutine_threadsafe(self.proto.send_message, async_main_loop)
        else:
            self.log.warning('Comms: Cannot write to closed connection: ' + data)
            # self.app.main_window.async_display("<<< {}".format(data))

    def _write(self, data):
        # calls the send_message in Serial Connection proto
        # print('Comms: _write {}'.format(data))
        if self.proto:
            self.proto.send_message(data)

    def _get_reports(self):
        if self._restart_timer:
            return

        queries = self.app.main_window.get_queries()
        if queries:
            self._write(queries)

        self._write('?')

    def stop(self):
        ''' called by ui thread when it is exiting '''
        if self.proto:
            # abort any streaming immediately
            self._stream_pause(False, True)
            if self.file_streamer:
                self.file_streamer.cancel()

            # we need to close the transport, this will cause mainloop to stop and thread to exit as well
            async_main_loop.call_soon_threadsafe(self.proto.transport.close)
            self.comms_thread.join()

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
            self.app.main_window.async_display('>>> Already running cannot connect again')
            return

        newloop = asyncio.new_event_loop()
        asyncio.set_event_loop(newloop)
        loop = asyncio.get_event_loop()
        async_main_loop = loop
        f = asyncio.Future()

        # if tcp connection port will be net://ipaddress[:port]
        # otherwise it will be serial:///dev/ttyACM0 or serial://COM2:
        if self.port.startswith('net://'):
            sc_factory = functools.partial(SerialConnection, cb=self, f=f, is_net=True)  # uses partial so we can pass a parameter
            self.net_connection = True
            ip = self.port[6:]
            ip = ip.split(':')
            if len(ip) == 1:
                self.port = 23
            else:
                self.port = ip[1]

            self.ipaddress = ip[0]
            self.log.info('Comms: Connecting to Network at {} port {}'.format(self.ipaddress, self.port))
            serial_conn = loop.create_connection(sc_factory, self.ipaddress, self.port)

        elif self.port.startswith('serial://'):
            sc_factory = functools.partial(SerialConnection, cb=self, f=f)  # uses partial so we can pass a parameter
            self.net_connection = False
            self.port = self.port[9:]
            serial_conn = libs.serial_asyncio.serial_asyncio.create_serial_connection(loop, sc_factory, self.port, baudrate=115200)

        else:
            loop.close()
            self.log.error('Comms: Not a valid connection port: {}'.format(self.port))
            self.app.main_window.async_display('>>> Connect failed: unknown connection type, use "serial://" or "net://"'.format(self.port))
            self.app.main_window.disconnected()
            loop.close()
            async_main_loop = None
            return

        try:
            transport, self.proto = loop.run_until_complete(serial_conn)  # sets up connection returning transport and protocol handler
            self.log.debug('Comms: serial connection task completed')

            # this is when we are really setup and ready to go, notify upstream
            self.app.main_window.connected()

            # issue a M115 command to get things started
            self._write('\n')
            self._write('M115\n')

            if self.report_rate > 0:
                # start a timer to get the reports
                self.timer = loop.call_later(self.report_rate, self._get_reports)

            # wait until we are disconnected
            self.log.debug('Comms: waiting until disconnection')
            loop.run_until_complete(f)

            # clean up and notify upstream we have been disconnected
            self.proto = None  # no proto now
            self._stream_pause(False, True)  # abort the stream if one is running
            if self.timer:  # stop the timer if we have one
                self.timer.cancel()
                self.timer = None

            self.app.main_window.disconnected()  # tell upstream we disconnected

            # we wait until all tasks are complete
            pending = asyncio.Task.all_tasks()
            self.log.debug('Comms: waiting for all tasks to complete: {}'.format(pending))
            loop.run_until_complete(asyncio.gather(*pending))
            # loop.run_forever()

        except asyncio.CancelledError:
            pass

        except Exception as err:
            # self.log.error('Comms: {}'.format(traceback.format_exc()))
            self.log.error("Comms: Got serial error opening port: {0}".format(err))
            self.app.main_window.async_display(">>> Connect failed: {0}".format(err))
            self.app.main_window.disconnected()

        finally:
            loop.close()
            async_main_loop = None
            self.log.info('Comms: comms thread Exiting...')

    def _parse_m115(self, s):
        # split fields
        ll = s.split(',')

        # parse into a dict of name: value
        d = {y[0].strip(): y[1].strip() for y in [x.split(':', 1) for x in ll]}
        if 'X-CNC' not in d:
            d['X-CNC'] = '0'
        if 'FIRMWARE_NAME' not in d:
            d['FIRMWARE_NAME'] = 'UNKNOWN'
        if 'FIRMWARE_VERSION' not in d:
            d['FIRMWARE_VERSION'] = 'UNKNOWN'

        self.log.info("Comms: Firmware: {}, Version: {}, CNC: {}".format(d['FIRMWARE_NAME'], d['FIRMWARE_VERSION'], 'Yes' if d['X-CNC'] == '1' else 'No'))
        self.app.main_window.async_display(s)

    def list_sdcard(self, done_cb):
        ''' Issue a ls /sd and send results back to done_cb '''
        self.log.debug('Comms: list_sdcard')
        if self.proto and async_main_loop:
            async_main_loop.call_soon_threadsafe(self._list_sdcard, done_cb)
        else:
            self.log.warning('Comms: Cannot list sd on a closed connection')
            return False

        return True

    def _list_sdcard(self, done_cb):
        asyncio.ensure_future(self._parse_sdcard_list(done_cb))

    async def _parse_sdcard_list(self, done_cb):
        self.log.debug('Comms: _parse_sdcard_list')

        # setup callback to receive and parse listing data
        files = []
        f = asyncio.Future()
        self.redirect_incoming(lambda x: self._rcv_sdcard_line(x, files, f))

        # issue command
        self._write('M20\n')

        # wait for it to complete and get all the lines
        # add a long timeout in case it fails and we don't want to wait for ever
        try:
            await asyncio.wait_for(f, 10)

        except asyncio.TimeoutError:
            self.log.warning("Comms: Timeout waiting for sd card list")
            files = []

        self.redirect_incoming(None)

        # call upstream callback with results
        done_cb(files)

    def _rcv_sdcard_line(self, ll, files, f):
        # accumulate the file list, called with each line received
        if ll.startswith('Begin file list') or ll == 'ok':
            # ignore these lines
            return

        if ll.startswith('End file list'):
            # signal we are done (TODO should we wait for the ok?)
            f.set_result(None)

        else:
            # accumulate the incoming lines
            files.append(ll)

    def redirect_incoming(self, l):
        async_main_loop.call_soon_threadsafe(self._redirect_incoming, l)

    def _redirect_incoming(self, l):
        if l:
            if self.timer:
                # temporarily turn off status timer so we don't get unexpected lines
                self.timer.cancel()
                self.timer = None
                self._restart_timer = True
            else:
                self._restart_timer = False

            self._reroute_incoming_data_to = l

        else:
            # turn off rerouting
            self._reroute_incoming_data_to = None

            if self._restart_timer:
                self.timer = async_main_loop.call_later(0.1, self._get_reports)
                self._restart_timer = False

    # Handle incoming data, see if it is a report and parse it otherwise just display it on the console log
    # Note the data could be a line fragment and we need to only process complete lines terminated with \n
    def incoming_data(self, data, error=False):
        ''' called by Serial connection when incoming data is received '''
        if error:
            self.app.main_window.async_display("WARNING: got bad incoming data: {}".format(data))

        ll = data.splitlines(1)

        self.log.debug('Comms: incoming_data: {}'.format(ll))

        # process incoming data
        for s in ll:
            if self._fragment:
                # handle line fragment
                s = ''.join((self._fragment, s))
                self._fragment = None

            if not s.endswith('\n'):
                # this is the last line and is a fragment
                self._fragment = s
                break

            s = s.rstrip()  # strip off \n

            if len(s) == 0:
                continue

            # send the line to the requested destination for processing
            if self._reroute_incoming_data_to is not None:
                self._reroute_incoming_data_to(s)
                continue

            # process a complete line
            if s.startswith('ok'):
                if self.okcnt is not None:
                    if self.ping_pong:
                        self.okcnt.set()
                    else:
                        self.okcnt += 1

                # if there is anything after the ok display it
                if len(s) > 2:
                    self.app.main_window.async_display('ok {}'.format(s[3:]))

            elif s.startswith('<'):
                try:
                    self.handle_status(s)
                except Exception:
                    self.log.error("Comms: error parsing status")

            elif s.startswith('[PRB:'):
                # Handle PRB reply
                self.handle_probe(s)

            elif s.startswith('[GC:'):
                self.handle_state(s)

            elif s.startswith("!!") or s.startswith("error:Alarm lock"):
                self.handle_alarm(s)
                # we should now be paused
                if self.okcnt is not None and self.ping_pong:
                    # we need to unblock waiting for ok if we get this
                    self.okcnt.set()

            elif s.startswith("ALARM") or s.startswith("ERROR") or s.startswith("HALTED"):
                self.handle_alarm(s)

            elif s.startswith('//'):
                # ignore comments but display them
                # handle // action:pause etc
                pos = s.find('action:')
                if pos >= 0:
                    act = s[pos + 7:].strip()  # extract action command
                    if act in 'pause':
                        self.app.main_window.async_display('>>> Smoothie requested Pause')
                        self.is_suspend = True  # this currently only happens if we suspend (M600)
                        self._stream_pause(True, False)
                    elif act in 'resume':
                        self.app.main_window.async_display('>>> Smoothie requested Resume')
                        self._stream_pause(False, False)
                    elif act in 'disconnect':
                        self.app.main_window.async_display('>>> Smoothie requested Disconnect')
                        self.disconnect()
                    else:
                        self.log.warning('Comms: unknown action command: {}'.format(act))

                else:
                    self.app.main_window.async_display('{}'.format(s))

            elif "FIRMWARE_NAME:" in s:
                # process the response to M115
                self._parse_m115(s)

            elif s.startswith("switch "):
                # switch fan is 0
                n, x, v = s[7:].split(' ')
                self.app.main_window.ids.macros.switch_response(n, v)

            elif s.startswith("done"):
                # ignore these sent after a command on V2
                pass

            else:
                self.app.main_window.async_display('{}'.format(s))

    def handle_state(self, s):
        # [GC:G0 G55 G17 G21 G90 G94 M0 M5 M9 T1 F4000.0000 S0.8000]
        s = s[4:-1]  # strip off [GC: .. ]

        # split fields
        ll = s.split(' ')
        self.log.debug("Comms: Got state: {}".format(ll))
        # we want the current WCS and the current Tool
        if len(ll) < 11:
            self.log.warning('Comms: Bad state report: {}'.format(s))
            return

        self.app.main_window.update_state(ll)

    def handle_status(self, s):
        # <Idle|MPos:68.9980,-49.9240,40.0000,12.3456|WPos:68.9980,-49.9240,40.0000|F:12345.12|S:1.2>
        # if temp readings are enabled then also returns T:25.0,0.0|B:25.2,0.0
        s = s[1:-1]  # strip off < .. >

        # split fields
        ll = s.split('|')
        self.log.debug("Comms: Got status: {}".format(ll))
        if len(ll) < 3:
            self.log.warning('Comms: old status report - set new_status_format')
            self.app.main_window.update_status("ERROR", "set new_status_format true")
            return

        # strip off status
        status = ll[0]

        # strip of rest into a dict of name: [values,...,]
        d = {a: [float(y) for y in b.split(',')] for a, b in [x.split(':') for x in ll[1:]]}

        self.log.debug('Comms: got status:{} - rest: {}'.format(status, d))

        self.app.main_window.update_status(status, d)

        # schedule next report
        self.timer = async_main_loop.call_later(self.report_rate, self._get_reports)

    def handle_probe(self, s):
        # [PRB:1.000,80.137,10.000:0]
        ll = s[5:-1].split(':')
        c = ll[0].split(',')
        st = ll[1]
        self.app.main_window.async_display("Probe: {} - X: {}, Y: {}, Z: {}".format(st, c[0], c[1], c[2]))
        self.app.last_probe = {'X': float(c[0]), 'Y': float(c[1]), 'Z': float(c[2]), 'status': st == '1'}

    def handle_alarm(self, s):
        ''' handle case where smoothie sends us !! or an error of some sort '''
        self.log.warning('Comms: alarm message: {}'.format(s))
        # pause any streaming immediately, (let operator decide to abort or not)
        self._stream_pause(True, False)

        # NOTE old way was to abort, but we could resume if we can fix the error
        # self._stream_pause(False, True)
        # if self.proto:
        #    self.proto.flush_queue()

        # call upstream after we have allowed stream to stop
        async_main_loop.call_soon(self.app.main_window.alarm_state, s)

    def stream_gcode(self, fn, progress=None):
        ''' called from external thread to start streaming a file '''
        self.progress = progress
        if self.proto and async_main_loop:
            async_main_loop.call_soon_threadsafe(self._stream_file, fn)
            return True
        else:
            self.log.warning('Comms: Cannot print to a closed connection')
            return False

    def _stream_file(self, fn):
        self.file_streamer = asyncio.ensure_future(self.stream_file(fn))

    def stream_pause(self, pause, do_abort=False):
        ''' called from external thread to pause or kill in process streaming '''
        async_main_loop.call_soon_threadsafe(self._stream_pause, pause, do_abort)

    def _stream_pause(self, pause, do_abort):
        if self.file_streamer:
            if do_abort:
                self.pause_stream = False
                self.abort_stream = True  # aborts stream
                if self.ping_pong and self.okcnt is not None:
                    self.okcnt.set()  # release it in case it is waiting for ok so it can abort
                self.log.info('Comms: Aborting Stream')

            elif pause:
                self.pause_stream = True  # .clear() # pauses stream
                # tell UI we paused (and if it was due to a suspend)
                self.app.main_window.action_paused(True, self.is_suspend)
                self.is_suspend = False  # always clear this
                self.log.info('Comms: Pausing Stream')

            else:
                self.pause_stream = False  # .set() # releases pause on stream
                self.app.main_window.action_paused(False)
                self.log.info('Comms: Resuming Stream')

    async def stream_file(self, fn):
        self.log.info('Comms: Streaming file {} to port'.format(fn))
        self.is_streaming = True
        self.abort_stream = False
        self.pause_stream = False  # .set() # start out not paused
        self.last_tool = None

        # optional do not use ping pong
        if self.app.fast_stream:
            self.ping_pong = False
            self.log.info("Comms: using fast stream")
        else:
            self.ping_pong = True

        if self.ping_pong:
            self.okcnt = asyncio.Event()
        else:
            self.okcnt = 0

        f = None
        success = False
        linecnt = 0
        tool_change_state = 0

        try:
            f = await aiofiles.open(fn, mode='r')
            while True:

                if tool_change_state == 0:
                    # await self.pause_stream.wait() # wait for pause to be released
                    # needed to do it this way as the Event did not seem to work it would pause but not unpause
                    # TODO maybe use Future here to wait for unpause
                    # create future when pause then await it here then delete it
                    if self.pause_stream:
                        if self.ping_pong:
                            # we need to ignore any ok from command while we are paused
                            self.okcnt = None

                        # wait until pause is released
                        while self.pause_stream:
                            await asyncio.sleep(1)
                            if self.progress:
                                self.progress(linecnt)
                            if self.abort_stream:
                                break

                        # recreate okcnt
                        if self.ping_pong:
                            self.okcnt = asyncio.Event()

                    # read next line
                    line = await f.readline()

                    if not line:
                        # EOF
                        break

                    if self.abort_stream:
                        break

                    line = line.strip()
                    if len(line) == 0 or line.startswith(';'):
                        continue

                    if line.startswith('(MSG'):
                        self.app.main_window.async_display(line)
                        continue

                    if line.startswith('(NOTIFY'):
                        notify = Notify()
                        notify.send(line)
                        continue

                    if line.startswith('('):
                        continue

                    if line.startswith('T'):
                        self.last_tool = line

                    if self.app.manual_tool_change:
                        # handle tool change M6 or M06
                        if line == "M6" or line == "M06" or "M6 " in line or "M06 " in line or line.endswith("M6"):
                            tool_change_state = 1

                    if self.app.wait_on_m0:
                        # handle M0 if required
                        if line == "M0" or line == "M00":
                            # we basically wait for the continue dialog to be dismissed
                            self.app.main_window.m0_dlg()
                            self.m0 = asyncio.Event()
                            await self.m0.wait()
                            self.m0 = None
                            continue

                if self.abort_stream:
                    break

                # handle manual tool change
                if self.app.manual_tool_change and tool_change_state > 0:
                    if tool_change_state == 1:
                        # we insert an M400 so we can wait for last command to actually execute and complete
                        line = "M400"
                        tool_change_state = 2

                    elif tool_change_state == 2:
                        # we got the M400 so queue is empty so we send a suspend and tell upstream
                        line = "M600"
                        # we need to pause the stream here immediately, but the real _stream_pause will be called by suspend
                        self.pause_stream = True  # we don't normally set this directly
                        self.app.main_window.tool_change_prompt("{} - {}".format(line, self.last_tool))
                        tool_change_state = 0

                # s = time.time()
                # print("{} - {}".format(s, line))
                # send the line
                if self.ping_pong and self.okcnt is not None:
                    # clear the event, which will be set by an incoming ok
                    self.okcnt.clear()

                # sending stripped line so add \n
                self._write("{}\n".format(line))

                # wait for ok from that command (I'd prefer to interleave with the file read but it is too complex)
                if self.ping_pong and self.okcnt is not None:
                    try:
                        await self.okcnt.wait()
                        # e = time.time()
                        # print("{} ({}ms) ok".format(e, (e - s) * 1000))
                    except Exception:
                        self.log.debug('Comms: okcnt wait cancelled')
                        break

                # when streaming we need to yield until the flow control is dealt with
                if self.proto._connection_lost:
                    # Yield to the event loop so connection_lost() may be
                    # called.  Without this, _drain_helper() would return
                    # immediately, and code that calls
                    #     write(...); await drain()
                    # in a loop would never call connection_lost(), so it
                    # would not see an error when the socket is closed.
                    await asyncio.sleep(0)

                if self.abort_stream:
                    break

                # if the buffers are full then wait until we can send some more
                await self.proto._drain_helper()
                if self.abort_stream:
                    break

                if self.ping_pong:
                    # we only count lines that start with GMXY
                    if line[0] in "GMXY":
                        linecnt += 1
                else:
                    linecnt += 1

                if self.progress and linecnt % 10 == 0:  # update every 10 lines
                    if self.ping_pong:
                        # number of lines sent
                        self.progress(linecnt)
                    else:
                        # number of lines ok'd
                        self.progress(self.okcnt)

            success = not self.abort_stream

        except Exception as err:
            self.log.error("Comms: Stream file exception: {}".format(err))
            # print('Exception: {}'.format(traceback.format_exc()))

        finally:
            if f:
                await f.close()

            if self.abort_stream:
                if self.proto:
                    self.proto.flush_queue()

                self._write('\x18')

            if success and not self.ping_pong:
                self.log.debug('Comms: Waiting for okcnt to catch up: {} vs {}'.format(self.okcnt, linecnt))
                # we have to wait for all lines to be ack'd
                tmo = 0
                while self.okcnt < linecnt:
                    if self.progress:
                        self.progress(self.okcnt)
                    if self.abort_stream:
                        success = False
                        break

                    await asyncio.sleep(1)
                    tmo += 1
                    if tmo >= 30:  # waited 30 seconds we need to give up
                        self.log.warning("Comms: timed out waitng for backed up oks")
                        break
                # update final progress display
                if self.progress:
                    self.progress(self.okcnt)

            self.file_streamer = None
            self.progress = None
            self.okcnt = None
            self.is_streaming = False
            self.do_query = False

            # notify upstream that we are done
            self.app.main_window.stream_finished(success)

            self.log.info('Comms: Streaming complete: {}'.format(success))

        return success

    def upload_gcode(self, fn, progress=None, done=None):
        ''' called from external thread to start uploading a file '''
        self.progress = progress
        if self.proto and async_main_loop:
            async_main_loop.call_soon_threadsafe(self._upload_gcode, fn, done)
            return True
        else:
            self.log.warning('Comms: Cannot upload to a closed connection')
            return False

    def _upload_gcode(self, fn, donecb):
        self.file_streamer = asyncio.ensure_future(self._stream_upload_gcode(fn, donecb))

    def _rcv_upload_gcode_line(self, ll, ev):
        if ll == 'ok':
            ev.set()
            self.okcnt += 1

        elif ll.startswith('open failed,') or ll.startswith('Error:') or ll.startswith('ALARM:') or ll.startswith('!!') or ll.startswith('error:'):
            self.upload_error = True
            ev.set()

        elif ll.startswith('Writing to file:') or ll.startswith('Done saving file.'):
            # ignore these lines
            return

        else:
            self.log.warning('Comms: unknown response: {}'.format(ll))

    async def _stream_upload_gcode(self, fn, donecb):
        self.log.info('Comms: Upload gcode file {}'.format(fn))

        self.upload_error = False
        self.abort_stream = False
        f = None
        success = False
        linecnt = 0
        okev = asyncio.Event()

        # use the simple ping pong one line per ok or fast stream
        self._redirect_incoming(lambda x: self._rcv_upload_gcode_line(x, okev))

        try:
            self.okcnt = 0
            okev.clear()
            self._write("M28 {}\n".format(os.path.basename(fn).lower()))
            await okev.wait()

            if self.upload_error:
                self.log.error('Comms: M28 failed for file /sd/{}'.format(os.path.basename(fn)))
                self.app.main_window.async_display("error: M28 failed to open file")
                return

            self.okcnt = 0
            if self.app.fast_stream:
                self.ping_pong = False
                self.log.info("Comms: using fast stream")
            else:
                self.ping_pong = True

            f = await aiofiles.open(fn, mode='r')

            while True:
                # read next line
                line = await f.readline()

                if not line:
                    # EOF
                    break

                ln = line.strip()
                if len(ln) == 0 or ln.startswith(';') or ln.startswith('('):
                    continue

                # clear the event, which will be set by an incoming ok
                if self.ping_pong:
                    okev.clear()
                self._write("{}\n".format(ln))

                if self.ping_pong:
                    # wait for ok from that line
                    await okev.wait()

                if self.upload_error:
                    self.log.error('Comms: Upload failed for file /sd/{}'.format(os.path.basename(fn)))
                    self.app.main_window.async_display("error: upload failed during transfer")
                    return

                # when streaming we need to yield until the flow control is dealt with
                if self.proto._connection_lost:
                    await asyncio.sleep(0)

                if self.abort_stream:
                    break

                # if the buffers are full then wait until we can send some more
                await self.proto._drain_helper()

                if self.abort_stream:
                    break

                if self.ping_pong:
                    if ln[0] in "GMXY":
                        # we only count lines that start with GMXY
                        linecnt += 1
                else:
                    # we count all lines sent
                    linecnt += 1

                if self.progress and linecnt % 100 == 0:  # update every 100 lines
                    if self.ping_pong:
                        # number of lines sent
                        self.progress(linecnt)
                    else:
                        # number of lines ok'd
                        self.progress(self.okcnt)

            success = not self.abort_stream

        except Exception as err:
            self.log.error("Comms: Upload GCode file exception: {}".format(err))

        finally:
            if not self.ping_pong:
                # wait for oks to catch up
                self.log.debug('Comms: Waiting for okcnt to catch up: {} vs {}'.format(self.okcnt, linecnt))
                # we have to wait for all lines to be ack'd
                tmo = 0
                while self.okcnt < linecnt:
                    if self.progress:
                        self.progress(self.okcnt)

                    await asyncio.sleep(1)
                    tmo += 1
                    if tmo >= 30:  # waited 30 seconds we need to give up
                        self.log.warning("Comms: timed out waiting for backed up oks")
                        break

                # update final progress display
                if self.progress:
                    self.progress(self.okcnt)

            okev.clear()
            self._write("M29\n")
            await okev.wait()

            self._redirect_incoming(None)
            if f:
                await f.close()
            self.progress = None
            self.file_streamer = None
            self.okcnt = None
            donecb(success)
            self.log.info('Comms: Upload GCode complete: {}'.format(success))

        return success

    def release_m0(self):
        if self.m0:
            self.m0.set()

    @staticmethod
    def file_len(fname, all=False):
        # TODO if windows use a slow python method
        if not all:
            # use external process to quickly find total number of G/M lines in file
            # NOTE some laser raster formats have lines that start with X and no G/M
            # and some CAM programs just output X or Y lines
            p = subprocess.Popen(['grep', '-c', "^[GMXY]", fname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result, err = p.communicate()
            if p.returncode != 0:
                raise IOError(err)
            return int(result.strip().split()[0])
        else:
            # count all lines
            p = subprocess.Popen(['wc', fname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result, err = p.communicate()
            if p.returncode != 0:
                raise IOError(err)
            return int(result.strip().split()[0])


if __name__ == "__main__":

    import datetime
    from time import sleep

    ''' a standalone streamer to test it with '''

    class CommsApp(object):
        """ Standalone app callbacks """
        def __init__(self):
            super(CommsApp, self).__init__()
            self.root = self
            self.log = logging.getLogger()
            self.start_event = threading.Event()
            self.end_event = threading.Event()
            self.is_connected = False
            self.ok = False
            self.main_window = self
            self.timer = None
            self.is_cnc = True
            self.fast_stream = False

        def connected(self):
            self.log.debug("CommsApp: Connected...")
            self.is_connected = True
            self.start_event.set()

        def disconnected(self):
            self.log.debug("CommsApp: Disconnected...")
            self.is_connected = False
            self.start_event.set()

        def async_display(self, data):
            print(data)

        def stream_finished(self, ok):
            self.log.debug('CommsApp: stream finished: {}'.format(ok))
            self.ok = ok
            self.end_event.set()

        def alarm_state(self, s):
            self.ok = False
            # in this case we do want to disconnect
            comms.proto.transport.close()

        def update_status(self, stat, d):
            pass

        def manual_tool_change(self, l):
            print("tool change: {}\n".format(l))

        def action_paused(self, flag, suspend=False):
            print("paused: {}, suspended: {}", flag, suspend)

        def get_queries(self):
            return ""

        def wait_on_m0(self, l):
            print("wait on m0: {}\n".format(l))

    def display_progress(n):
        global start, nlines

        if nlines:
            now = datetime.datetime.now()
            d = (now - start).seconds
            if n > 10 and d > 10:
                # we have to wait a bit to get reasonable estimates
                lps = n / d
                eta = (nlines - n) / lps
            else:
                eta = 0
            et = datetime.timedelta(seconds=int(eta))
            print("progress: {}/{} {:.1%} ETA {}".format(n, nlines, n / nlines, et))

    def upload_done(x):
        app.ok = x
        app.end_event.set()

    if len(sys.argv) < 3:
        print("Usage: {} port file [-u] [-f] [-d]".format(sys.argv[0]))
        exit(0)

    upload = False
    loglevel = logging.INFO
    app = CommsApp()
    comms = Comms(app, 0)
    while len(sys.argv) > 3:
        a = sys.argv.pop()
        if a == '-u':
            upload = True
            print('Upload only')
        elif a == '-f':
            app.fast_stream = True
            print('Fast Stream')
        elif a == '-d':
            loglevel = logging.DEBUG
        else:
            print("Unknown option: {}".format(a))

    logging.basicConfig(format='%(levelname)s:%(message)s', level=loglevel)

    try:
        nlines = Comms.file_len(sys.argv[2], app.fast_stream)  # get number of lines so we can do progress and ETA
        print('number of lines: {}'.format(nlines))
    except Exception:
        print('Exception: {}'.format(traceback.format_exc()))
        nlines = None

    start = None

    try:
        t = comms.connect(sys.argv[1])
        if app.start_event.wait(5):  # wait for connected as it is in a separate thread
            if app.is_connected:
                # wait for startup to clear up any incoming oks
                sleep(2)  # Time in seconds.
                start = datetime.datetime.now()
                print("Print started at: {}".format(start.strftime('%x %X')))

                if upload:
                    comms.upload_gcode(sys.argv[2], progress=lambda x: display_progress(x), done=upload_done)
                else:
                    comms.stream_gcode(sys.argv[2], progress=lambda x: display_progress(x))

                app.end_event.wait()  # wait for streaming to complete

                now = datetime.datetime.now()
                print("File sent: {}".format('Ok' if app.ok else 'Failed'))
                print("Print ended at : {}".format(now.strftime('%x %X')))
                if start:
                    et = datetime.timedelta(seconds=int((now - start).seconds))
                    print("Elapsed time: {}".format(et))

            else:
                print("Error: Failed to connect")

        else:
            print("Error: Connection timed out")

    except KeyboardInterrupt:
        print("Interrupted- aborting")
        comms._stream_pause(False, True)
        app.end_event.wait()  # wait for streaming to complete

    finally:
        # now stop the comms if it is connected or running
        comms.stop()
        t.join()
