import kivy

from kivy.app import App

from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, ObjectProperty
from kivy.app import App
from kivy.lang import Builder

#Builder.load_file('kbd.kv')

Builder.load_string('''
# a template Butt of type Button
[Butt@Button]
    # ctx.'attribute_name' is used to access the
    # attributes defined in the instance of Butt.
    text: ctx.text
    # below vars are constant for every instance of Butt
    size_hint_x: None
    width: 57.143
    on_press: self.parent.parent.do_action(ctx.text)

<KbdWidget>:
    GridLayout:
        cols: 7
        row_force_default: True
        row_default_height: 30
        #pos_hint: {'center_x':.5}
        size_hint: (None, None)
        # size is updated whenever minimum_size is.
        size: self.minimum_size
        # top is updated whenever height is.
        top: self.height

        Butt:
        	text: 'G'
        Butt:
        	text: 'M'
        Butt:
        	text: 'T'
        Butt:
        	text: 'F'
        Butt:
        	text: 'X'
        Butt:
        	text: 'Y'
        Butt:
        	text: 'Z'
        Butt:
        	text: 'A'
        Butt:
        	text: 'B'
        Butt:
        	text: 'C'
        Butt:
        	text: 'D'
        Butt:
        	text: 'E'
        Butt:
        	text: 'H'
        Butt:
        	text: 'I'
        Butt:
        	text: 'J'
        Butt:
        	text: 'K'
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
        Butt:
        	text: ' '
	    Butt:
        	text: ' '
    	Butt:
        	text: ' '
    	Butt:
        	text: ' '
        Butt:
            text: '1'
        Butt:
            text: '2'
        Butt:
            text: '3'
        Butt:
            text: '4'
        Butt:
            text: '5'
        Butt:
            text: '6'
        Butt:
            text: '7'
        Butt:
            text: '8'
        Butt:
            text: '9'
        Butt:
            text: '0'
        Butt:
            text: '.'
        Butt:
            text: '-'
        Butt:
        	text: 'BS'
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

	BoxLayout:
		orientation: 'vertical'
		padding: 1,1,0,0
		#spacing: (5, 5)

		ScrollableLabel:
			text: kbd_widget.log

		BoxLayout:
			orientation: 'vertical'
		    TextInput:
		    	id: command_input
		    	multiline: False
		    	size_hint_y: None
		    	height: self.minimum_height
		    	#pos_hint: {'x': 0, 'y': 0}
		    	text: kbd_widget.inp
		    	on_text_validate: kbd_widget.handle_input(self.text)

			KbdWidget:
				id: kbd_widget
	Widget:
''')

class ScrollableLabel(ScrollView):
    text = StringProperty('')

class KbdWidget(Widget):
	log = StringProperty()
	inp = StringProperty()
	def do_action(self, key):
		print("Key " + key)
		if key == 'Send':
			self.log += self.inp + '\n'
			self.inp= ''
		elif key == 'BS':
			self.inp= self.inp[:-1]
		else:
			self.inp += key

	def handle_input(self, s):
		self.log += s + '\n'
		self.inp= ''

class MainWindow(BoxLayout):
	pass

class KPronterfaceApp(App):
	def build(self):
		return MainWindow()

if __name__ == "__main__":
	KPronterfaceApp().run()



