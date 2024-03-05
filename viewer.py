from kivy.uix.scatter import Scatter
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.logger import Logger, LOG_LEVELS
from kivy.graphics import Color, Line, Scale, Translate, PopMatrix, PushMatrix, Rectangle
from kivy.graphics import InstructionGroup
from kivy.properties import NumericProperty, BooleanProperty, ListProperty, ObjectProperty
from kivy.graphics.transformation import Matrix
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.clock import Clock, mainthread
from kivy.core.text import Label as CoreLabel
from message_box import MessageBox
from input_box import InputBox

import logging
import sys
import re
import math
import time
import traceback

Builder.load_string('''
<GcodeViewerScreen>:
    on_enter: self.loading()
    on_leave: self.clear()
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgb: 0.5, 0.5, 0.5, 0.5
            Rectangle:
                size: self.size
        BoxLayout:
            id: view_window
            pos_hint: {'top': 1}
            Scatter:
                id: surface
                on_transform_with_touch: root.moved(*args)
                do_collide_after_children: True
                do_rotation: False
                canvas.before:
                    ScissorPush:
                        # without this we can see the scatter underneath the buttons in the rest of the window
                        x: self.parent.pos[0]
                        y: self.parent.pos[1]
                        width: self.parent.width
                        height: self.parent.height

                    Color:
                        rgb: (1, 1, 1, 1) if root.valid else (0,0,0,1)
                    Rectangle:
                        size: self.size

                canvas.after:
                    ScissorPop:
        Label:
            text: "{} size: {:1.4f}x{:1.4f} minz: {:1.4f} maxz: {:1.4f} {}".format(app.gcode_file, root.bounds[0], root.bounds[1], root.bounds[2], root.bounds[3], "Not all displayed" if root.too_many else "")
            size_hint_y: None
            height: self.texture_size[1]

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 40
            Label:
                canvas.before:
                    Color:
                        rgb: 0, 1, 0, 1
                    Rectangle:
                        size: self.size
                id: z_value
                text: '{}<>{}'.format(round(root.below_layer, 1), round(root.above_layer, 1)) if root.twod_mode else 'Z{}'.format(round(root.current_z, 1))
                size_hint_x: None
                width: self.texture_size[0]
            Button:
                text: 'Set slice'
                size_hint_x: None
                opacity: 1 if root.twod_mode else 0
                width: dp(80) if root.twod_mode else 0
                on_press: root.set_slice()
            Button:
                text: 'First Layer'
                on_press: root.clear(); root.loading()
            Button:
                text: 'Prev Layer'
                disabled: not root.twod_mode and len(root.layers) <= 2
                on_press: root.prev_layer()
            Button:
                text: 'Next Layer'
                on_press: root.next_layer()
            Spinner:
                text_autoupdate: True
                values: ('3D', '2D', 'Laser', 'Drill') if not app.is_cnc else ('2D', 'Laser', 'Drill', '3D')
                on_text: root.set_type(self.text)

            ToggleButton:
                id: select_mode_but
                text: 'Select'
                on_press: root.select(self.state == 'down')

            Button:
                text: 'Set WPOS'
                disabled: not root.select_mode
                on_press: root.set_wcs()
            Button:
                text: 'Move to'
                disabled: not root.select_mode
                on_press: root.move_gantry()
            Button:
                text: 'GCode'
                on_press: app.main_window._edit_text(app.gcode_file)
            Button:
                text: 'Back'
                on_press: root.manager.current = 'main'
''')

XY = 0
XZ = 1
CNC_accuracy = 0.1


class GcodeViewerScreen(Screen):
    current_z = NumericProperty(0)
    select_mode = BooleanProperty(False)
    twod_mode = BooleanProperty(False)
    laser_mode = BooleanProperty(False)
    drill_mode = BooleanProperty(False)
    valid = BooleanProperty(False)
    bounds = ListProperty([0, 0, 0, 0])
    layers = ListProperty([0])
    slice_size = NumericProperty(1.0)
    above_layer = NumericProperty(-1.0)
    below_layer = NumericProperty(0.0)
    too_many = BooleanProperty(False)

    def __init__(self, comms=None, is_standalone=False, **kwargs):
        super(GcodeViewerScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.last_file_pos = None
        self.canv = InstructionGroup()
        self.bind(pos=self._redraw, size=self._redraw)
        self.tx = 0
        self.ty = 0
        self.scale = 1.0
        self.comms = comms
        self.twod_mode = self.app.is_cnc
        self.rval = 0.0
        self.max_vectors = -1
        if not is_standalone:
            self.slice_size = self.app.config.get('Viewer', 'slice')
            self.above_layer = -self.slice_size
            self.max_vectors = self.app.config.getint('Viewer', 'vectors')

    def loading(self):
        self.valid = False
        self.li = Image(source='img/image-loading.gif')
        self.add_widget(self.li)
        self.ids.surface.canvas.remove(self.canv)
        # give loading image a chance to display
        Clock.schedule_once(self._load_file)

    def _loaded(self, ok):
        if not ok:
            mb = MessageBox(text='File not found: {} or Parse error'.format(self.app.gcode_file))
            mb.open()
            self.manager.current = 'main'

        Logger.debug("GcodeViewerScreen: in _loaded. ok: {}".format(self._loaded_ok))
        self.remove_widget(self.li)
        self.li = None
        self.ids.surface.canvas.add(self.canv)
        self.valid = self._loaded_ok
        if self._loaded_ok:
            # not sure why we need to do this
            self.ids.surface.top = Window.height
            if self.app.is_connected:
                self.app.bind(wpos=self.update_tool)

    def _load_file(self, *args):
        self._loaded_ok = False
        try:
            self.parse_gcode_file(self.app.gcode_file, True)
        except Exception as e:
            Logger.error('GcodeViewerScreen: Got Exception: {}'.format(e))
            print(traceback.format_exc())
            self._loaded(False)
        else:
            self._loaded(True)

    def _redraw(self, instance, value):
        self.ids.surface.canvas.remove(self.canv)
        self.ids.surface.canvas.add(self.canv)

    def clear(self):
        self.app.unbind(wpos=self.update_tool)

        if self.li:
            self.remove_widget(self.li)
            self.li = None

        if self.select_mode:
            self.stop_cursor(0, 0)
            self.select_mode = False
            self.ids.select_mode_but.state = 'normal'

        self.valid = False
        self.is_visible = False
        self.canv.clear()
        self.ids.surface.canvas.remove(self.canv)
        self.layers = [0]

        # reset scale and translation
        m = Matrix()
        m.identity()
        self.ids.surface.transform = m
        # not sure why we need to do this
        self.ids.surface.top = Window.height
        # reset cnc layers
        self.above_layer = -self.slice_size
        self.below_layer = 0.0

    def next_layer(self):
        if self.twod_mode:
            self.above_layer -= self.slice_size
            self.below_layer -= self.slice_size

        self.loading()

    def prev_layer(self):
        if self.twod_mode:
            self.above_layer += self.slice_size
            self.below_layer += self.slice_size
            self.loading()

        else:
            if len(self.layers) > 2:
                self.layers.pop()
                self.layers.pop()
                self.loading()

    def _set_slice(self, val):
        if val:
            try:
                self.slice_size = float(val)
                self.above_layer = -self.slice_size
                self.below_layer = 0.0
                self.loading()
            except Exception as e:
                pass

    def set_slice(self):
        o = InputBox(title='Set Slice', text='enter size in mm of slice to view', cb=self._set_slice)
        o.open()

    def do_print(self):
        self.app.main_window._start_print()

    extract_tool = re.compile(r"\(Tool: (\d+) \-\> Dia: (-?\d*\.?\d*\.?)\)")

    def read_drill_list(self, f):
        # reads a flatcam tool list
        # (TOOLS DIAMETER: )
        # (Tool: 1 -> Dia: 0.4)
        # (Tool: 2 -> Dia: 0.6)
        # (Tool: 3 -> Dia: 0.8)
        # (Tool: 4 -> Dia: 1.0)
        # (Tool: 5 -> Dia: 1.2)
        # (Tool: 6 -> Dia: 2.5)
        tt = {}
        eof = False
        while not eof:
            ln = f.readline()
            if not ln:
                break
            if ln.startswith('(TOOLS DIAMETER: )'):
                while ln:
                    ln = f.readline()
                    matches = self.extract_tool.findall(ln)
                    if not matches:
                        eof = True
                        break

                    for m in matches:
                        tt[int(m[0])] = float(m[1])

        f.seek(0)
        return tt

    extract_gcode = re.compile(r"(G|X|Y|Z|I|J|K|E|S)(-?\d*\.?\d*\.?)")

    def parse_gcode_file(self, fn, one_layer=False):
        # open file parse gcode and draw
        Logger.debug("GcodeViewerScreen: parsing file {}". format(fn))
        lastpos = [None, None, None]  # XYZ, set to initial tool position
        last_layer_z = None
        lastdeltaz = None
        laste = 0
        lasts = 1
        last_gcode = -1
        points = []
        max_x = float('nan')
        max_y = float('nan')
        min_x = float('nan')
        min_y = float('nan')
        min_z = float('nan')
        max_z = float('nan')
        has_e = False
        plane = XY
        rel_move = False
        self.is_visible = True
        drill_size = None

        if self.laser_mode:
            self.twod_mode = True  # laser mode implies 2D mode

        # reset scale and translation
        m = Matrix()
        m.identity()
        self.ids.surface.transform = m

        # remove all instructions from canvas
        self.canv.clear()

        self.canv.add(PushMatrix())
        modal_g = 0
        cnt = 0

        x = lastpos[0]
        y = lastpos[1]
        z = lastpos[2]

        point_count = 0
        with open(fn) as f:
            # if we are in drill_mode then try to read flatcams drill list
            if self.drill_mode:
                try:
                    tool_table = self.read_drill_list(f)
                except Exception as e:
                    Logger.error('GcodeViewerScreen: read_drill_list Got Exception: {}'.format(e))
                    tool_table = None

            # jump to last read position
            f.seek(self.layers[-1])
            # print('Jumped to layer position: {}'.format(f.tell()))

            got_layer = False
            while not got_layer:
                last_file_pos = f.tell()  # save the start of this line

                ln = f.readline()
                if not ln:
                    break
                Logger.debug("GcodeViewerScreen: {}".format(ln))

                cnt += 1
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith(';') or ln.startswith('#'):
                    continue
                if ln.startswith('('):
                    continue
                p = ln.find(';')
                if p >= 0:
                    ln = ln[:p]
                p = ln.find('(')
                if p >= 0:
                    p2 = ln.find(')')
                    lnt = ln[:p]
                    if p2 > 0:
                        lnt += ln[p2 + 1:]
                    ln = lnt

                # in drill mode we try to set the drill size
                if self.drill_mode:
                    # see if tool change
                    if ln.startswith('T'):
                        tool = int(ln[1])
                        if tool_table is not None and tool in tool_table:
                            drill_size = tool_table[tool]
                        else:
                            drill_size = 3.0  # default drill size

                matches = self.extract_gcode.findall(ln)

                # this handles multiple G codes on one line
                gcodes = []
                d = {}
                for m in matches:
                    if m[0] == 'G' and 'G' in d:
                        # we have another G code on the same line
                        gcodes.append(d)
                        d = {}
                    d[m[0]] = float(m[1])

                gcodes.append(d)

                for d in gcodes:
                    if not d:
                        continue

                    Logger.debug("GcodeViewerScreen: d={}".format(d))

                    # handle modal commands
                    if 'G' not in d and ('X' in d or 'Y' in d or 'Z' in d or 'S' in d):
                        d['G'] = modal_g

                    gcode = int(d['G'])

                    # G92 E0 resets E
                    if 'G' in d and gcode == 92 and 'E' in d:
                        laste = float(d['E'])
                        has_e = True

                    if 'G' in d and (gcode == 91 or gcode == 90):
                        rel_move = gcode == 91

                    # only deal with G0/1/2/3
                    if gcode > 3:
                        continue

                    modal_g = gcode

                    # see if it is 3d printing (ie has an E axis on a G1)
                    if not has_e and ('E' in d and 'G' in d and gcode == 1):
                        has_e = True

                    if rel_move:
                        # x or y maybe None if no absolute move preceded this
                        # so presume they are at 0
                        if 'X' in d:
                            if x is None:
                                x = 0
                            x += float(d['X'])
                        if 'Y' in d:
                            if y is None:
                                y = 0
                            y += float(d['Y'])
                        if z is not None:
                            if 'Z' in d:
                                z += float(d['Z'])

                    else:
                        x = lastpos[0] if 'X' not in d else float(d['X'])
                        y = lastpos[1] if 'Y' not in d else float(d['Y'])
                        z = lastpos[2] if 'Z' not in d else float(d['Z'])

                    i = 0.0 if 'I' not in d else float(d['I'])
                    j = 0.0 if 'J' not in d else float(d['J'])
                    self.rval = 0.0 if 'R' not in d else float(d['R'])

                    e = laste if 'E' not in d else float(d['E'])
                    s = lasts if 'S' not in d else float(d['S'])

                    if x is None or y is None:
                        if x is not None:
                            lastpos[0] = x
                        if y is not None:
                            lastpos[1] = y
                        if z is not None:
                            lastpos[2] = z

                        continue

                    if not self.twod_mode:
                        # handle layers (when Z changes)
                        if last_layer_z is None:
                            # start of first layer
                            last_layer_z = z

                        elif z != last_layer_z:
                            # possible new layer
                            if z < last_layer_z:
                                # this may have been preceded by a z lift or an initial setting of Z
                                # replace last one with this one as it is probably the start of the layer
                                self.layers[-1] = last_file_pos
                                Logger.debug('Replaced position: {} for layer: {}'.format(self.layers[-1], len(self.layers)))
                                last_layer_z = z

                            else:
                                last_layer_z = z
                                # remember the start of this line
                                self.layers.append(last_file_pos)
                                Logger.debug('Saved position: {} for layer: {}'.format(self.layers[-1], len(self.layers)))
                                # we are done with the layer, process it
                                got_layer = True
                                break

                        if z is not None:
                            self.current_z = z

                        if self.max_vectors > 0 and point_count > self.max_vectors:
                            # TODO make configurable, set low for rpi
                            Logger.info('GcodeViewerScreen: Too many vectors to display')
                            self.too_many = True
                            got_layer = True
                            break

                    else:
                        # find extents of entire thing
                        if math.isnan(min_x) or x < min_x:
                            min_x = x
                        if math.isnan(min_y) or y < min_y:
                            min_y = y
                        if math.isnan(max_x) or x > max_x:
                            max_x = x
                        if math.isnan(max_y) or y > max_y:
                            max_y = y
                        if z is not None:
                            if math.isnan(min_z) or z < min_z:
                                min_z = z
                            if math.isnan(max_z) or z > max_z:
                                max_z = z

                        # Logger.debug("GcodeViewerScreen: min - {} {} {} {}".format(min_x, min_y, max_x, max_y))

                        # in CNC mode we want to only see slices between a slice
                        # but as we mostly do depth first cutting we have to process everything
                        self.current_z = self.above_layer
                        if not self.drill_mode and gcode > 0 and z is not None and (z < self.above_layer or z > self.below_layer):
                            # ignore layers below or above slice
                            Logger.debug('...Ignored...')
                            last_gcode = gcode
                            lastpos = [x, y, z]
                            continue

                        if self.max_vectors > 0 and point_count > self.max_vectors:
                            Logger.info('GcodeViewerScreen: Too many vectors to display')
                            self.too_many = True
                            continue

                    Logger.debug("GcodeViewerScreen: x= {}, y= {}, z= {}, s= {}".format(x, y, z, s))

                    # find bounding box
                    if not self.twod_mode:
                        if math.isnan(min_x) or x < min_x:
                            min_x = x
                        if math.isnan(min_y) or y < min_y:
                            min_y = y
                        if math.isnan(max_x) or x > max_x:
                            max_x = x
                        if math.isnan(max_y) or y > max_y:
                            max_y = y
                        if z is not None:
                            if math.isnan(min_z) or z < min_z:
                                min_z = z
                            if math.isnan(max_z) or z > max_z:
                                max_z = z

                    # accumulating vertices is more efficient but we need to flush them at some point
                    # Here we flush them if we encounter a new G code like G3 following G1
                    if last_gcode != gcode:
                        # flush vertices
                        if points:
                            point_count += len(points) / 2
                            self.canv.add(Color(0, 0, 0))
                            self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                            points = []

                    last_gcode = gcode

                    if lastpos[0] is None or lastpos[1] is None:
                        lastpos = [x, y, z]
                        continue

                    # in slicer generated files there is no G0 so we need a way to know when to draw, so if there is an E then draw else don't
                    if gcode == 0:
                        # print("move to: {}, {}, {}".format(x, y, z))
                        # draw moves in dashed red
                        self.canv.add(Color(1, 0, 0))
                        self.canv.add(Line(points=[lastpos[0], lastpos[1], x, y], width=1, dash_offset=1, cap='none', joint='none'))

                    elif gcode == 1:
                        if ('X' in d or 'Y' in d):
                            if self.laser_mode and s <= 0.01:
                                # do not draw non cutting lines
                                if points:
                                    point_count += len(points) / 2
                                    # draw accumulated points upto this point
                                    self.canv.add(Color(0, 0, 0))
                                    self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                                    points = []

                            # for 3d printers (has_e) only draw if there is an E
                            elif not has_e or 'E' in d:
                                # if a CNC gcode file or there is an E in the G1 (3d printing)
                                # print("draw to: {}, {}, {}".format(x, y, z))
                                # collect points but don't draw them yet
                                if len(points) < 2:
                                    points.append(lastpos[0])
                                    points.append(lastpos[1])

                                points.append(x)
                                points.append(y)

                            else:
                                # a G1 with no E, treat as G0 and draw moves in red
                                # print("move to: {}, {}, {}".format(x, y, z))
                                if points:
                                    point_count += len(points) / 2
                                    # draw accumulated points upto this point
                                    self.canv.add(Color(0, 0, 0))
                                    self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                                    points = []
                                # now draw the move in red
                                self.canv.add(Color(1, 0, 0))
                                self.canv.add(Line(points=[lastpos[0], lastpos[1], x, y], width=1, cap='none', joint='none'))

                        else:
                            # A G1 with no X or Y, maybe E only move (retract) or Z move (layer change)
                            if points:
                                point_count += len(points) / 2
                                # draw accumulated points upto this point
                                self.canv.add(Color(0, 0, 0))
                                self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                                points = []

                            # if drill mode and negative Z only then it is a drill, so show a circle
                            # we use an arbitrary value of -0.5 to distinguish drill from engrave copper on PCB
                            if self.drill_mode and ('Z' in d) and (z < -0.5):
                                if drill_size is None:
                                    drill_size = 3.0

                                self.canv.add(Color(1, 0, 0))
                                self.canv.add(Line(circle=(x, y, drill_size / 2 / self.ids.surface.scale)))

                    elif gcode in [2, 3]:  # CW=2,CCW=3 circle
                        # G02 X0 Y-2 I0 J-2.0
                        mposx, mposy = (lastpos[0], lastpos[1])
                        centerX, centerY = (mposx + i, mposy + j)
                        endpointX, endpointY = (x, y)
                        clockwise = (gcode == 2)

                        sX = mposx - centerX
                        sY = mposy - centerY
                        eX = endpointX - centerX
                        eY = endpointY - centerY

                        if clockwise:
                            # Clockwise
                            angleA = math.atan2(sY, sX)
                            angleB = math.atan2(eY, eX)

                        else:
                            # Counterclockwise
                            angleB = math.atan2(sY, sX)
                            angleA = math.atan2(eY, eX)

                        if angleA <= angleB:
                            angleA += 2.0 * math.pi

                        radius = math.sqrt(sX * sX + sY * sY)
                        circle_dat = (centerX, centerY, radius, 90 - math.degrees(angleA), 90 - math.degrees(angleB), 64)
                        self.canv.add(Color(0, 0, 0))
                        self.canv.add(Line(circle=circle_dat))
                        # Logger.debug("GcodeViewerScreen: Circle {}".format(circle_dat))
                        # FIXME this gets out of hand for large radius arcs that are only partial arcs
                        # max_x = max(centerX + radius, max_x)
                        # min_x = min(centerX - radius, min_x)
                        # max_y = max(centerY + radius, max_y)
                        # min_y = min(centerY - radius, min_y)
                        point_count += 4

                    # always remember last position
                    lastpos = [x, y, z]
                    laste = e
                    lasts = s

                if max_x == min_x and max_y == min_y:
                    got_layer = False
                    Logger.debug("GcodeViewerScreen: no geometry found try next line")

        if not self.twod_mode and last_layer_z is None:
            # we hit the end of file before finding the layer we want
            Logger.info("GcodeViewerScreen: no layer found - last layer was at {}".format(lastpos[2]))
            return

        # flush any points not yet drawn
        if points:
            point_count += len(points) / 2
            # draw accumulated points upto this point
            self.canv.add(Color(0, 0, 0))
            self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
            points = []

        Logger.debug("GcodeViewerScreen: point count= {}".format(point_count))

        # center the drawing and scale it
        dx = max_x - min_x
        dy = max_y - min_y
        self.bounds = [dx, dy, min_z, max_z]

        if not self.twod_mode:
            if dx == 0 or dy == 0:
                Logger.warning("GcodeViewerScreen: size is bad, maybe need 2D mode")
                return

        dx += 4
        dy += 4
        Logger.debug("GcodeViewerScreen: dx= {}, dy= {}".format(dx, dy))

        # add in the translation to center object
        self.tx = -min_x - dx / 2
        self.ty = -min_y - dy / 2
        self.canv.insert(1, Translate(self.tx, self.ty))
        Logger.debug("GcodeViewerScreen: tx= {}, ty= {}".format(self.tx, self.ty))

        # scale the drawing to fit the screen
        if abs(dx) > abs(dy):
            scale = self.ids.surface.width / abs(dx)
            if abs(dy) * scale > self.ids.surface.height:
                scale *= self.ids.surface.height / (abs(dy) * scale)
        else:
            scale = self.ids.surface.height / abs(dy)
            if abs(dx) * scale > self.ids.surface.width:
                scale *= self.ids.surface.width / (abs(dx) * scale)

        Logger.debug("GcodeViewerScreen: scale= {}".format(scale))
        self.scale = scale
        self.canv.insert(1, Scale(scale, scale, 1.0))
        # translate to center of canvas
        self.offs = self.ids.surface.center
        self.canv.insert(1, Translate(self.ids.surface.center[0], self.ids.surface.center[1]))
        Logger.debug("GcodeViewerScreen: cx= {}, cy= {}".format(self.ids.surface.center[0], self.ids.surface.center[1]))
        Logger.debug("GcodeViewerScreen: sx= {}, sy= {}".format(self.ids.surface.size[0], self.ids.surface.size[1]))

        # axis Markers
        self.canv.add(Color(0, 1, 0, mode='rgb'))
        self.canv.add(Line(points=[0, -10, 0, self.ids.surface.height / scale], width=1, cap='none', joint='none'))
        self.canv.add(Line(points=[-10, 0, self.ids.surface.width / scale, 0], width=1, cap='none', joint='none'))

        # center of extents marker
        cex = (max_x + min_x) / 2
        cey = (max_y + min_y) / 2
        cer = (5.0 / self.ids.surface.scale) / scale
        self.canv.add(Color(1, 0, 0, mode='rgb'))
        self.canv.add(Line(circle=(cex, cey, cer)))
        self.canv.add(Line(points=[cex - cer, cey, cex + cer, cey], width=1, cap='none', joint='none'))
        self.canv.add(Line(points=[cex, cey - cer, cex, cey + cer], width=1, cap='none', joint='none'))

        # extents
        if self.twod_mode:
            self.canv.add(Color(1, 0, 1, mode='rgb'))
            self.canv.add(Line(points=[min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y, min_x, min_y], width=1, cap='none', joint='none'))

        # tool position marker
        if self.app.is_connected:
            x = self.app.wpos[0]
            y = self.app.wpos[1]
            r = (10.0 / self.ids.surface.scale) / scale
            self.canv.add(Color(1, 0, 0, mode='rgb', group="tool"))
            self.canv.add(Line(circle=(x, y, r), group="tool"))

        # self.canv.add(Rectangle(pos=(x, y-r/2), size=(1/scale, r), group="tool"))
        # self.canv.add(Rectangle(pos=(x-r/2, y), size=(r, 1/scale), group="tool"))

        self.canv.add(PopMatrix())
        self._loaded_ok = True
        Logger.debug("GcodeViewerScreen: done loading")
        Logger.debug("GcodeViewerScreen: bounds {}x{}".format(self.bounds[0], self.bounds[1]))

    def update_tool(self, i, v):
        if not self.is_visible or not self.app.is_connected:
            return

        # follow the tool path
        # self.canv.remove_group("tool")
        x = v[0]
        y = v[1]
        r = (10.0 / self.ids.surface.scale) / self.scale
        g = self.canv.get_group("tool")
        if g:
            g[2].circle = (x, y, r)
            # g[4].pos= x, y-r/2
            # g[6].pos= x-r/2, y

    def transform_to_wpos(self, posx, posy):
        ''' convert touch coords to local scatter widget coords, relative to lower bottom corner '''
        pos = self.ids.surface.to_widget(posx, posy)
        # convert to original model coordinates (mm), need to take into account scale and translate
        wpos = ((pos[0] - self.offs[0]) / self.scale - self.tx, (pos[1] - self.offs[1]) / self.scale - self.ty)
        return wpos

    def transform_to_spos(self, posx, posy):
        ''' inverse transform of model coordinates to scatter coordinates '''
        pos = ((((posx + self.tx) * self.scale) + self.offs[0]), (((posy + self.ty) * self.scale) + self.offs[1]))
        spos = self.ids.surface.to_window(*pos)
        # print("pos= {}, spos= {}".format(pos, spos))
        return spos

    def moved(self, w, touch):
        # we scaled or moved the scatter so need to reposition cursor
        # TODO it would be nice if the cursor stayed where it was relative to the model during a move or scale
        # NOTE right now we can't move or scale while cursor is on
        # if self.select_mode:
        #     x, y= (self.crossx[0].pos[0], self.crossx[1].pos[1])
        #     self.stop_cursor(x, y)
        #     self.start_cursor(x, y)

        # hide tool marker
        self.canv.remove_group('tool')

    def start_cursor(self, x, y):
        tx, ty = self.transform_to_wpos(x, y)
        label = CoreLabel(text="{:1.2f},{:1.2f}".format(tx, ty))
        label.refresh()
        texture = label.texture
        px, py = (x, y)
        with self.ids.surface.canvas.after:
            Color(0, 0, 1, mode='rgb', group='cursor_group')
            self.crossx = [
                Rectangle(pos=(px, 0), size=(1, self.height), group='cursor_group'),
                Rectangle(pos=(0, py), size=(self.width, 1), group='cursor_group'),
                Line(circle=(px, py, 20), group='cursor_group'),
                Rectangle(texture=texture, pos=(px - texture.size[0] / 2, py - 40), size=texture.size, group='cursor_group')
            ]

    def move_cursor_by(self, dx, dy):
        x, y = (self.crossx[0].pos[0] + dx, self.crossx[1].pos[1] + dy)

        self.crossx[0].pos = x, 0
        self.crossx[1].pos = 0, y
        self.crossx[2].circle = (x, y, 20)
        tx, ty = self.transform_to_wpos(x, y)
        label = CoreLabel(text="{:1.2f},{:1.2f}".format(tx, ty))
        label.refresh()
        texture = label.texture
        self.crossx[3].texture = texture
        self.crossx[3].pos = x - texture.size[0] / 2, y - 40

    def stop_cursor(self, x=0, y=0):
        self.ids.surface.canvas.after.remove_group('cursor_group')
        self.crossx = None

    def on_touch_down(self, touch):
        # print(self.ids.surface.bbox)
        if self.ids.view_window.collide_point(touch.x, touch.y):
            # if within the scatter window
            if self.select_mode:
                touch.grab(self)
                return True

            elif touch.is_mouse_scrolling:
                # Allow mouse scroll wheel to zoom in/out
                if touch.button == 'scrolldown':
                    # zoom in
                    if self.ids.surface.scale < 100:
                        rescale = 1.1
                        self.ids.surface.apply_transform(Matrix().scale(rescale, rescale, rescale), post_multiply=True, anchor=self.ids.surface.to_widget(*touch.pos))

                elif touch.button == 'scrollup':
                    # zoom out
                    if self.ids.surface.scale > 0.01:
                        rescale = 0.8
                        self.ids.surface.apply_transform(Matrix().scale(rescale, rescale, rescale), post_multiply=True, anchor=self.ids.surface.to_widget(*touch.pos))

                self.moved(None, touch)
                return True

        return super(GcodeViewerScreen, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.select_mode:
            if touch.grab_current is not self:
                return False

            dx = touch.dpos[0]
            dy = touch.dpos[1]
            self.move_cursor_by(dx, dy)
            return True

        else:
            return super(GcodeViewerScreen, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True

        return super(GcodeViewerScreen, self).on_touch_up(touch)

    def select(self, on):
        if not on and self.select_mode:
            self.stop_cursor()
            self.select_mode = False
        elif on and not self.select_mode:
            x, y = self.center
            self.start_cursor(x, y)
            self.select_mode = True

    def move_gantry(self):
        if not self.select_mode:
            return

        self.select_mode = False
        self.ids.select_mode_but.state = 'normal'

        # convert to original model coordinates (mm), need to take into account scale and translate
        x, y = (self.crossx[0].pos[0], self.crossx[1].pos[1])
        self.stop_cursor(x, y)
        wpos = self.transform_to_wpos(x, y)

        if self.comms:
            self.comms.write('G0 X{:1.2f} Y{:1.2f}\n'.format(wpos[0], wpos[1]))
        else:
            print('Move Gantry to: {:1.2f}, {:1.2f}'.format(wpos[0], wpos[1]))
            print('G0 X{:1.2f} Y{:1.2f}'.format(wpos[0], wpos[1]))

    def set_wcs(self):
        if not self.select_mode:
            return

        self.select_mode = False
        self.ids.select_mode_but.state = 'normal'

        # convert to original model coordinates (mm), need to take into account scale and translate
        x, y = (self.crossx[0].pos[0], self.crossx[1].pos[1])
        self.stop_cursor(x, y)
        wpos = self.transform_to_wpos(x, y)
        if self.comms:
            self.comms.write('G10 L20 P0 X{:1.2f} Y{:1.2f}\n'.format(wpos[0], wpos[1]))
        else:
            print('Set WCS to: {:1.2f}, {:1.2f}'.format(wpos[0], wpos[1]))
            print('G10 L20 P0 X{:1.2f} Y{:1.2f}'.format(wpos[0], wpos[1]))

    def set_type(self, t):
        if t == '3D':
            self.twod_mode = False
            self.laser_mode = False
            self.drill_mode = False
        elif t == '2D':
            self.twod_mode = True
            self.laser_mode = False
            self.drill_mode = False
        elif t == 'Laser':
            self.twod_mode = True
            self.laser_mode = True
            self.drill_mode = False
        elif t == 'Drill':
            self.twod_mode = True
            self.laser_mode = False
            self.drill_mode = True

        self.layers = [0]
        self.clear()
        self.loading()


if __name__ == '__main__':

    Builder.load_string('''
<StartScreen>:
    Button:
        text: 'Quit'
        on_press: app.stop()
<ExitScreen>:
    on_enter: app.stop()
''')

    class StartScreen(Screen):
        pass

    class ExitScreen(Screen):
        pass

    class SimpleConfig():
        def get(self, key):
            return "1.0"

    class GcodeViewerApp(App):
        is_connected = BooleanProperty(False)
        is_desktop = NumericProperty(3)
        wpos = ListProperty([0, 0, 0])
        is_touch = BooleanProperty(False)

        def __init__(self, **kwargs):
            super(GcodeViewerApp, self).__init__(**kwargs)
            self.is_cnc = False
            if len(sys.argv) > 1:
                self.gcode_file = sys.argv[1]
                if not self.gcode_file.endswith('.gcode'):
                    self.is_cnc = True
            else:
                self.gcode_file = 'test.gcode'  # 'circle-test.g'

        def build(self):
            Window.size = (1024, 768)
            self.sm = ScreenManager()
            self.sm.add_widget(StartScreen(name='start'))
            self.sm.add_widget(GcodeViewerScreen(name='gcode', is_standalone=True))
            self.sm.add_widget(ExitScreen(name='main'))
            self.sm.current = 'gcode'

            level = LOG_LEVELS.get('debug') if len(sys.argv) > 2 else LOG_LEVELS.get('info')
            Logger.setLevel(level=level)
            logging.getLogger().setLevel(level)
            return self.sm

    GcodeViewerApp().run()
