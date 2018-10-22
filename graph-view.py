from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ListProperty, DictProperty
from kivy.lang import Builder
from libs.graph import Graph, MeshLinePlot
from kivy.utils import get_color_from_hex as rgb
from kivy.clock import Clock

import math

Builder.load_string('''
#:import rgb kivy.utils.get_color_from_hex
<GraphView>:
    Graph:
        id: graph
        label_options: { 'color': rgb('444444'),  'bold': True } # color of tick labels and titles
        background_color: (0, 0, 0, 1)  # back ground color of canvas
        tick_color: (0,0,1, 1)  # ticks and grid
        border_color: (0,1,1, 1)  # border drawn around each graph
        font_size: '8sp'
        precision: '%.1f' # axis label formatting
        # xlabel: 'Time (Mins)'
        # ylabel: 'Temp °C'
        x_ticks_minor: 1
        x_ticks_major: 1
        #y_ticks_minor: 10
        y_ticks_major: 50
        y_grid_label: True
        x_grid_label: True
        y_ticks_angle: 90
        padding: 5
        xlog: False
        ylog: False
        x_grid: False
        y_grid: False
        xmin: 0
        xmax: 5
        ymin: 10
        ymax: 300
''')

class GraphView(FloatLayout):
    values= DictProperty()

    def __init__(self, **kwargs):
        super(GraphView, self).__init__(**kwargs)
        self.he1_plot= None
        self.he2_plot= None
        self.bed_plot= None
        self.secs= 0
        self.clk= None

    def start(self):
        if self.clk is None:
            self.clk= Clock.schedule_interval(self.update_points, 1)


    def stop(self):
        # if self.clk:
        #     self.clk.cancel()
        #     self.clk= None
        pass

    def update_points(self, *args):
        if 'hotend0' not in self.values or math.isnan(self.values['hotend0'][1]) or self.values['hotend0'][1] == 0:
            if self.he1_plot is not None:
                self.he1_plot.points= []
                self.ids.graph.remove_plot(self.he1_plot)
                self.he1_plot= None
        else:
            if self.he1_plot is None:
                self.he1_plot = MeshLinePlot(color=(1,0,0))
                self.ids.graph.add_plot(self.he1_plot)

        if 'bed' not in self.values or math.isnan(self.values['bed'][1]) or self.values['bed'][1] == 0:
            if self.bed_plot is not None:
                self.bed_plot.points= []
                self.ids.graph.remove_plot(self.bed_plot)
                self.bed_plot= None
        else:
            if self.bed_plot is None:
                self.bed_plot = MeshLinePlot(color=(0,1,0))
                self.ids.graph.add_plot(self.bed_plot)

        if self.he1_plot is None:
            return

        if len(self.he1_plot.points) > 300: # 5 minutes
            del(self.he1_plot.points[0])
            del(self.bed_plot.points[0])
            self.ids.graph.xmin += 1/60.
            self.ids.graph.xmax += 1/60.

        self.he1_plot.points.append((self.secs/60., self.temp))
        self.temp += 2
        if self.temp > 200:
            self.temp= 200

        self.bed_plot.points.append((self.secs/60., self.temp/2.))

        self.secs += 1


    # TODO add set points
    # TODO add he2
    # TODO customize x axis label to round mins
