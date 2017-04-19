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
<CircularButton>:
    canvas:
        Ellipse:
            pos: self.pos
            size: self.size
    Label:
        pos: root.pos
        size: root.size
        color: 1,0,0,1
        text: root.text

<ArrowButton>:
    # canvas.before:
    #     Color:
    #         rgba: 1, 0, 0, 1
    #     Rectangle:
    #         pos: self.pos
    #         size: self.size

    canvas:
        Color:
            rgba: 0,0,1,1
        PushMatrix
        Translate:
            x: self.pos[0]
            y: self.pos[1]
        Rotate:
            angle: root.angle
            origin: 25,25
        Mesh:
            mode: 'triangle_fan'
            vertices: 0,0,0,0, 0,25,0,0, 25,50,0,0, 50,25,0,0, 50,0,0,0
            indices: 0,1,2,3,4
        PopMatrix

    Label:
        size_hint: None, None
        pos: root.pos
        size: root.size
        color: 1,1,1,1
        text: root.text

<JogRoseWidget>:
    x10_cb: x10cb
    canvas:
        Color:
            rgba: 0.5, 0.5, 0.5, 1
        Rectangle:
            pos: 0, 0
            size: self.size

    GridLayout:
        pos_hint: {'center_x': 0.5, 'top': 1.0}
        size_hint: None, None
        size: 50, 150
        #spacing: 4
        rows: 3
        col_force_default: True
        col_default_width: 50
        row_force_default: True
        row_default_height: 50
        ArrowButton:
            size_hint: None, None
            size: 50, 50
            text: 'Y +10'
            angle: 0
            on_press: root.handle_action('Y', 10)
        Button:
            size_hint: None, None
            size: 50, 50
            text: 'Y +1'
            on_press: root.handle_action('Y', 1)
        Button:
            size_hint: None, None
            size: 50, 50
            text: 'Y +0.1'
            on_press: root.handle_action('Y', 0.1)

    GridLayout:
        pos_hint: {'center_x': 0.5, 'bottom': 1.0}
        size_hint: None, None
        size: 50, 150
        #spacing: 4
        rows: 3
        col_force_default: True
        col_default_width: 50
        row_force_default: True
        row_default_height: 50

        Button:
            size_hint: None, None
            size: 50, 50
            text: 'Y -0.1'
            on_press: root.handle_action('Y', -0.1)
        Button:
            size_hint: None, None
            size: 50, 50
            text: 'Y -1'
            on_press: root.handle_action('Y', -1)
        ArrowButton:
            size_hint: None, None
            size: 50, 50
            text: 'Y -10'
            angle: 180
            on_press: root.handle_action('Y', -10)

    GridLayout:
        pos_hint: {'left': 1, 'center_y': 0.5}
        size_hint: None, None
        size: 150, 50
        #spacing: 4
        cols: 3
        col_force_default: True
        col_default_width: 50
        row_force_default: True
        row_default_height: 50

        ArrowButton:
            size_hint: None, None
            size: 50, 50
            text: 'X -10'
            angle: 90
            on_press: root.handle_action('X', -10)
        Button:
            size_hint: None, None
            size: 50, 50
            text: 'X -1'
            on_press: root.handle_action('X', -1)
        Button:
            size_hint: None, None
            size: 50, 50
            text: 'X -0.1'
            on_press: root.handle_action('X', -0.1)

    GridLayout:
        pos_hint: {'right': 1, 'center_y': 0.5}
        size_hint: None, None
        size: 150, 50
        #spacing: 4
        cols: 3
        col_force_default: True
        col_default_width: 50
        row_force_default: True
        row_default_height: 50

        Button:
            size_hint: None, None
            size: 50, 50
            text: 'X 0.1'
            on_press: root.handle_action('X', 0.1)
        Button:
            size_hint: None, None
            size: 50, 50
            text: 'X 1'
            on_press: root.handle_action('X', 1)
        ArrowButton:
            size_hint: None, None
            size: 50, 50
            text: 'X +10'
            angle: -90
            on_press: root.handle_action('X', 10)

    CircularButton:
        pos_hint: {'center_x': 0.5, 'center_y': 0.5}
        size_hint: None, None
        size: 50, 50
        text: 'Origin'
        on_press: root.handle_action('H', 0)

    GridLayout:
        pos_hint: {'left': 1.0, 'top': 1.0}
        size_hint: 0.2, None
        cols: 2
        CheckBox:
            id: x10cb
        Label:
            text: "x10"
            #active: True

# a template Butt of type Button
<Butt@Button>
    font_size: 16
    on_press: self.parent.parent.do_action(self.text)

<KbdWidget>:
	display: entry
    rows: 9
    padding: 2
    spacing: 2

    BoxLayout:
	    TextInput:
	    	id: entry
	    	multiline: False
	    	font_size: 16
	    	on_text_validate: self.parent.parent.handle_input(self.text)

	BoxLayout:
        Butt:
        	text: 'G'
        Butt:
        	text: 'M'
        Butt:
        	text: 'T'
        Butt:
        	text: 'F'

    BoxLayout:
        Butt:
        	text: 'X'
        Butt:
        	text: 'Y'
        Butt:
        	text: 'Z'
        Butt:
        	text: 'E'

	BoxLayout:
        Butt:
        	text: 'A'
        Butt:
        	text: 'B'
        Butt:
        	text: 'C'
        Butt:
    		text: 'D'
        Butt:
        	text: 'H'
        Butt:
        	text: 'I'
        Butt:
        	text: 'J'
        Butt:
        	text: 'K'

    BoxLayout:
        Butt:
        	text: 'L'
        Butt:
        	text: 'P'
        Butt:
        	text: 'Q'
        Butt:
        	text: 'R'
        Butt:
        	text: 'S'
        Butt:
        	text: 'U'
        Butt:
        	text: 'V'
        Butt:
        	text: 'W'

    BoxLayout:
        Butt:
            text: '1'
        Butt:
            text: '2'
        Butt:
            text: '3'
        Butt:
            text: '4'

    BoxLayout:
        Butt:
            text: '5'
        Butt:
            text: '6'
        Butt:
            text: '7'
        Butt:
            text: '8'

    BoxLayout:
        Butt:
            text: '9'
        Butt:
            text: '0'
        Butt:
            text: '.'
        Butt:
            text: '-'

    BoxLayout:
        Butt:
        	text: 'BS'
        Butt:
            text: ' '
        Butt:
        	text: 'Send'

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



