from kivy.uix.scatter import Scatter
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.logger import Logger, LOG_LEVELS
from kivy.graphics import Color, Line, Scale, Translate, PopMatrix, PushMatrix, Rectangle
from kivy.graphics import InstructionGroup
from kivy.properties import NumericProperty, BooleanProperty, ListProperty
from kivy.graphics.transformation import Matrix
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel

import logging
import sys
import re
import math

Builder.load_string('''
<GcodeViewerScreen>:
    on_enter: self.parse_gcode_file(app.gcode_file, 1, True)
    on_leave: root.clear()
    BoxLayout:
        orientation: 'vertical'
        BoxLayout:
            pos_hint: {'top': 1}
            Scatter:
                id: surface
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
                        rgb: 1, 1, 1, 1
                    Rectangle:
                        size: self.size

                canvas.after:
                    ScissorPop:

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
                text: 'Z{}'.format(round(root.current_z, 1))
                size_hint_x: None
                width: self.texture_size[0]
            Button:
                text: 'First Layer'
                disabled: root.cam_mode
                on_press: root.parse_gcode_file(app.gcode_file, 1, True)
            Button:
                text: 'Prev Layer'
                disabled: root.cam_mode
                on_press: root.prev_layer()
            Button:
                text: 'Next Layer'
                disabled: root.cam_mode
                on_press: root.next_layer()
            Button:
                text: 'Clear'
                on_press: root.clear()
            ToggleButton:
                id: cam_but
                text: 'CAM mode'
                on_press: root.set_cam(self.state == 'down')
            ToggleButton:
                id: set_wpos_but
                text: 'Set WPOS'
                on_press: root.set_wcs(self.state == 'down')
            ToggleButton:
                id: move_gantry_but
                text: 'Move Gantry'
                on_press: root.move_gantry(self.state == 'down')
            Button:
                text: 'Back'
                on_press: root.manager.current = 'main'
''')

XY = 0
XZ = 1
CNC_accuracy = 0.001

class GcodeViewerScreen(Screen):
    current_z= NumericProperty(0)
    select_mode= BooleanProperty(False)
    set_wpos_mode= BooleanProperty(True)
    cam_mode= BooleanProperty(False)

    def __init__(self, comms= None, **kwargs):
        super(GcodeViewerScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.last_file_pos= None
        self.canv = InstructionGroup()
        self.ids.surface.canvas.add(self.canv)
        self.transform= self.ids.surface.transform
        self.bind(pos=self._redraw, size=self._redraw)
        self.last_target_layer= 0
        self.tx= 0
        self.ty= 0
        self.scale= 1.0
        self.comms= comms
        self.cam_mode= self.app.is_cnc
        self.rval= 0.0
        self.timer= None

    def _redraw(self, instance, value):
        self.ids.surface.canvas.remove(self.canv)
        self.ids.surface.canvas.add(self.canv)

    def clear(self):
        if self.timer:
            self.timer.cancel()
            self.timer= None

        self.is_visible= False
        self.canv.clear()

        self.last_target_layer= 0
        # reset scale and translation
        m= Matrix()
        m.identity()
        self.ids.surface.transform= m
        # not sure why we need to do this
        self.ids.surface.top= Window.height

    def next_layer(self):
        self.parse_gcode_file(self.app.gcode_file, self.last_target_layer+1, True)

    def prev_layer(self):
        n= 1 if self.last_target_layer <= 1 else self.last_target_layer-1
        self.parse_gcode_file(self.app.gcode_file, n, True)


    #----------------------------------------------------------------------
    # Return center x,y,z,r for arc motions 2,3 and set self.rval
    # Cribbed from bCNC
    #----------------------------------------------------------------------
    def motionCenter(self, gcode, plane, xyz_cur, xyz_val, ival, jval, kval= 0.0):
        if self.rval>0.0:
            if plane == XY:
                x  = xyz_cur[0]
                y  = xyz_cur[1]
                xv = xyz_val[0]
                yv = xyz_val[1]
            elif plane == XZ:
                x  = xyz_cur[0]
                y  = xyz_cur[2]
                xv = xyz_val[0]
                yv = xyz_val[2]
            else:
                x  = xyz_cur[1]
                y  = xyz_cur[2]
                xv = xyz_val[1]
                yv = xyz_val[2]

            ABx = xv-x
            ABy = yv-y
            Cx  = 0.5*(x+xv)
            Cy  = 0.5*(y+yv)
            AB  = math.sqrt(ABx**2 + ABy**2)
            try: OC  = math.sqrt(self.rval**2 - AB**2/4.0)
            except: OC = 0.0
            if gcode==2: OC = -OC  # CW
            if AB != 0.0:
                return Cx-OC*ABy/AB, Cy + OC*ABx/AB
            else:
                # Error!!!
                return x,y
        else:
            # Center
            xc = xyz_cur[0] + ival
            yc = xyz_cur[1] + jval
            zc = xyz_cur[2] + kval
            self.rval = math.sqrt(ival**2 + jval**2 + kval**2)

            if plane == XY:
                return xc,yc
            elif plane == XZ:
                return xc,zc
            else:
                return yc,zc

    extract_gcode= re.compile("(G|X|Y|Z|I|J|K|E)(-?\d*\.?\d+\.?)")
    def parse_gcode_file(self, fn, target_layer= 0, one_layer= False):
        # open file parse gcode and draw
        Logger.debug("GcodeViewerScreen: parsing file {}". format(fn))
        lastpos= [0,0,-1] # XYZ
        lastz= None
        laste= 0
        layer= 0
        last_gcode= -1
        points= []
        max_x= float('nan')
        max_y= float('nan')
        min_x= float('nan')
        min_y= float('nan')
        has_e= False
        plane= XY
        self.is_visible= True

        self.last_target_layer= target_layer

        # reset scale and translation
        m= Matrix()
        m.identity()
        self.ids.surface.transform= m

        # remove all instructions from canvas
        self.canv.clear()

        self.canv.add(PushMatrix())
        modal_g= 0
        cnt= 0
        with open(fn) as f:
            # if self.last_file_pos:
            #     # jump to last read position
            #     f.seek(self.last_file_pos)
            #     self.last_file_pos= None
            #     print('Jumped to Saved position: {}'.format(self.last_file_pos))

            for l in f:
                cnt += 1
                l = l.strip()
                if not l: continue
                if l.startswith(';'): continue
                if l.startswith('('): continue
                p= l.find(';')
                if p >= 0: l= l[:p]
                matches = self.extract_gcode.findall(l)
                if len(matches) == 0: continue

                #print(cnt, matches)
                d= dict((m[0], float(m[1])) for m in matches)

                # handle modal commands
                if 'G' not in d and ('X' in d or 'Y' in d) :
                    d['G'] = modal_g

                # G92 E0 resets E
                if 'G' in d and d['G'] == 92 and 'E' in d:
                    laste= float(d['E'])
                    has_e= True

                # only deal with G0/1/2/3
                if d['G'] > 3: continue

                modal_g= d['G']

                # TODO handle first move when lastpos is not valid yet

                # see if it is 3d printing (ie has an E axis on a G1)
                if not has_e and ('E' in d and 'G' in d and d['G'] == 1): has_e= True

                x= lastpos[0] if 'X' not in d else float(d['X'])
                y= lastpos[1] if 'Y' not in d else float(d['Y'])
                z= lastpos[2] if 'Z' not in d else float(d['Z'])
                i= 0.0 if 'I' not in d else float(d['I'])
                j= 0.0 if 'J' not in d else float(d['J'])
                self.rval= 0.0 if 'R' not in d else float(d['R'])

                e= laste if 'E' not in d else float(d['E'])

                if not self.cam_mode :
                    # handle layers (when Z changes)
                    if lastz is None:
                        # first layer
                        lastz= z
                        layer= 1

                    if z != lastz:
                        # count layers
                        layer += 1
                        lastz= z

                    # wait until we get to the requested layer
                    if layer != target_layer:
                        continue

                    if layer > target_layer and one_layer:
                        # FIXME for some reason this does not work, -- not counting layers
                        #self.last_file_pos= f.tell()
                        #print('Saved position: {}'.format(self.last_file_pos))
                        break

                    self.current_z= lastpos[2]

                # find bounding box
                if math.isnan(min_x) or x < min_x: min_x= x
                if math.isnan(min_y) or y < min_y: min_y= y
                if math.isnan(max_x) or x > max_x: max_x= x
                if math.isnan(max_y) or y > max_y: max_y= y

                gcode= d['G']

                # accumulating vertices is more efficient but we need to flush them at some point
                # Here we flush them if we encounter a new G code like G3 following G1
                if last_gcode != gcode:
                    # flush vertices
                    if points:
                        self.canv.add(Color(0, 0, 0))
                        self.canv.add(Line(points=points, width= 1, cap='none', joint='none'))
                        points= []

                last_gcode= gcode

                # in slicer generated files there is no G0 so we need a way to know when to draw, so if there is an E then draw else don't
                if gcode == 0:
                    #print("move to: {}, {}, {}".format(x, y, z))
                    # draw moves in red
                    self.canv.add(Color(1, 0, 0))
                    self.canv.add(Line(points=[lastpos[0], lastpos[1], x, y], width= 1, cap='none', joint='none'))

                elif gcode == 1:
                    if ('X' in d or 'Y' in d):
                        # for 3d printers (has_e) only draw if there is an E
                        if not has_e or 'E' in d:
                            # if a CNC gcode file or there is an E in the G1 (3d printing)
                            #print("draw to: {}, {}, {}".format(x, y, z))
                            # collect points but don't draw them yet
                            if len(points) < 2:
                                points.append(lastpos[0])
                                points.append(lastpos[1])

                            points.append(x)
                            points.append(y)

                        else:
                            # a G1 with no E, treat as G0 and draw moves in red
                            #print("move to: {}, {}, {}".format(x, y, z))
                            if points:
                                # draw accumulated points upto this point
                                self.canv.add(Color(0, 0, 0))
                                self.canv.add(Line(points=points, width= 1, cap='none', joint='none'))
                                points= []
                            # now draw the move in red
                            self.canv.add(Color(1, 0, 0))
                            self.canv.add(Line(points=[lastpos[0], lastpos[1], x, y], width= 1, cap='none', joint='none'))

                    else:
                        # A G1 with no X or Y, maybe E only move (retract) or Z move (layer change)
                        if points:
                            # draw accumulated points upto this point
                            self.canv.add(Color(0, 0, 0))
                            self.canv.add(Line(points=points, width= 1, cap='none', joint='none'))
                            points= []


                elif gcode in [2, 3]: # CW=2,CCW=3 circle
                    # code cribbed from bCNC
                    xyz= []
                    xyz.append((lastpos[0],lastpos[1],lastpos[2]))
                    uc,vc = self.motionCenter(gcode, plane, lastpos, [x,y,z], i, j)

                    if plane == XY:
                        u0 = lastpos[0]
                        v0 = lastpos[1]
                        w0 = lastpos[2]
                        u1 = x
                        v1 = y
                        w1 = z
                    elif plane == XZ:
                        u0 = lastpos[0]
                        v0 = lastpos[2]
                        w0 = lastpos[1]
                        u1 = x
                        v1 = z
                        w1 = y
                        gcode = 5-gcode # flip 2-3 when XZ plane is used
                    else:
                        u0 = lastpos[1]
                        v0 = lastpos[2]
                        w0 = lastpos[0]
                        u1 = y
                        v1 = z
                        w1 = x
                    phi0 = math.atan2(v0-vc, u0-uc)
                    phi1 = math.atan2(v1-vc, u1-uc)
                    try:
                        sagitta = 1.0-CNC_accuracy/self.rval
                    except ZeroDivisionError:
                        sagitta = 0.0
                    if sagitta>0.0:
                        df = 2.0*math.acos(sagitta)
                        df = min(df, math.pi/4.0)
                    else:
                        df = math.pi/4.0

                    if gcode==2:
                        if phi1>=phi0-1e-10: phi1 -= 2.0*math.pi
                        ws  = (w1-w0)/(phi1-phi0)
                        phi = phi0 - df
                        while phi>phi1:
                            u = uc + self.rval*math.cos(phi)
                            v = vc + self.rval*math.sin(phi)
                            w = w0 + (phi-phi0)*ws
                            phi -= df
                            if plane == XY:
                                xyz.append((u,v,w))
                            elif plane == XZ:
                                xyz.append((u,w,v))
                            else:
                                xyz.append((w,u,v))
                    else:
                        if phi1<=phi0+1e-10: phi1 += 2.0*math.pi
                        ws  = (w1-w0)/(phi1-phi0)
                        phi = phi0 + df
                        while phi<phi1:
                            u = uc + self.rval*math.cos(phi)
                            v = vc + self.rval*math.sin(phi)
                            w = w0 + (phi-phi0)*ws
                            phi += df
                            if plane == XY:
                                xyz.append((u,v,w))
                            elif plane == XZ:
                                xyz.append((u,w,v))
                            else:
                                xyz.append((w,u,v))

                    xyz.append((x,y,z))
                    # plot the points
                    points= []
                    for t in xyz:
                        x1,y1,z1 = t
                        points.append(x1)
                        points.append(y1)

                    self.canv.add(Color(0, 0, 0))
                    self.canv.add(Line(points=points, width= 1, cap='none', joint='none'))
                    points= []


                # always remember last position
                lastpos= [x, y, z]
                laste= e

        # flush any points not yet drawn
        if points:
            # draw accumulated points upto this point
            self.canv.add(Color(0, 0, 0))
            self.canv.add(Line(points=points, width= 1, cap='none', joint='none'))
            points= []

        # center the drawing and scale it
        dx= max_x-min_x
        dy= max_y-min_y
        if dx == 0 or dy == 0 :
            Logger.warning("GcodeViewerScreen: size is bad, maybe need cam mode")
            return

        dx += 4
        dy += 4
        Logger.debug("GcodeViewerScreen: dx= {}, dy= {}".format(dx, dy))

        # add in the translation to center object
        self.tx= -min_x - dx/2
        self.ty= -min_y - dy/2
        self.canv.insert(1, Translate(self.tx, self.ty))
        Logger.debug("GcodeViewerScreen: tx= {}, ty= {}".format(self.tx, self.ty))

        # scale the drawing to fit the screen
        if abs(dx) > abs(dy):
            scale= self.ids.surface.width/abs(dx)
            if abs(dy)*scale > self.ids.surface.height:
                scale *= self.ids.surface.height/(abs(dy)*scale)
        else:
            scale= self.ids.surface.height/abs(dy)
            if abs(dx)*scale > self.ids.surface.width:
                scale *= self.ids.surface.width/(abs(dx)*scale)

        Logger.debug("GcodeViewerScreen: scale= {}".format(scale))
        self.scale= scale
        self.canv.insert(1, Scale(scale))
        # translate to center of canvas
        self.offs= self.ids.surface.center
        self.canv.insert(1, Translate(self.ids.surface.center[0], self.ids.surface.center[1]))
        Logger.debug("GcodeViewerScreen: cx= {}, cy= {}".format(self.ids.surface.center[0], self.ids.surface.center[1]))
        Logger.debug("GcodeViewerScreen: sx= {}, sy= {}".format(self.ids.surface.size[0], self.ids.surface.size[1]))

        # tool position marker
        x= self.app.wpos[0]
        y= self.app.wpos[1]
        r= 10/scale
        self.canv.add(Color(1, 0, 0, mode='rgb', group="tool")),
        self.canv.add(Line(circle=(x, y, r), group="tool")),
        self.canv.add(Rectangle(pos=(x, y-r/2), size=(1/scale, r), group="tool")),
        self.canv.add(Rectangle(pos=(x-r/2, y), size=(r, 1/scale), group="tool"))

        self.canv.add(PopMatrix())

        # not sure why we need to do this
        self.ids.surface.top= Window.height

        if not self.timer: # and self.app.status == "Run":
            self.timer= Clock.schedule_interval(self.update, 0.5)

    def update(self, dt):
        if not self.is_visible: return

        # follow the tool path
        #self.canv.remove_group("tool")
        x= self.app.wpos[0]
        y= self.app.wpos[1]
        r= 10/self.scale
        g= self.canv.get_group("tool")
        g[2].circle= (x, y, r)
        g[4].pos= x, y-r/2
        g[6].pos= x-r/2, y

    def transform_pos(self, posx, posy):
        # convert touch coords to local scatter widget coords, relative to lower bottom corner
        pos= self.ids.surface.to_widget(posx, posy)
        # convert to original model coordinates (mm), need to take into account scale and translate
        wpos= ((pos[0] - self.offs[0]) / self.scale - self.tx, (pos[1] - self.offs[1]) / self.scale - self.ty)
        return wpos

    def on_touch_down(self, touch):
        #print(self.ids.surface.bbox)
        # if within the scatter and we are in select mode...
        if self.ids.surface.collide_point(touch.x, touch.y) and self.select_mode:
            pos= (touch.x, touch.y)
            ud = touch.ud
            ud['group'] = g = str(touch.uid)

            label = CoreLabel(text="{:1.3f},{:1.3f}".format(self.transform_pos(touch.x, touch.y)[0], self.transform_pos(touch.x, touch.y)[1]))
            label.refresh()
            texture= label.texture
            with self.canvas.after:
                Color(0, 0, 1, mode='rgb', group=g)
                ud['crossx'] = [
                    Rectangle(pos=(pos[0], 0), size=(1, self.height), group=g),
                    Rectangle(pos=(0, pos[1]), size=(self.width, 1), group=g),
                    Line(circle=(pos[0], pos[1], 20), group=g),
                    Rectangle(texture=texture, pos=(pos[0]-texture.size[0]/2, pos[1]-40), size=texture.size, group=g)
                ]

            touch.grab(self)
            return True

        else:
            return super(GcodeViewerScreen, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.select_mode:
            if touch.grab_current is not self:
                return

            pos= (touch.x, touch.y)
            print(self.ids.surface.to_widget(pos[0], pos[1]))
            print(self.transform_pos(pos[0], pos[1])[0], self.transform_pos(pos[0], pos[1])[1])
            ud = touch.ud
            ud['crossx'][0].pos = pos[0], 0
            ud['crossx'][1].pos = 0, pos[1]
            ud['crossx'][2].circle = (pos[0], pos[1], 20)
            label = CoreLabel(text="{:1.3f},{:1.3f}".format(self.transform_pos(pos[0], pos[1])[0], self.transform_pos(pos[0], pos[1])[1]))
            label.refresh()
            texture= label.texture
            ud['crossx'][3].texture= texture
            ud['crossx'][3].pos= pos[0]-texture.size[0]/2, pos[1]-40

        else:
            return super(GcodeViewerScreen, self).on_touch_move(touch)


    def on_touch_up(self, touch):
        if self.select_mode:
            if touch.grab_current is not self:
                return

            touch.ungrab(self)
            ud = touch.ud
            self.canvas.after.remove_group(ud['group'])
            self.select_mode= False
            self.ids.set_wpos_but.state= 'normal'
            self.ids.move_gantry_but.state= 'normal'

            # convert to original model coordinates (mm), need to take into account scale and translate
            wpos= self.transform_pos(touch.x, touch.y)
            if self.set_wpos_mode:
                if self.comms:
                    self.comms.write('G10 L20 P0 X{} Y{}'.format(wpos[0], wpos[1]))
                else:
                    print('Set WCS to: {}, {}'.format(wpos[0], wpos[1]))
                    print('G10 L20 P0 X{} Y{}'.format(wpos[0], wpos[1]))
            else:
                if self.comms:
                    self.comms.write('G0 X{} Y{}'.format(wpos[0], wpos[1]))
                else:
                    print('Move Gantry to: {}, {}'.format(wpos[0], wpos[1]))
                    print('G0 X{} Y{}'.format(wpos[0], wpos[1]))

        else:
            return super(GcodeViewerScreen, self).on_touch_up(touch)

    def move_gantry(self, on):
        self.set_wpos_mode= False
        self.select_mode= on

    def set_wcs(self, on):
        self.set_wpos_mode= True
        self.select_mode= on

    def set_cam(self, on):
        self.cam_mode= on
        self.parse_gcode_file(self.app.gcode_file, 0, True)


if __name__ == '__main__':

    Builder.load_string('''
<StartScreen>:
    on_leave: print('leaving start')
    Button:
        text: 'press me'
        on_press: root.manager.current = 'gcode'
''')

    class StartScreen(Screen):
        pass

    class GcodeViewerApp(App):
        is_cnc= BooleanProperty(False)
        wpos= ListProperty([0,0,0])
        def __init__(self, **kwargs):
            super(GcodeViewerApp, self).__init__(**kwargs)
            if len(sys.argv) > 1:
                self.gcode_file= sys.argv[1]
            else:
                self.gcode_file= 'test.gcode' #'circle-test.g'

        def build(self):
            self.sm = ScreenManager()
            self.sm.add_widget(StartScreen(name='main'))
            self.sm.add_widget(GcodeViewerScreen(name='gcode'))
            level = LOG_LEVELS.get('debug')
            Logger.setLevel(level=level)
            logging.getLogger().setLevel(logging.DEBUG)
            return self.sm

    GcodeViewerApp().run()
