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

	ScrollableLabel:
		text: kbd_widget.log

    PageLayout:
        size_hint: 1.0, 1.0
        border: 20
        KbdWidget:
            id: kbd_widget

        JogRoseWidget:
            id: jog_rose

        Button:
            text: 'macro page place holder'
            background_color: 0,1,0,1

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
        else:
            print("Jog " + axis + ' ' + str(v))

class ScrollableLabel(ScrollView):
    text= StringProperty()

class KbdWidget(GridLayout):
    log= StringProperty()

    def do_action(self, key):
        print("Key " + key)
        if key == 'Send':
        	print("Sending " + self.display.text)
        	self.log += self.display.text + '\n'
        	self.display.text = ''
        elif key == 'BS':
        	self.display.text = self.display.text[:-1]
        else:
        	self.display.text += key

	def handle_input(self, s):
		self.log += s + '\n'
		self.display.text = ''

class MainWindow(BoxLayout):
	pass

class SmoothieHost(App):
	def build(self):
		return MainWindow()

if __name__ == "__main__":
	SmoothieHost().run()



