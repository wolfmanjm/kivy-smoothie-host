from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ListProperty
from kivy.lang import Builder
from libs.graph import Graph, MeshLinePlot
from kivy.utils import get_color_from_hex as rgb

import math
import time

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
        precision: '%.0f' # axis label formatting
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
    def __init__(self, **kwargs):
        super(GraphView, self).__init__(**kwargs)
        self.he1_plot= None
        self.he1sp_plot= None
        self.bed_plot= None
        self.bedsp_plot= None
        self.secs= 0
        self.maxsecs= None
        self.last_time= None

    def start(self):
        pass

    def stop(self):
        pass

    def update_temperature(self, heater, temp, setpoint):
        if self.maxsecs is None:
            self.maxsecs= self.ids.graph.xmax*60.

        if heater == 'hotend0':
            if math.isinf(temp):
                if self.he1_plot is not None:
                    self.ids.graph.remove_plot(self.he1_plot)
                    self.he1_plot.points= []
                    self.he1_plot= None
                return

            if self.he1_plot is None:
                self.he1_plot = MeshLinePlot(color=(1,0,0))
                self.ids.graph.add_plot(self.he1_plot)

            self.he1_plot.points.append((self.secs/60., temp))
            # truncate points
            if len(self.he1_plot.points) > self.maxsecs:
                del(self.he1_plot.points[0])

            # now draw in setpoint if set
            if not math.isnan(setpoint) and setpoint > 0:
                if self.he1sp_plot is None:
                    self.he1sp_plot = MeshLinePlot(color=(1,1,0))
                    self.ids.graph.add_plot(self.he1sp_plot)
                self.he1sp_plot.points.append((self.secs/60., setpoint))
                # truncate points
                if len(self.he1sp_plot.points) > self.maxsecs:
                    del(self.he1sp_plot.points[0])
            else:
                if self.he1sp_plot is not None:
                    self.ids.graph.remove_plot(self.he1sp_plot)
                    self.he1sp_plot.points= []
                    self.he1sp_plot= None

        elif heater == 'bed':
            if math.isinf(temp):
                if self.bed_plot is not None:
                    self.ids.graph.remove_plot(self.bed_plot)
                    self.bed_plot.points= []
                    self.bed_plot= None
                return

            if self.bed_plot is None:
                self.bed_plot = MeshLinePlot(color=(0,1,0))
                self.ids.graph.add_plot(self.bed_plot)

            self.bed_plot.points.append((self.secs/60., temp))

            if len(self.bed_plot.points) > self.maxsecs:
                del(self.bed_plot.points[0])

            if not math.isnan(setpoint) and setpoint > 0:
                if self.bedsp_plot is None:
                    self.bedsp_plot = MeshLinePlot(color=(0,1,1))
                    self.ids.graph.add_plot(self.bedsp_plot)
                self.bedsp_plot.points.append((self.secs/60., setpoint))
                # truncate points
                if len(self.bedsp_plot.points) > self.maxsecs:
                    del(self.bedsp_plot.points[0])
            else:
                if self.bedsp_plot is not None:
                    self.ids.graph.remove_plot(self.bedsp_plot)
                    self.bedsp_plot.points= []
                    self.bedsp_plot= None

        # get elapsed time since last one
        ts= time.time()
        if self.last_time is None:
            self.last_time= ts
        else:
            self.secs += ts-self.last_time
            self.last_time= ts

        if self.secs/60. > self.ids.graph.xmax:
            self.ids.graph.xmin += 1.
            self.ids.graph.xmax += 1.

    # TODO if disconnected clear plots and reset secs
    # TODO add he2

