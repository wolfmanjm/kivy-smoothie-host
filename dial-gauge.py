# -*- coding: utf-8 -*-

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label

from kivy.properties import ListProperty, NumericProperty, ObjectProperty, BooleanProperty, AliasProperty, ReferenceListProperty
from kivy.lang import Builder
from kivy.graphics import Color, Line, Translate, Rotate, PushMatrix, PopMatrix, Mesh, Scale, Rectangle
from kivy.graphics import InstructionGroup
from kivy.uix.slider import Slider
from kivy.vector import Vector
from kivy.core.text import Label as CoreLabel

Builder.load_string('''
<DialGauge>:
    id: dial_gauge

    # angle_offset: 0

    # canvas.before:
    #     Color:
    #         rgba: 1, 0, 0, 1
    #     Rectangle:
    #         pos: self.pos
    #         size: self.size

    size_hint: None, None
    size: [self.dial_diameter, (self.dial_diameter/2)+self.hub_radius] if self.semi_circle else self.dial_size

    canvas.before:
        # background dial
        Color:
            rgb: self.dial_color

        PushMatrix
        Translate:
            y: -self.dial_diameter/2+self.hub_radius if self.semi_circle else 0

        Ellipse:
            pos: self.pos
            size: self.dial_size
            angle_start: 0 if not self.semi_circle else -90
            angle_end: 360 if not self.semi_circle else 90

        PopMatrix
        Rectangle:
            pos: self.pos[0], self.pos[1]
            size: [self.dial_diameter, self.hub_radius] if self.semi_circle else [0, 0]

    canvas:
        # needle
        Color:
            rgb: self.needle_color
        PushMatrix
        Rotate:
            angle: -180+self.angle_start+self.angle_offset + ((self.angle_stop-self.angle_start) * ((self.value-self.scale_min) / (self.scale_max-self.scale_min)))
            axis: 0,0,-1 # we want clockwise rotation
            origin: self.dial_center
        Translate:
            x: self.dial_center[0]
            y: self.dial_center[1]
        Scale:
            x: dial_gauge.needle_width
            y: dial_gauge.needle_length
        Mesh:
            vertices: -1,0,0,0, -1,0.9,0,0, 0,1,0,0, 1,0.9,0,0, 1,0,0,0
            indices: 0,1,2,3,4
            mode: 'triangle_fan'
        PopMatrix

        # hub
        Color:
            rgb: self.hub_color
        Ellipse:
            pos: self.dial_center[0]-self.hub_radius, self.dial_center[1]-self.hub_radius
            size: self.hub_radius*2, self.hub_radius*2

    # Display the Value
    Label:
        text: str(int(float(dial_gauge.value))) + '°c' if dial_gauge.show_value else ''
        pos: dial_gauge.dial_center[0]-self.size[0]/2+dial_gauge.value_offset_pos[0], dial_gauge.dial_center[1]-self.size[1]/2+dial_gauge.value_offset_pos[1]
        size: self.texture_size
        font_size: dial_gauge.value_font_size
        color: dial_gauge.value_color
''')

if __name__ == '__main__':
    Builder.load_string('''
<MainView>:
    BoxLayout:
        orientation: 'vertical'
        size_hint: None, None
        size: 480, 480
        pos_hint: {'center_x': 0.5, 'top': 1.0}
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            Rectangle:
                pos: self.pos
                size: self.size

        DialGauge:
            # canvas.after:
            #     Color:
            #         rgba: 0,0,0,1
            #     Rectangle:
            #         pos: self.pos
            #         size: 4,4
            id: dg
            pos_hint: {'center_x': .5, 'top': 1.0}
            dial_diameter: 250

            # gauge properties
            scale_max: 260
            scale_min: 20
            value: self.scale_min

            # example for half temperature gauge
            scale_increment: 20
            semi_circle: True
            angle_start: 90
            angle_stop: 270
            tic_frequency: 1

            # example for full round gauge
            #scale_increment: 10
            #tic_frequency: 2
            #angle_start: 45
            #angle_stop: 315

            tic_radius: self.dial_diameter/2.0
            needle_length: self.dial_diameter/2 - self.tic_length -4 # ends just where tics start less a few pixels
            needle_width: 5
            hub_radius: 8
            dial_color: 1,1,0,1
            hub_color: 1,0,0
            needle_color: 1,0,0

            show_value: True
            value_offset_pos: 0, self.dial_diameter/4 # offset from center of dial
            value_color: [0,1,0,1]
        Label:
            text: 'test dial'
            size_hint_y: None
            size: self.texture_size
            color: 0,0,0,1
        Widget:

    Button:
        size_hint: None, None
        size: 60, 40
        pos_hint: {'left': 0, 'center_y': 0.3}
        text: 'Test'
        on_press: print(root.ids.dg.pos)

    Slider:
        size_hint: None, None
        size: 500, 40
        pos_hint: {'left': 0, 'bottom': 0}
        orientation: 'horizontal'
        min: dg.scale_min
        max: dg.scale_max
        value: dg.scale_min
        on_value: dg.value= self.value
    Label:
        size_hint: None, None
        size: 40, 40
        pos_hint: {'right': 1, 'bottom': 0}
        text: str(dg.value)

''')

class DialGauge(Widget):
    dial_diameter= NumericProperty(180)
    dial_size= ReferenceListProperty(dial_diameter, dial_diameter)
    scale_max = NumericProperty(100.0)
    scale_min = NumericProperty(0.0)
    scale_increment = NumericProperty(10.0)
    angle_start = NumericProperty(0.0)
    angle_stop = NumericProperty(360.0)
    angle_offset = NumericProperty(0.0)
    tic_frequency = NumericProperty(2.0)
    tic_length = NumericProperty(8)
    tic_width = NumericProperty(2)
    tic_radius = NumericProperty(100)
    tic_color = ListProperty([0,0,1])
    dial_color = ListProperty([1,1,1])
    needle_color = ListProperty([1,0,0])
    hub_color = ListProperty([1,0,0])
    needle_length = NumericProperty(100)
    needle_width = NumericProperty(4)
    hub_radius = NumericProperty(20)
    semi_circle = BooleanProperty(False)
    value = NumericProperty(0.0)
    value_offset_pos = ListProperty([0,0])
    show_value = BooleanProperty(True)
    value_color = ListProperty([0,0,1,1])
    value_font_size = NumericProperty(20)
    scale_font_size = NumericProperty(10)


    def __init__(self, **kwargs):
        super(DialGauge, self).__init__(**kwargs)
        self.draw_annulars()
        self.draw_ticks()
        self.bind(pos=self._redraw, size=self._redraw)

    def get_dial_center(self):
        x= self.pos[0] + self.dial_diameter / 2.
        y= self.pos[1] + self.dial_diameter / 2.
        if self.semi_circle:
            y += (-self.dial_diameter/2+self.hub_radius)

        return [x, y]

    def set_dial_center(self):
        pass

    dial_center = AliasProperty(get_dial_center, set_dial_center, bind=['size', 'pos'])

    def _redraw(self, instance, value):
        self.canvas.before.remove(self.annulars)
        self.draw_annulars()
        self.canvas.remove(self.ticks)
        self.draw_ticks()

    def draw_annulars(self):
        self.annulars = InstructionGroup()

        # draw three annulars green, orange, red
        # TODO make this configurable
        awidth= 6
        self.annulars.add(Color(0, 1, 0, 1))
        if self.semi_circle:
            self.annulars.add(PushMatrix())
            self.annulars.add(Translate(0, -self.dial_diameter/2+self.hub_radius))

        self.annulars.add(Line(ellipse=(self.pos[0]+awidth, self.pos[1]+awidth, self.dial_diameter-awidth*2, self.dial_diameter-awidth*2, -90, -50), width=awidth, cap= 'none', joint='round'))
        self.annulars.add(Color(1, 165.0/255, 0, 1))
        self.annulars.add(Line(ellipse=(self.pos[0]+awidth, self.pos[1]+awidth, self.dial_diameter-awidth*2, self.dial_diameter-awidth*2, -50, 0), width=awidth, cap= 'none', joint='round'))
        self.annulars.add(Color(1, 0, 0, 1))
        self.annulars.add(Line(ellipse=(self.pos[0]+awidth, self.pos[1]+awidth, self.dial_diameter-awidth*2, self.dial_diameter-awidth*2, 0, 94), width=awidth, cap= 'none', joint='round'))
        if self.semi_circle:
            self.annulars.add(PopMatrix())

        self.canvas.before.add(self.annulars)

    def draw_ticks(self):
        scangle= self.angle_stop-self.angle_start
        inc= scangle / ((self.scale_max-self.scale_min)/self.scale_increment)
        inc /= self.tic_frequency
        cnt= 0

        # create an instruction group so we can remove it and recall draw_ticks to update when pos or size changes
        self.ticks = InstructionGroup()

        self.ticks.add(Color(*self.tic_color))

        labi = self.scale_min
        x= -180.0+self.angle_start+self.angle_offset # start
        while x <= self.angle_stop-180+self.angle_offset :
            a= x if(x < 0.0) else x+360.0

            need_label= True
            ticlen= self.tic_length

            if(cnt % self.tic_frequency != 0):
                ticlen= self.tic_length/2
                need_label= False

            cnt += 1

            self.ticks.add(PushMatrix())
            self.ticks.add(Rotate(angle=a, axis=(0,0,-1), origin=(self.dial_center[0], self.dial_center[1])))
            self.ticks.add(Translate(0, self.tic_radius-ticlen))
            self.ticks.add(Line(points=[self.dial_center[0], self.dial_center[1], self.dial_center[0], self.dial_center[1]+ticlen], width=self.tic_width, cap='none', joint='none'))

            if need_label:
                #print("label: " + str(labi))
                #kw['font_size'] = self.tic_length * 2
                label = CoreLabel(text=str(int(round(labi))), font_size=self.scale_font_size)
                label.refresh()
                texture= label.texture
                self.ticks.add(Translate(-texture.size[0]/2, -texture.size[1]-2))
                self.ticks.add(Rectangle(texture=texture, pos=self.dial_center, size=texture.size))
                labi += self.scale_increment

            self.ticks.add(PopMatrix())
            x += inc

        self.canvas.add(self.ticks)
        #self.add_widget(Label(text='hello'))


if __name__ == '__main__':
    class MainView(FloatLayout):
        pass

    from kivy.base import runTouchApp
    runTouchApp(MainView(width=400))

