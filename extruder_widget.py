import kivy

from kivy.app import App
from kivy.properties import NumericProperty, ObjectProperty, DictProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.logger import Logger

import math

class ExtruderWidget(BoxLayout):
    bed_dg= ObjectProperty()
    hotend_dg= ObjectProperty()
    last_bed_temp= NumericProperty()
    last_hotend_temp= NumericProperty()
    curtool= NumericProperty(-1)
    temperatures= DictProperty()

    def __init__(self, **kwargs):
        super(ExtruderWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.last_bed_temp= self.app.config.getfloat('Extruder', 'last_bed_temp')
        self.last_hotend_temp= self.app.config.getfloat('Extruder', 'last_hotend_temp')
        self.temp_changed= False
        self.temp_set= False
        self.bind(temperatures=self._update_temp)
        #self.bind(on_curtool=self._on_curtool)

    def switch_active(self, instance, type, on, value):
        if on:
            if value == 'select':
                MessageBox(text='Select a temperature first!').open()
                instance.active= False
            else:
                self.set_temp(type, value)
                self.temp_changed= True
                # save temp whenever we turn it on (not saved if it is changed while already on)
                if float(value) > 0:
                    self.set_last_temp(type, value)

        else:
            self.set_temp(type, '0')
            self.temp_changed= True

    def selected_temp(self, type, temp):
        # new temp selected from dropdown
        if type == 'hotend':
            self.last_hotend_temp= float(temp)
            self.temp_set= True
            self.ids.hotend_slider.value= 0
            if self.ids.hotend_switch.active:
                # update temp
                self.set_temp(type, self.last_hotend_temp)
                self.temp_changed= True

        elif type == 'bed':
            self.last_bed_temp= float(temp)
            self.temp_set= True
            self.ids.bed_slider.value= 0
            if self.ids.bed_switch.active:
                # update temp
                self.set_temp(type, self.last_bed_temp)
                self.temp_changed= True

    def adjust_temp(self, type, value):
        if value == 'select temp' or self.temp_set:
            # if we programmaticaly set the value ignore it
            self.temp_set= False
            return

        if type == 'bed':
            self.ids.set_bed_temp.text= '{:1.1f}'.format(self.last_bed_temp + float(value))
            if self.ids.bed_switch.active:
                # update temp
                self.set_temp(type, self.ids.set_bed_temp.text)
                self.temp_changed= True
        else:
            self.ids.set_hotend_temp.text= '{:1.1f}'.format(self.last_hotend_temp + float(value))
            if self.ids.hotend_switch.active:
                # update temp
                self.set_temp(type, self.ids.set_hotend_temp.text)
                self.temp_changed= True

    def set_last_temp(self, type, value):
        if type == 'bed':
            self.last_bed_temp= float(value)
        else:
            self.last_hotend_temp= float(value)

        self.app.config.set('Extruder', 'last_{}_temp'.format(type), value)
        self.app.config.write()

    def set_temp(self, type, temp):
        ''' called when the target temp is changed '''
        if type == 'bed':
            self.app.comms.write('M140 S{0}\n'.format(str(temp)))
        elif type == 'hotend':
            self.app.comms.write('M104 S{0}\n'.format(str(temp)))

    def _update_temp(self, w, v):
        ''' called to update the temperature display'''
        if self.temp_changed:
            self.temp_changed= False
            return

        for type in v:
            temp, setpoint = v[type]
            self.ids.graph_view.update_temperature(type, temp, setpoint)

            if type == 'bed':
                if math.isinf(temp):
                    self.bed_dg.value= float('inf')
                    continue
                self.bed_dg.value= temp

                if not math.isnan(setpoint):
                    if setpoint > 0:
                        self.ids.set_bed_temp.text= str(setpoint)
                        self.bed_dg.setpoint_value= setpoint
                    else:
                        self.bed_dg.setpoint_value= float('nan')
                        if self.bed_switch.active:
                            self.bed_switch.active= False

            elif type == 'hotend0' or type == 'hotend1':
                if (self.ids.tool_t0.state == 'down' and type == 'hotend0') or (self.ids.tool_t1.state == 'down' and type == 'hotend1'):
                    if math.isinf(temp):
                        self.hotend_dg.value= float('inf')
                        continue
                    self.hotend_dg.value= temp

                    if not math.isnan(setpoint):
                        if setpoint > 0:
                            self.ids.set_hotend_temp.text= str(setpoint)
                            self.hotend_dg.setpoint_value= setpoint
                        else:
                            self.hotend_dg.setpoint_value= float('nan')
                            if self.hotend_switch.active:
                                self.hotend_switch.active= False
                else:
                    self.hotend_dg.value= float('inf')

            else:
                Logger.error('Extruder: unknown temp type - ' + type)

    def set_tool(self, t):
        self.app.comms.write('T{}\n'.format(str(t)))

    def update_length(self):
        self.app.config.set('Extruder', 'length', self.ids.extrude_length.text)
        self.app.config.write()

    def update_speed(self):
        self.app.config.set('Extruder', 'speed', self.ids.extrude_speed.text)
        self.app.config.write()

    def extrude(self):
        ''' called when the extrude button is pressed '''
        Logger.debug('Extruder: extrude {0} mm @ {1} mm/min'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))
        self.app.comms.write('G91 G0 E{0} F{1} G90\n'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))

    def reverse(self):
        ''' called when the reverse button is pressed '''
        Logger.debug('Extruder: reverse {0} mm @ {1} mm/min'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))
        self.app.comms.write('G91 G0 E-{0} F{1} G90\n'.format(self.ids.extrude_length.text, self.ids.extrude_speed.text))

    def update_buttons(self):
        self.app.comms.write("$G\n")

    def _on_curtool(self):
        self.ids.tool_t0.state= 'down' if self.curtool == 0 else 'normal'
        self.ids.tool_t1.state= 'down' if self.curtool == 1 else 'normal'

    def on_touch_down(self, touch):
        if self.ids.temps_screen.collide_point(touch.x, touch.y):
            if touch.is_double_tap:
                self.ids.temps_screen.current = 'graph' if self.ids.temps_screen.current == 'dials' else 'dials'
                return True

        return super(ExtruderWidget, self).on_touch_down(touch)

