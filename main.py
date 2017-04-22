import kivy

from kivy.app import App

from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, ObjectProperty
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.behaviors.button import ButtonBehavior
from kivy.vector import Vector
from kivy.clock import Clock, mainthread
#from kivy.garden.gauge import Gauge
from kivy.factory import Factory

import threading
import asyncio
import serial_asyncio

async_main_loop= None
comms= None

Builder.load_string('''
#:include jogrose.kv
#:include kbd.kv

<ScrollableLabel>:
    Label:
        size_hint_y: None
        height: self.texture_size[1]
        text_size: self.width, None
        text: root.text

<MainWindow>:
    orientation: 'horizontal'

    BoxLayout:
        orientation: 'vertical'
        ScrollableLabel:
            id: log_window
            text: kbd_widget.log

        BoxLayout:
            orientation: 'horizontal'
            Button:
                id: connect_button
                size_hint_y: None
                size: 20, 40
                text: 'Connect'
                on_press: root.connect()

    PageLayout:
        id: page_layout
        size_hint: 1.0, 1.0
        border: 20
        KbdWidget:
            id: kbd_widget

        JogRoseWidget:
            id: jog_rose

        Button:
            text: 'macro page place holder'
            background_color: 0,1,0,1

        Button:
            text: 'temperature/extruder place holder'
            background_color: 0,0,1,1

        Button:
            text: 'play file page place holder'
            background_color: 0,1,1,1

        Button:
            text: 'DRO place holder'
            background_color: 1,1,0,1

''')

class CircularButton(ButtonBehavior, Widget):
    text= StringProperty()
    def collide_point(self, x, y):
        return Vector(x, y).distance(self.center) <= self.width / 2

class ArrowButton(ButtonBehavior, Widget):
    text= StringProperty()
    angle= NumericProperty()
    # def collide_point(self, x, y):
    #     bmin= Vector(self.center) - Vector(25, 25)
    #     bmax= Vector(self.center) + Vector(25, 25)
    #     return Vector.in_bbox((x, y), bmin, bmax)

class JogRoseWidget(RelativeLayout):
    def handle_action(self, axis, v):
        x10= self.x10_cb.active
        if x10:
            v *= 10
        if axis == 'H':
            print("G0 X0 Y0")
            comms.write('G0 X0 Y0\n')
        else:
            print("Jog " + axis + ' ' + str(v))
            comms.write(axis + ' ' + str(v) + '\n')

class ScrollableLabel(ScrollView):
    text= StringProperty()

class KbdWidget(GridLayout):
    log= StringProperty()

    def do_action(self, key):
        print("Key " + key)
        if key == 'Send':
            print("Sending " + self.display.text)
            self.log +=  '<< ' + self.display.text + '\n'
            comms.write(self.display.text + '\n')
            self.display.text = ''
        elif key == 'BS':
            self.display.text = self.display.text[:-1]
        else:
            self.display.text += key

    def handle_input(self, s):
        self.log += ('<< ' + s + '\n')
        comms.write(s + '\n')
        self.display.text = ''

class MainWindow(BoxLayout):
    def __init__(self, **kwargs):
        super(MainWindow, self).__init__(**kwargs)
        self.is_connected= False
        #     Clock.schedule_once(self.my_callback, 5)

    # def my_callback(self, dt):
    #     print("switch page")
    #     self.ids.page_layout.page= 2
    def connect(self):
        if self.is_connected:
            print("Disconnecting...")
            self.ids.kbd_widget.log += "Disconnecting...\n"
            comms.disconnect()
        else:
            print("Connecting...")
            self.ids.kbd_widget.log += "Connecting...\n"
            comms.connect('/dev/ttyACM1')

    @mainthread
    def display(self, data):
        self.ids.kbd_widget.log += data

    @mainthread
    def connected(self):
        print("Connected...")
        self.is_connected= True
        self.ids.connect_button.text= "Disconnect"

    @mainthread
    def disconnected(self):
        print("Disconnected...")
        self.is_connected= False
        self.ids.connect_button.text= "Connect"

    def error_message(self, str):
        self.display('! ' + str + '\n')


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


class SmoothieHost(App):
    #Factory.register('Comms', cls=Comms)
    def on_stop(self):
        # The Kivy event loop is about to stop, stop the async main loop
        comms.stop(); # stop the aysnc loop

    def build(self):
        global comms
        comms= Comms(self)
        return MainWindow()

if __name__ == "__main__":
    SmoothieHost().run()



