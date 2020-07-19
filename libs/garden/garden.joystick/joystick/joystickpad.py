from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, ListProperty


class JoystickPad(Widget):
    _diameter = NumericProperty(1)
    _radius = NumericProperty(1)
    _background_color = ListProperty([0, 0, 0, 1])
    _line_color = ListProperty([1, 1, 1, 1])
    _line_width = NumericProperty(1)
