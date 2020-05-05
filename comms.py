import asyncio
import serial_asyncio
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


class SerialConnection(asyncio.Protocol):
    def __init__(self, cb, fcon, fclo, is_net=False):
        super().__init__()
        self.log = logging.getLogger()  # getChild('SerialConnection')
        self.log.debug('SerialConnection: creating SerialConnection')
        self.cb = cb
        self.fcon = fcon
        self.fclo = fclo
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
            self.log.info('Buffer limits: {} - {}'.format(transport._high_water, transport._low_water))
        else:
            # transport.serial.rts = False  # You can manipulate Serial object via transport
            transport.serial.reset_input_buffer()
            transport.serial.reset_output_buffer()

        self.fcon.set_result("Connected")

    def flush_queue(self):
        # if self.transport:
        #     self.transport.abort()
        # TODO does not do anything at the moment possible is to do transport.abort() but that closes the connection
        if not self.is_net and self.transport:
            self.transport.serial.reset_output_buffer()

    def send_message(self, data, hipri=False):
        """ Feed a message to the sender coroutine. """
        self.log.debug('SerialConnection: send_message: {}'.format(data))
        self.transport.write(data.encode('utf-8'))

    def data_received(self, data):
        # print('data received', repr(data))
        str = ''
        try:
            # FIXME this is a problem when it splits utf-8, may need to get whole lines here anyway
            str = data.decode('utf-8')
        except Exception as err:
            self.log.error("SerialConnection: Got decode error on data {}: {}".format(repr(data), err))
            str = repr(data)  # send it upstream anyway

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
        self.fclo.set_result('Disconnected')

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
        self.log.info('SerialConnection: pause writing: {}'.format(self.transport.get_write_buffer_size()))
        if not self.is_net:
            return
        # we only do this pause stream stuff for net
        assert not self._paused
        self._paused = True

    def resume_writing(self):
        self.log.info('SerialConnection: resume writing: {}'.format(self.transport.get_write_buffer_size()))
        if not self.is_net:
            return
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
        self.fcomms = None
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
        self.loop = asyncio.get_event_loop()
        self.log = logging.getLogger()  # .getChild('Comms')
        # logging.getLogger().setLevel(logging.DEBUG)

    def connect(self, port):
        ''' called to connect to given port '''
        if self.proto:
            self.log.error("Comms: Already connected")
            self.app.main_window.async_display('>>> Already connected')
            return

        self.port = port
        self.fcomms = asyncio.ensure_future(self.run_comms())

    def disconnect(self):
        ''' called to disconnect '''
        if self.proto:
            self.proto.transport.close()

    def write(self, data):
        ''' Write to serial port '''
        if self.proto:
            self.proto.send_message(data)
        else:
            self.log.warning('Comms: Cannot write to closed connection: ' + data)
            # self.app.main_window.async_display("<<< {}".format(data))

    def _get_reports(self):
        if self._restart_timer:
            return

        queries = self.app.main_window.get_queries()
        if queries:
            self.write(queries)

        if self.net_connection:
            if not self.is_streaming:
                self.write('?\n')
        else:
            self.write('?')

    def stop(self):
        ''' called when app is exiting '''
        if self.proto:
            # abort any streaming immediately
            self.stream_pause(False, True)
            if self.file_streamer:
                self.file_streamer.cancel()

            # we need to close the transport, this will cause comms task to exit
            self.proto.transport.close()

    def get_ports(self):
        return [port for port in serial.tools.list_ports.comports() if port[2] != 'n/a']

    async def run_comms(self):
        ''' called by connect() '''
        self.log.info('Comms: starting...')

        loop = self.loop
        fconnected = loop.create_future()
        fclosed = loop.create_future()

        # if tcp connection port will be net://ipaddress[:port]
        # otherwise it will be serial:///dev/ttyACM0 or serial://COM2:
        if self.port.startswith('net://'):
            sc_factory = functools.partial(SerialConnection, cb=self, fcon=fconnected, fclo=fclosed, is_net=True)  # uses partial so we can pass a parameter
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
            if self.app.fast_stream:  # optional do not use ping pong for network connections
                self.ping_pong = False

        elif self.port.startswith('serial://'):
            sc_factory = functools.partial(SerialConnection, cb=self, fcon=fconnected, fclo=fclosed)  # uses partial so we can pass a parameter
            self.net_connection = False
            self.port = self.port[9:]
            serial_conn = serial_asyncio.create_serial_connection(loop, sc_factory, self.port, baudrate=115200)

        else:
            self.log.error('Comms: Not a valid connection port: {}'.format(self.port))
            self.app.main_window.async_display('>>> Connect failed: unknown connection type, use "serial://" or "net://"'.format(self.port))
            self.app.main_window.disconnected()
            return

        try:
            transport, self.proto = await serial_conn  # sets up connection returning transport and protocol handler
            # wait for successful connection
            await fconnected

            self.log.debug('Comms: serial connection connected')

            # this is when we are really setup and ready to go, notify upstream
            self.app.main_window.connected()

            # issue a M115 command to get things started
            self.write('\n')
            self.write('M115\n')

            if self.report_rate > 0:
                # start a timer to get the reports
                self.timer = self.loop.call_later(self.report_rate, self._get_reports)

            # wait until we are disconnected
            self.log.debug('Comms: waiting until disconnection')
            await fclosed

            # clean up and notify upstream we have been disconnected
            self.proto = None  # no proto now
            self.stream_pause(False, True)  # abort the stream if one is running
            if self.timer:  # stop the timer if we have one
                self.timer.cancel()
                self.timer = None

            self.app.main_window.disconnected()  # tell upstream we disconnected

        except asyncio.CancelledError:
            pass

        except Exception as err:
            self.log.error('Comms: {}'.format(traceback.format_exc()))
            self.log.error("Comms: Got serial error opening port: {0}".format(err))
            self.app.main_window.async_display(">>> Connect failed: {0}".format(err))
            self.app.main_window.disconnected()

        finally:
            self.log.info('Comms: ended')

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
        if self.proto:
            asyncio.ensure_future(self._parse_sdcard_list(done_cb))
        else:
            self.log.warning('Comms: Cannot list sd on a closed connection')
            return False

        return True

    async def _parse_sdcard_list(self, done_cb):
        self.log.debug('Comms: _parse_sdcard_list')

        # setup callback to receive and parse listing data
        files = []
        f = asyncio.Future()
        self.redirect_incoming(lambda x: self._rcv_sdcard_line(x, files, f))

        # issue command
        self.write('M20\n')

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
                self.timer = self.loop.call_later(0.1, self._get_reports)
                self._restart_timer = False

    # Handle incoming data, see if it is a report and parse it otherwise just display it on the console log
    # Note the data could be a line fragment and we need to only process complete lines terminated with \n
    def incoming_data(self, data):
        ''' called by Serial connection when incoming data is received '''
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
                        self.stream_pause(True, False)
                    elif act in 'resume':
                        self.app.main_window.async_display('>>> Smoothie requested Resume')
                        self.stream_pause(False, False)
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
        if len(ll) < 10:
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
        self.timer = self.loop.call_later(self.report_rate, self._get_reports)

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
        self.stream_pause(True, False)

        # NOTE old way was to abort, but we could resume if we can fix the error
        # self.stream_pause(False, True)
        # if self.proto:
        #    self.proto.flush_queue()

        # call upstream
        self.app.main_window.alarm_state(s)

    def stream_pause(self, pause, do_abort=False):
        ''' called to pause or kill in process streaming '''
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

    def stream_gcode(self, fn, progress=None):
        ''' called to start streaming a file '''
        self.progress = progress
        if self.proto:
            self.file_streamer = asyncio.ensure_future(self.stream_file(fn))
            return True
        else:
            self.log.warning('Comms: Cannot print to a closed connection')
            return False

    async def stream_file(self, fn):
        self.log.info('Comms: Streaming file {} to port'.format(fn))
        self.is_streaming = True
        self.abort_stream = False
        self.pause_stream = False  # .set() # start out not paused
        self.last_tool = None

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

                    ln = line.strip()
                    if len(ln) == 0 or ln.startswith(';'):
                        continue

                    if ln.startswith('(MSG'):
                        self.app.main_window.async_display(ln)
                        continue

                    if ln.startswith('(NOTIFY'):
                        Notify.send(ln)
                        continue

                    if ln.startswith('('):
                        continue

                    if ln.startswith('T'):
                        self.last_tool = ln

                    if self.app.manual_tool_change:
                        # handle tool change M6 or M06
                        if ln == "M6" or ln == "M06" or "M6 " in ln or "M06 " in ln or ln.endswith("M6"):
                            tool_change_state = 1

                    if self.app.wait_on_m0:
                        # handle M0 if required
                        if ln == "M0" or ln == "M00":
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
                        line = "M400\n"
                        tool_change_state = 2

                    elif tool_change_state == 2:
                        # we got the M400 so queue is empty so we send a suspend and tell upstream
                        line = "M600\n"
                        # we need to pause the stream here immediately, but the real stream_pause will be called by suspend
                        self.pause_stream = True  # we don't normally set this directly
                        self.app.main_window.tool_change_prompt("{} - {}".format(ln, self.last_tool))
                        tool_change_state = 0

                # s= time.time()
                # print("{} - {}".format(s, line))
                # send the line
                if self.ping_pong and self.okcnt is not None:
                    # clear the event, which will be set by an incoming ok
                    self.okcnt.clear()

                self.write(line)

                # wait for ok from that command (I'd prefer to interleave with the file read but it is too complex)
                if self.ping_pong and self.okcnt is not None:
                    try:
                        await self.okcnt.wait()
                        # e= time.time()
                        # print("{} ({}) ok".format(e, (e-s)*1000, ))
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

                # we only count lines that start with GMXY
                if ln[0] in "GMXY":
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
            print('Exception: {}'.format(traceback.format_exc()))

        finally:
            if f:
                await f.close()

            if self.abort_stream:
                if self.proto:
                    self.proto.flush_queue()

                self.write('\x18')

            if success and not self.ping_pong:
                self.log.debug('Comms: Waiting for okcnt to catch up: {} vs {}'.format(self.okcnt, linecnt))
                # we have to wait for all lines to be ack'd
                while self.okcnt < linecnt:
                    if self.progress:
                        self.progress(self.okcnt)
                    if self.abort_stream:
                        success = False
                        break

                    await asyncio.sleep(1)

            self.file_streamer = None
            self.progress = None
            self.okcnt = None
            self.is_streaming = False
            self.do_query = False

            # notify upstream that we are done
            self.app.main_window.stream_finished(success)

            self.log.info('Comms: Streaming complete: {}'.format(success))

        return success

    def upload_gcode(self, fn, progress=None, donecb=None):
        ''' called to start uploading a file '''
        self.progress = progress
        if self.proto:
            self.file_streamer = asyncio.ensure_future(self._stream_upload_gcode(fn, donecb))
            return True
        else:
            self.log.warning('Comms: Cannot upload to a closed connection')
            return False

    def _rcv_upload_gcode_line(self, ll, ev):
        if ll == 'ok':
            ev.set()

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
        okev = asyncio.Event()
        self.upload_error = False
        self.abort_stream = False
        f = None
        success = False
        linecnt = 0
        # use the simple ping pong one line per ok
        self.redirect_incoming(lambda x: self._rcv_upload_gcode_line(x, okev))

        try:
            okev.clear()
            self.write("M28 {}\n".format(os.path.basename(fn).lower()))
            await okev.wait()

            if self.upload_error:
                self.log.error('Comms: M28 failed for file /sd/{}'.format(os.path.basename(fn)))
                self.app.main_window.async_display("error: M28 failed to open file")
                return

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
                okev.clear()
                self.write(line)
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

                # we only count lines that start with GMXY
                if ln[0] in "GMXY":
                    linecnt += 1

                if self.progress and linecnt % 100 == 0:  # update every 100 lines
                    # number of lines sent
                    self.progress(linecnt)

            success = not self.abort_stream

        except Exception as err:
            self.log.error("Comms: Upload GCode file exception: {}".format(err))

        finally:
            okev.clear()
            self.write("M29\n")
            await okev.wait()

            self.redirect_incoming(None)
            if f:
                await f.close()
            self.progress = None
            self.file_streamer = None

            donecb(success)
            self.log.info('Comms: Upload GCode complete: {}'.format(success))

        return success

    def release_m0(self):
        if self.m0:
            self.m0.set()

    @staticmethod
    def file_len(fname):
        ''' use external process to quickly find total number of G/M lines in file '''
        # NOTE some laser raster formats have lines that start with X and no G/M
        # and some CAM programs just output X or Y lines
        # TODO if windows use a slow python method
        p = subprocess.Popen(['grep', '-c', "^[GMXY]", fname], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, err = p.communicate()
        if p.returncode != 0:
            raise IOError(err)
        return int(result.strip().split()[0])


if __name__ == "__main__":
    import signal
    import datetime
    from time import sleep

    ''' a standalone streamer to test it with '''

    class CommsApp():
        """ Standalone app callbacks """
        def __init__(self):
            super(CommsApp, self).__init__()
            self.root = self
            self.log = logging.getLogger()
            self.start_event = asyncio.Event()
            self.end_event = asyncio.Event()
            self.is_connected = False
            self.ok = False
            self.main_window = self
            self.timer = None
            self.is_cnc = True
            self.wait_on_m0 = False

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
            # comms.proto.transport.close()

        def update_status(self, stat, d):
            pass

        def manual_tool_change(self, l):
            print("tool change: {}\n".format(l))

        def action_paused(self, flag, suspend=False):
            print("paused: {}, suspended: {}", flag, suspend)

        def get_queries(self):
            return ""

    class CommsMain():
        start = None
        nlines = None
        comms = None

        def display_progress(self, n):
            if self.nlines:
                now = datetime.datetime.now()
                d = (now - self.start).seconds
                if n > 10 and d > 10:
                    # we have to wait a bit to get reasonable estimates
                    lps = n / d
                    eta = (self.nlines - n) / lps
                else:
                    eta = 0
                et = datetime.timedelta(seconds=int(eta))
                print("progress: {}/{} {:.1%} ETA {}".format(n, self.nlines, n / self.nlines, et))

        def upload_done(self, x):
            self.app.ok = x
            self.app.end_event.set()

        async def main(self):
            if len(sys.argv) < 3:
                print("Usage: {} port file [-u] [-f]".format(sys.argv[0]))
                exit(0)

            self.app = CommsApp()
            self.comms = Comms(self.app, 10)

            upload = False

            while len(sys.argv) > 3:
                a = sys.argv.pop()
                if a == '-u':
                    upload = True
                    print('Upload only')
                elif a == '-f':
                    self.comms.ping_pong = False
                    print('Fast Stream')
                else:
                    print("Unknown option: {}".format(a))

            try:
                self.nlines = Comms.file_len(sys.argv[2])  # get number of lines so we can do progress and ETA
                print('number of lines: {}'.format(self.nlines))
            except Exception:
                print('Exception: {}'.format(traceback.format_exc()))
                self.nlines = None

            try:
                self.app.start_event.clear()
                self.app.end_event.clear()

                t = self.comms.connect(sys.argv[1])
                await self.app.start_event.wait()  # wait for connected
                if self.app.is_connected:
                    # wait for startup to clear up any incoming oks
                    await asyncio.sleep(2)

                    self.start = datetime.datetime.now()
                    print("Print started at: {}".format(self.start.strftime('%x %X')))

                    if upload:
                        self.comms.upload_gcode(sys.argv[2], progress=lambda x: self.display_progress(x), donecb=self.upload_done)
                    else:
                        self.comms.stream_gcode(sys.argv[2], progress=lambda x: self.display_progress(x))

                    await self.app.end_event.wait()  # wait for streaming to complete

                    now = datetime.datetime.now()
                    print("File sent: {}".format('Ok' if self.app.ok else 'Failed'))
                    print("Print ended at : {}".format(now.strftime('%x %X')))
                    if self.start:
                        et = datetime.timedelta(seconds=int((now - self.start).seconds))
                        print("Elapsed time: {}".format(et))

                else:
                    print("Error: Failed to connect")

            except KeyboardInterrupt:
                print("Interrupted- aborting")
                self.comms.stream_pause(False, True)
                await self.app.end_event.wait()  # wait for streaming to complete

            finally:
                # now stop the comms if it is connected or running
                self.comms.stop()
                await self.comms.fcomms  # wait for end

    def handle_exception(loop, context):
        # context["message"] will always be there; but context["exception"] may not
        msg = context.get("exception", context["message"])
        print("Caught exception: {}".format(msg))
        loop.stop()

    def ask_exit(signame):
        print("got signal %s: exit" % signame)
        if commsmain.comms:
            # abort stream
            commsmain.comms.stream_pause(False, True)

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

    loop = asyncio.get_event_loop()
    loop.set_debug(False)
    loop.set_exception_handler(handle_exception)
    commsmain = CommsMain()

    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame),
                                functools.partial(ask_exit, signame))

    try:
        loop.run_until_complete(commsmain.main())
    finally:
        loop.close()
