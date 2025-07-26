RPITouchScreenV2
----------------

To run with an RPI5 (or probably any RPI with Bookworm Desktop)...

Set kivy to run in full screen mode by editing ~/.kivy/config.ini and set these settings

    [graphics]
    fullscreen = auto
    show_cursor = 0
    borderless = 1
    resizable = 0

If in Landscape use...

    [input]
    mtdev_%(name)s = probesysfs,provider=mtdev,param=rotation=270,param=invert_x=1

If in Portrait use...

    [input]
    mtdev_%(name)s = probesysfs,provider=mtdev

The [input] setting enables the multitouch and changes its orientation correctly

The follow settings are required to run in Landscape mode which is the best orientation for Smoopi to run in.

## To run in Landscape mode then follow these directions...

First switch Wayland/X to Landscape [See](https://www.raspberrypi.com/documentation/accessories/touch-display-2.html#change-screen-orientation)

    select Screen Configuration from the Preferences menu.
    Right-click on the touch display rectangle (likely DSI-1) in the layout editor,
    select Orientation, then pick right

In smoopi edit the smoothiehost.ini and set

    [UI]
    display_type = Small Desktop
    touch_screen = 1

or click settings when smoopi is running and select Desktop Layout to Small Desktop, the touch screen setting needs to be edited in though.

The run Smoothie with the following line...

    KIVY_METRICS_DENSITY=1.2 ~/smoopivenv/bin/python main.py

This makes everything a little bit bigger otherwise the buttons and text are tiny. YMMV if you have good eyes.

## To run in portrait mode (the default for this screen)

In smoopi edit the smoothiehost.ini and set

    [UI]
    display_type = Portrait Desktop
    touch_screen = 1

Then run Smoothie with the following line...

    KIVY_METRICS_DENSITY=1.2 ~/smoopivenv/bin/python main.py


