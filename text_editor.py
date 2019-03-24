
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import BooleanProperty

Builder.load_string('''
<Row@BoxLayout>:
    value: ''
    index: 0
    ro: True
    TextInput:
        text: root.value
        multiline: False
        readonly: root.ro
        idx: root.index
        on_text_validate: root.parent.parent.parent.parent.save_change(root.index, self.text)
        on_focus: root.parent.parent.parent.parent.got_focus(root.index)

<TextEditor>:
    rv: rv
    BoxLayout:
        canvas:
            Color:
                rgba: 0.3, 0.3, 0.3, 1
            Rectangle:
                size: self.size
                pos: self.pos
        rv: rv
        orientation: 'vertical'
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(8)
            spacing: dp(16)
            Button:
                text: 'Close'
                on_press: root.close()
            ToggleButton:
                text: 'Editable' if root.editable else "Readonly"
                on_press: root.set_edit()
            Button:
                text: 'Insert Line'
                on_press: root.insert()
                disabled: not root.editable
            Button:
                text: 'Save'
                on_press: root.save()
                disabled: not root.editable

        RecycleView:
            id: rv
            scroll_type: ['bars', 'content']
            scroll_wheel_distance: dp(114)
            bar_width: dp(10)
            viewclass: 'Row'
            RecycleBoxLayout:
                default_size: None, dp(32)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
''')

class TextEditor(Screen):
    editable= BooleanProperty(False)

    def open(self, fn):
        cnt= 0
        with open(fn) as f:
            for line in f:
                self.rv.data.append({'value': line.rstrip(), 'index': cnt, 'ro': True})
                cnt += 1

    def close(self):
        self.rv.data= []
        self.manager.current = 'main'

    def save(self):
        if self.editable:
            # rename old file to .bak
            for l in self.rv.data:
                # writeout file
                print(l)

    def got_focus(self, i):
        print("Got focus: {}".format(i))

    def insert(self):
        #get position at top center of RecycleView (upper limit)
        pos = self.rv.to_local(self.rv.center_x, self.rv.height)
        #check which items collides with the given position
        i= self.rv.layout_manager.get_view_index_at(pos)
        # TODO now see which line is selected and insert before that
        self.rv.data.insert(i, {'value': "new line", 'index': i, 'ro': False})
        # we need to renumber all following lines
        cnt= len(self.rv.data)
        for j in range(i+1, cnt):
            self.rv.data[j]['index'] = j

    def set_edit(self):
        self.editable= not self.editable
        for l in self.rv.data:
            l['ro']= not self.editable
        self.rv.refresh_from_data()

    def save_change(self, k, v):
        #print("line {} changed to {}\n".format(k, v))
        if self.editable:
            self.rv.data[k]['value']= v
            self.rv.refresh_from_data()
