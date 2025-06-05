# Smoopi a Graphical Smoothie Host for 3D printing and CNC

Github supports ToC, it is available in the top-right corner of this document.

A Smoothie host designed to run on an rpi with multitouch screen or on a desktop with a mouse and keyboard.

This is stable and ready for everyday use.

This uses python >= 3.7.x and <= 3.13.x and kivy >= 2.1.x <= 2.3

Use an RPI-3 Model B or B+, or the RPI-3 Model A+ with RPI multitouch screen. (No XWindows, but multitouch is required if there is no keyboard or mouse).
Also runs on RPI4xx and RPI5 under the current raspbian Desktop (Bookworm).
Also runs on pretty much any Linux XWindows desktop (and maybe Mac).

It will run on Windows if you install Python 3.7 (or newer), and follow the kivy instructions for installing kivy on windows. https://kivy.org/doc/stable/installation/installation-windows.html

The minimum usable resolution is 800x480. There are various layouts to suit different screen resolutions.

(See [here](INSTALL.md) for installation instructions)


## Tested touch panels
The following touch panels have been tested and work nicely:

1. Official RPI 7" touch screen. Works well with the `RPI Touch` layout 800x480
2. Waveshare 7" QLED IPS Capacitive Touch Display. Works well with the `RPI Full Screen` layout 1024x600
3. SunFounder 10.1" HDMI 1280x800 IPS LCD Touchscreen. Works well with the `Wide Desktop` layout and setting the `Touch screen` setting.
4. Official RPI 7" version 2 touch screen, which is portrait mode by default. See [RPI Touch Screen v2](RPITouchScreenV2.md)

Most HDMI/USB touch panels should also work.

## Goal
The goal is to have a small touch screen host that can run a smoothie and is better than an LCD Panel, and almost as good as a host PC running pronterface.
It is not meant to be a replacement for say Octoprint whose goals are different.
A secondary goal is to have a decent smoothie aware desktop host to replace Pronterface and bCNC, that has good support for CNC tasks as well as 3D printing. The CNC goals are to allow setting of the WCS to a point on the workpiece, and move to points on the workpiece to check for placement etc.

(*UPDATE* there are several desktop layouts that make it more usable on a regular desktop that has a larger screen, it has been tested on various linux machines but should run anywhere that python3 and kivy will run).

An RPI with 7" touch screen is about the same price as the better LCD panels, and makes a great standalone controller for a 3D printer.

## Usage

Run as ```python3 main.py``` and it MUST be run from the smoopi directory.

To select the port to connect to click the System menu and select Port, then select the serial port from the list, or for a network connection select Network...
then enter the host or ip optionally followed by the port :23 (23 is the default if not specified), eg smoothieip or 192.168.0.2:23 (NOTE network communication is not well tested).
Once you have selected a port to connect to it is saved in the ini file, and you can then click the connect menu item to connect.

The left screen is the console and displays messages from smoothie, the right screen is a selection of panels (Modes) which can be switched to using the tabs to select the panel you want, you can scroll the left screen up and down by swiping up or down.

There is a status bar at the bottom left showing status, DRO and print ETA when printing.

You can select 3d printer mode or CNC mode from the Settings menu, this can affect what Panels are available amongst other minor changes.

- The Console panel has a keyboard for entering gcodes and if you touch the edit field a keyboard will pop up for typing commands (non gcodes). If you precede the command with ! it will be sent to the linux shell instead of smoothie. Sending ? will pop up a GCode reference screen.
- The Extruder Panel is used to control temperatures and extuder. You can switch between gauge view and graph view by double clicking on the view
- The Jog Panel has the usual jog controls, plus a continuous jog mode in the middle (which can only be pushed in one direction before release).
- The Macro Panel is a user configurable buttons panel to control whatever you want. (Edit the `macros.ini` file)
  There is a `sample-macros.ini` just copy that to `macros.ini` and edit as appropriate to define your own macro buttons.
- The DRO Panel shows current MCS and WCS, and allows easy selection of the WCS to use, and allows setting of WCS. If WCS entered is ```/2``` it will halve the current position. (Usefull for moving to the center of things)
- The MPG Panel is a simulation of an MPG pendant, it allows control of movement and feedrate override via a simulated rotary knob. (There is an optional module to take controls from a real MPG USB pendant [See](README-pendants.md)).
- The config editor displays the current smoothie config in a scrollable window, values can be updated click the return key and then will update the config on sd accordingly. (reset is of course required to take effect).
- Under the Tools menu there is an entry to upload GCode files to the sdcard, and to start an sdcard based print. (don't try to upload non gcode files)
- There is a Fast Stream Tool for streaming gcode that has very small segments and stutters under normal streaming (or for raster laser engraving)

If your screen is larger than the 800x480 of the RPI touch screen there are various other layouts designed to work on bigger screens, if you also set the touch_screen setting it presumes you are running on a touch screen in full screen mode, and adds a few extra menu items to allow shutdown and also a simple text editor. There is also a screen blanking option.

There is a gcode visualizer window that shows the layers, or for CNC allows setting WPOS and moving the gantry to specific parts of the Gcode...
Click the Viewer menu item, select the file to view, then the layers can be moved up or down.
To set the WPOS to a point in the view click the select button, then touch the screen to move the crosshairs, when you have the point you want selected then click the set WPOS button, that point will be set as WPOS. To move the gantry to a point on the view click the select button, then touch and drag until you get the point and then click the move to button, the gantry will move to that point.

The Kivy file browser is pretty crude and buggy. To allow it to be usable on a touch panel I had to set it so directory changes require double taps on the directory. I also do not enable the Load button unless a valid file is selected by tapping the file. This allows swiping to scroll the file lists to work reliably. 
If running in desktop mode you can select a different native file chooser from the settings page. (You will need to install zenity or kdialog or wx for python3)

The Update System menu entry requires git to be installed and the running directory be a valid git repo pointing to github.

When running on a desktop you can jog using the keyboard up/down/left/right/pgup/pgdown keys, the default jog is 0.1mm, if ctrl key is pressed it is 0.01mm, if shift is pressed it is 1mm. pgup/pgdown move the Z axis. up/down move the Y axis and left/right move the X axis. If alt is pressed then it does a continuous jog until the key is released.

By default the screen size and position will be saved and set, however when running on egl_rpi (full screen) this is not allowed, so in this case set `screen_size` and `screen_pos` to `none` in `smoothiehost.ini` in the `[UI]` section.

### Macros
Macro buttons can be defined in the `macros.ini` file that can issue simple commands, can be toggle buttons, can be toggle buttons that monitor switches (eg fan, psu), that can issue shell commands to the host O/S, and that can run scripts on the host O/S that communicate with smoothie.
Macros buttons can prompt for input and substitute the given variables.
(See sample-macros.ini for examples).
Simple macro buttons can be created by clicking the green `New Macro` button.

If a simple macro starts with ```@``` then the following characters are a file name and that file is opened and sent to smoothie. Note that ok is not checked, so it must be a fairly small file of gcodes.

If a simple macro starts with ```?``` then a confirmation dialog will prompt before executing it.

If in CNC mode it will first check for 'macros-cnc.ini' and load that if found, otherwise it will load 'macros.ini'.
Scripts can also be executed from a macro button [see](scripts/README.md).

### CNC Support (PCB milling etc)
There are features specifically implemented to make CNC use easier.
- Tool change can be enabled which will catch Tn/M6 commands and suspend the job allowing you to manually change the drill bit and/or tool and then return to the point it was suspended. Full jogging and resetting of Z0 is allowed while suspended.
NOTE for toolchange to be caught by Smoopi the M6 must be on a line by itself or on a line and followed by at least one space, or at the end of the line...
(eg ```M6\n``` or ```T6 M6\n```)

- Cambam tool change gcode is supported if the profile is slightly modified to output Tn followed by M6 on the next line, and will show the size of the bit required in the console window.
    
      <ToolChange>{$clearance}
      T{$tool.index} {$comment} T{$tool.index} : {$tool.diameter} {$endcomment}
      M6</ToolChange>

- Flatcam gcode is supported but a minor postprocess on the gcode needs to be done so the comment showing the tool required is moved to before the M6 (it is currently after the M6 so you don't see it until after you resume).

- ```M0``` can be enabled and any (MSG, xxxx) is displayed in the console window. However M0 simply pauses the job until the dialog is dismissed. This presumes the tool heights are all the same and no jogging is required to change a tool

- The viewer allows setting the WCS to any arbitrary point on the workpiece, and to move to any point on the workpiece. This allows positioning and size checking before the job is run.

- When viewing a CNC gcode file it only displays a 'slice' (0 to -1mm) in the gcode, this is set to 1.0mm by default, and should be set to the depth of cut for the file you are viewing. (For instance if the DOC is 0.4mm then set the slice to 0.4).

-  On an RPI with limited GPU memory you can limit the number of vectors that are displayed by setting the ```[viewer] vectors=10000``` (so the display doesn't freeze). There is a bounding box though around the entire object even if some details are skipped, so WCS can still be set correctly.

### Suspend (filament change) support
M600/suspend is handled correctly, and will suspend the print until the resume button is clicked (this will send M601). A useful thing is to insert ```(MSG any message here)``` in the gcode file before the M600 which will display in the console window, it could be a prompt to change the filament to a specific color for instance.

### Notifications
EMail notifications can be sent to monitor progress by embedding a token in the gcode file. 
    
    (NOTIFY any message here)

When this is read in the gcode file an email is sent with the message.
In order to send email a file ```notify.ini``` must be created with the SMTP authentication for your email server. (GMail works fine for instance).
Look at the file ```sample-notify.ini``` and modify accordingly.

Additionally an email can optionally be sent whenever a run finishes either ok or abnormally, set the notify email option in Settings.

Note for gmail users, it is best to setup an application password and use that instead of your gmail login.

### Unexpected HALTs
If smoothie halts and goes into the alarm state for any reason (like limit hit or temperature overrun), it may be possible to restart from where it left off. After correcting the issue that caused the HALT, turn the heaters back on (and power) and then click the resume button, if you are lucky it will continue from where it left off. It is probably best to abort the print though.

### Fast Streaming
To use the fast streaming option, you must enable the second serial port on Smoothie V1 in the config. We run a separate process to fast stream to the second serial port, while the first serial port is still connected to Smoopi and can monitor the temperature etc, and Kill if needed. Progress will be displayed in the status bar as usual.
To use it we would add the following to the smoothiehost.ini (or via Settings)
(For rpi or Linux, windows it will be a COMn: port)

```fast_stream_cmd = python3 -u comms.py serial:///dev/ttyACM1 {file} -f -q```

### Multiple configs
In some cases you may be using one desktop system running Smoopi to control different machines. In this case you can create different config files (default is `smoothiehost.ini`) by running Smoopi with an extension on the command line eg ```python3 main.py mine``` in this case it will load the config from 'smoothiehost-mine.ini' instead of `smoothiehost.ini`, of course `mine` can be any extension you like.


## Smoothie version required

This *always* requires the latest versions (V1 or V2) from Smoothie github.

__NOTE__ to use the T0 and T1 buttons in the Extruder panel the temperature controls need to have the following designators 'T' and 'T1'. The temperature for the currently selected tool will show, and the set temp will apply to that tool.

## Spindle Camera
There is support for a spindle camera (or just a regular camera).
On a rpi if you are using the rpi camera you need to install a couple of extra modules...
    
    pip3 install --user picamera numpy

and remember to enable the camera in raspi-config.

To use a USB camera it should just work.

### Usage
There are various buttons in the spindle camera screen as well as a cross hair in the center.

![zero](img/set_zero.png "Zero WCS") will set the X and Y WPOS to zero at the current position

![capture](img/screenshot.png "Capture image") will create a PNG of the current camera screen in the current directory

![jog](img/cross-mouse.png "Jog Mode") Enters touch jog mode

![invert](img/invert_jog.png "Invert Jog") Inverts the jog movement

![back](img/back.png "Go Back") Exits the spindle camera window

To jog and focus you need to use multitouch on an RPI screen. Once the jog mode button is pressed one finger slid left or right will jog in the X axis by 0.001mm, two fingers will jog by 0.01mm, three fingers will jog by 0.1mm. 
Slide up and down will move in Y.
Four finger slides up/down will move the Z axis up/down to focus the camera.
NOTE that only the first finger to touch is tracked so if that is lifted it will no longer jog until all fingers are lifted. If four fingers touch then it enters z jog mode and will stay in that mode until all fingers are lifted.

If using one of the desktop layouts you will have access to the jog screen for jogging, or you can use the pendant.

## UART debug logger
When debugging configs etc it is useful to monitor the DEBUG UART output from the smoothie board, this can easily be done by ataching an FTDI to the smoothie board. However the RPI also has UART pins so you can hook the smoothie UART direct to the RPI uart without needing a FTDI.
In Smoopi under tools you select the ```Start Uart Log``` menu item and select the port (usually /dev/ttyAMA0 on RPI). Then a toggle button appears under the log view that allows you to toggle between the normal console output and the UART debug output.
On an RPI enabling the UART pins on the header is a bit tricky, you need to disable the linux console and enable the uart in raspi-config, and also in the /boot/config.txt you need to add ```dtoverlay=pi3-disable-bt``` for the UART to be enabled properly.

# Screen shots
## Extruder screens
![Extruder Screen](pics/screen1.png)
![Temp Graph](pics/temp-graph.png)
## DRO screen
![DRO Screen](pics/dro_mode.png)
## Command screen
![Command Screen](pics/screen2.png)
## Jog screen
![Jog Screen](pics/screen3.png)
## Macro screen
![Macro Screen](pics/macro-screen.png)
## MPG screen
![MPG Screen](pics/mpg-mode.png)
## Config Editor
![Config editor](pics/config-editor.png)
## GCode viewer
![Gcode Viewer Screen](pics/viewerscreen.png)
![Selection in Gcode Viewer Screen](pics/viewer-select.png)
## Settings
![Settings](pics/settings.png)
## GCode help screen
![GCode Help Screen](pics/gcode-help.png)
## Desktop mode
![Desktop Screen](pics/desktop-mode.png)
## Wide Screen Desktop mode
![Wide screen Screen](pics/wide-screen.png)

