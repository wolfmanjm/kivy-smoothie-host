# Smoopi
A Smoothie host, written in Kivy for running on rpi with touch screen or on a desktop.

This is a work in progress, but is stable and ready for everyday use.

This uses python >= 3.4.3

Use an RPI-3 Model B or B+, or the RPI-3 Model A+ with RPI multitouch screen. (No XWindows)
Also runs on pretty much any Linux XWindows desktop (and maybe Mac or Windows if Kivy runs on them).

## Goal
The goal is to have a small touch screen host that can run a smoothie and is better than an LCD Panel, and almost as good as a host PC running pronterface.
It is not meant to be a replacement for say Octoprint whose goals are different.
A secondary goal is to have a decent smoothie aware desktop host to replace Pronterface and bCNC, that has good support for CNC tasks as well as 3D printing. The CNC goals are to allow setting of the WCS to a point on the workpiece, and move to points on the workpiece to check for placement etc.

(*UPDATE* there is now a desktop layout setting that makes it more usable on a regular desktop, it has been tested on various linux machines but should run anywhere that python3 and kivy will run).

An RPI with 7" touch screen is about the same price as the better LCD panels, and makes a great standalone controller for a 3D printer.

## Usage

To select the port to connect to click the System menu and select Port, then select the serial port from the list, or for a network connection select Network...
then enter the host or ip optionally followed by the port :23 (23 is the default if not specified), eg smoothieip or 192.168.0.2:23
Once you have selected a port to connect to it is saved in the ini file, and you can then click the connect menu item to connect.

The left screen is the console and displays messages from smoothie, the right screen is a selection of panels (Modes) which can be switched to using the tabs to select the panel you want, you can scroll the left screen up and down by swiping up or down.

There is a status bar at the bottom left showing status, DRO and print ETA when printing.

You can select 3d printer mode or CNC mode from the Settings menu, this can affect what Panels are available amongst other minor changes.

- The Console panel has a keyboard for entering gcodes and if you touch the edit field a keyboard will pop up for typing commands (non gcodes). If you precede the command with ! it will be sent to the linux shell instead of smoothie. Sending ? will pop up a GCode reference screen.
- The Extruder Panel is used to control temperatures and extuder. You can switch between gauge view and graph view by swiping left or right (or double click)
- The Jog Panel has the usual jog controls.
- The Macro Panel is a user configurable buttons panel to control whatever you want. (Edit the `macros.ini` file)
  There is a `sample-macros.ini` just copy that to `macros.ini` and edit as appropriate to define your own macro buttons.
- The DRO Panel shows current MCS and WCS, and allows easy selection of the WCS to use, and allows setting of WCS
- The MPG Panel is a simulation of an MPG pendant, it allows control of movement and feedrate override via a simulated rotary knob. (There is an optional module to take controls from a real MPG USB pendant).
- The config editor displays the current smoothie config in a scrollable window, values can be updated click the return key and then will update the config on sd accordingly. (reset is of course required to take effect).

There is a gcode visualizer window that shows the layers, or for CNC allows setting WPOS and moving the gantry to specific parts of the Gcode...
Click the Viewer menu item, select the file to view, then the layers can be moved up or down.
To set the WPOS to a point in the view click the select button, then touch the screen to move the crosshairs, when you have the point you want selected then click the set WPOS button, that point will be set as WPOS. To move the gantry to a point on the view click the select button, then touch and drag until you get the point and then click the move to button, the gantry will move to that point.

The Kivy file browser is pretty crude and buggy. To allow it to be usable on a touch panel I had to set it so directory changes require double taps on the directory. I also do not enable the Load button unless a valid file is selected by tapping the file. This allows swiping to scroll the file lists to work reliably. 
If running in desktop mode you can select a different native file chooser from the settings page. (You will need to install zenity or kdialog or wx for python3)

The Update System menu entry requires git to be installed and the running directory be a valid git repo pointing to github.

When running on a desktop you can jog using the keyboard up/down/left/right/pgup/pgdown keys, the default jog is 0.1mm, if ctrl key is pressed it is 0.01mm, if shift is pressed it is 1mm. pgup/pgdown move the Z axis. up/down move the Y axis and left/right move the X axis.

### Macros
Macro buttons can be defined in the `macros.ini` file that can issue simple commands, can be toggle buttons, can be toggle buttons that monitor switches (eg fan, psu), that can issue shell commands to the host O/S, and that can run scripts on the host O/S that communicate with smoothie.
Macros buttons can prompt for input and substitute the given variables.
(See sample-macros.ini for examples).
Simple macro buttons can be created by clicking the green `New Macro` button.


### CNC Support (PCB milling etc)
There are features specifically implemented to make CNC use easier.
- Tool change can be enabled which will catch Tn/M6 commands and suspend the job allowing you to manually change the drill bit and/or tool and then return to the point it was suspended. Full jogging and resetting of Z0 is allowed while suspended.
Cambam gcode is supported and will show the size of the bit required in the console window. Flatcam gcode is supported but a minor postprocess on the gcode needs to be done so the comment showing the tool required is moved to before the M6 (it is currently after the M6 so you don't see it until after you resume).
- M0 can be enabled and any (MSG, xxxx) is displayed in the console window. However M0 simply pauses the job until the dialog is dismissed. This presumes the tool heights are all thhe same and no jogging is required to change a tool
- The viewer allows setting the WCS to any arbitrary point on the workpiece, and to move to any point on the workpiece. This allows positioning and size checking before the job is run.

## Install on RPI

**NOTE** on the current image and all installs on raspbian you need to add this...

    > sudo jove /etc/udev/rules.d/90-smoothie.rules
    and add this...

    SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666"
    SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666", SYMLINK+="smoothie%n"
    ACTION=="add", SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", RUN+="/bin/stty -F /dev/ttyACM%n -echo -echoe -echok"

The last line is quite important otherwise you get a whole lot of ok's echoed back to smoothie when it opens. This does not appear to be needed on a desktop probably due to the speed it is setup vs the rpi.

### Image
For RPI  and touch screen you can just download the image which has a fully running version smoopi with autostart, blanking etc, so no need to do anything else.

Download from http://smoothieware.org/_media/bin/smoopi.img
And image it to an sdcard using for instance https://www.balena.io/etcher/

Once loaded boot into the sdcard, and then update raspbian stretch...

* login in with username pi and password raspberry
* sudo apt-get update
* sudo apt-get upgrade
* setup wifi using  ```sudo raspi-config```

smoopi is normally run on bootup, but in order to allow you to login and do the initial setup it is initially down. You will need to hook up a keyboard temporarily so you can access the login and run raspi-config etc.

Once that is done setup smoopi to run on boot by doing...
    
    > sudo rm /home/pi/sv/smoopi/down
    > sudo sv up /etc/service/smoopi

Once running use the System menu upgrade to fetch the latest smoopi. If that is successful, then quit under the System menu and smoopi will exit and then be restarted by runit.


### Rasbian/Debian Stretch on RPI

(Only tested on genuine RPI 7" multitouch screen).

Install the latest raspbian stretch lite... (No XWindows)
https://downloads.raspberrypi.org/raspbian_lite_latest

Follow these instructions if using an rpi 3 B+ and rasbian stretch...
https://kivy.org/doc/stable/installation/installation-rpi.html

But change all references to python.. to python3.. As we need kivy for python3.

For instance...

    sudo apt-get update
    sudo apt-get install libsdl2-dev libsdl2-image-dev \
       libsdl2-mixer-dev libsdl2-ttf-dev \
       pkg-config libgl1-mesa-dev libgles2-mesa-dev \
       python3-setuptools libgstreamer1.0-dev git-core \
       gstreamer1.0-plugins-{bad,base,good,ugly} \
       gstreamer1.0-{omx,alsa} python3-dev libmtdev-dev \
       xclip xsel
    sudo apt-get install python3-pip
    sudo pip3 install -U Cython==0.28.2
    sudo pip3 install --upgrade git+https://github.com/kivy/kivy.git@86b6e19

This installs a known working version of kivy, albeit an older one. Newer versions seem to be somewhat unstable. 
```git+https://github.com/kivy/kivy.git@stable``` seems to work ok too so long as it is v1.10.1.

On an rpi3b+ it seems the double tap time needs to be increased to be usable..

    # in file ~/.kivy/config.ini
    [postproc]
    double_tap_distance = 20
    double_tap_time = 400 # <-- increase this from the 200 default
    triple_tap_distance = 20
    triple_tap_time = 600 # <- and this to be > than double_tap_time

### Common setup
It is recommended to do this:- 

    > sudo apt-get update
    > sudo apt-get upgrade

Install some smoopi dependencies...

    > pip3 install pyserial pyserial-asyncio aiofiles

Install Smoopi itself

    > mkdir smoopi
    > cd smoopi
    > git clone https://github.com/wolfmanjm/kivy-smoothie-host.git .

Run with...

    > python3 main.py

NOTE make sure the ```~/.kivy/config.ini``` has the following set so the virtual keyboard works in a usable fashion on an RRI touch screen...

    [kivy]
    keyboard_mode = systemanddock
    desktop = 0

If your ```~/.kivy/config.ini``` is empty or not setup for the touch display then here is an example that works for the RPI official 7" touch screen:-
https://gist.github.com/4f9c23c7e66f391b8c2d32c01e8a8d14

To allow the program to shutdown the RPI when the shutdown menu entry is selected you need to do the following, unless smoopi is running as root/superuser.


    Use policykit (make sure policykit-1 is installed).

    Create as root /etc/polkit-1/localauthority/50-local.d/all_all_users_to_shutdown_reboot.pkla with the 
    following content:

    [Allow all users to shutdown and reboot]
    Identity=unix-user:*
    Action=org.freedesktop.login1.power-off;org.freedesktop.login1.power-off-multiple-sessions;org.freedesktop.login1.reboot;org.freedesktop.login1.reboot-multiple-sessions
    ResultAny=yes

### Autostart Smoopi (Optional)

To autostart smoopi on boot but run as the pi user follow these directions. (Assuming you are using stretch)...

1. Install runit (sudo apt-get install runit). On Raspbian Stretch also do ```sudo apt-get install runit-systemd```
2. in the /home/pi directory run ```tar xvf ./smoopi/runit-setup-stretch.tar``` (presuming you checked out the smoopi source into /home/pi/smoopi)
3. sudo ln -s /home/pi/sv/smoopi /etc/service


To allow Smoopi to connect to the smoothie when auto start by runit you need to do this...
    
    sudo jove /etc/udev/rules.d/90-smoothie.rules
    and add this...

    SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666"
    SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666", SYMLINK+="smoothie%n"
    ACTION=="add", SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", RUN+="/bin/stty -F /dev/ttyACM%n -echo -echoe -echok"

smoopi is now managed by runit. (This has the side effect of restarting smoopi if it crashes).

The smoopi app will start, and will also start on boot. (To stop it you type ```sudo sv stop /etc/service/smoopi```)

### Shutdown and Startup button for RPI (Optional)
Optionally to add a button to boot and to shutdown the rpi install a NORMALLY OPEN push button on pins 5 and 6 on the header, 
then you need to add the shutdown script to autostart... ```sudo ln -s /home/pi/sv/shutdown /etc/service```. NOTE you may need a capacitor across the button to stop noise shutting down the system.

### Backlight on RPI
To allow Smoopi to turn on/off the backlight you need to do this...

    sudo nano /etc/udev/rules.d/backlight-permissions.rules
    and add this...
    SUBSYSTEM=="backlight",RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"

NOTE the default is for no blanking, there is a setting under the settings menu that allows you to set the timeout for blanking the screen, it is initially set to 0 which is no blanking. If it blanks then touching the screen will unblank it.

### Builtin webserver and optional camera
In Settings you can turn on the webserver which will simply allow you to get current progress from any web browser, nothing fancy.
Also in Settings you can enable the video option which uses mjpg-streamer 
(which needs to be built and installed, See https://github.com/jacksonliam/mjpg-streamer.git for instructions on that). If enabled and running then the video will show up in the progress web page.
There is also a camera option in the system menu which allows a preview of the camera view, the url for this is also in the settings, and should be the url which gets a snapshot single jpeg frame from the camera.

## On linux Desktop (and maybe windows/macos)

Install kivy for python3 from your distro:-

https://kivy.org/docs/installation/installation.html

1. sudo add-apt-repository ppa:kivy-team/kivy
2. sudo apt-get update
3. sudo apt-get install python3-kivy

or get the latest version of kivy if the distro version is too old (currently using  1.10.1)

    sudo pip3 install kivy


Install some dependencies we need...

    sudo pip3 install pyserial pyserial-asyncio aiofiles

Run as

    > cd kivy-smoothie-host
    > python3 main.py

In settings set the desktop layout to 1 or 2 and restart. 1 is for smaller screens and 2 is for bigger screens.

__NOTE__ all the files are coded UTF-8 so make sure your locale (LANG=en_US.utf8 or even LANG=C.UTF-8) is set to a UTF-8 variety otherwise you will get weird errors from deep within python/kivy.

## Smoothie version required

This requires the latest FirmwareBin/firmware-latest.bin from Smoothie github, (or FirmwareBin/firmware-cnc-latest.bin).

__NOTE__ to use the T0 and T1 buttons in the Extruder panel the temperature controls need to have the following designators 'T' and 'T1'. The temperature for the currently selected tool will show, and the set temp will apply to that tool.

## Pendants
There is support for a home made MPG pendant using a Teensy as a rawhid device. Also the LHB04 Mach3 pendant.

### Home made
Project here...
* https://github.com/wolfmanjm/mpg-usb
* install as described there

Then you need to do the following on the rpi...

* sudo apt-get install libffi-dev
* sudo apt-get install libhidapi-libusb0
* git clone https://github.com/ahtn/python-easyhid
* cd python-easyhid
* sudo python3 setup.py install
* add to the smoothiehost.ini file...

     [modules]
     mpg_rawhid = 0x16C0:0x0486

* create a file /etc/udev/rules.d/49-teensy.rules and add the following...

    ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="04[789B]?", ENV{ID_MM_DEVICE_IGNORE}="1"
    ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="04[789A]?", ENV{MTP_NO_PROBE}="1"
    SUBSYSTEMS=="usb", ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="04[789ABCD]?", MODE:="0666"
    KERNEL=="ttyACM*", ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="04[789B]?", MODE:="0666"


Then you will have the MPG/Pendant controller available for jogging etc.

(NOTE you need the latest version of smoothieware dated greater than 1 October 2018 to support the $J command)

### HB04 wired  USB
Support for the wired LHB04 MACH3 USB pendant is now available.
add the following to the smoothiehost.ini file...

    [modules]
    hb04 = 0x10ce:0xeb70

The button functions can be defined in the hb04.ini file (see the sample-hb04.ini file)...

    [macros]
    # user defined macro buttons
    macro1 = G0 X20 Y20
    macro2 = G0 {axis}0
    #macro7 = 
    #macro3 = 
    #macro6 = 
    #start = 
    #rewind = 
    # predefined buttons can be overriden
    #safez = G91 G0 Z20 G90
    #origin = G90 G0 X0 Y0
    #probez = G38.3 Z-25
    #zero = G10 L20 P0 {axis}0
    #home = $H
    #spindle = M3 or M5 depending on whether spindle switch is on or off
    #half = "G90 G0 {}{}".format(axis, self.app.wpos[axis-88]/2)

Python Easyhid needs to be installed...

* sudo apt-get install libffi-dev
* sudo apt-get install libhidapi-libusb0
* git clone https://github.com/ahtn/python-easyhid
* cd python-easyhid
* sudo python3 setup.py install

then add this to ```/etc/udev/rules.d/50-HB04.rules```...

    SUBSYSTEMS=="usb", ATTRS{idVendor}=="10ce", ATTRS{idProduct}=="eb70", MODE:="0666"

Plug in the HB04 and turn it on, then run smoopi.

Many of the buttons have default actions, but can be redefined in the ```[macros]``` section of the hb04.ini file. NOTE that if ```{axis}``` appears in the macro it will be replaced by the currently selected axis.

The hard coded buttons are the step button which increases the move multiplier, and the MPG button next to it which decreases the multiplier.
at x1 each encoder click moves 0.001mm, at x10 it moves 0.01mm, at x100 it moves 0.1mm etc.

The Stop button will send a kill/halt (control X) to smoothie and the reset will send ```$X``` to unkill.

The move to origin and home buttons do as you would expect.
The ```=0``` button sets the WCS of the selected axis to 0.
The spindle button will toggle the spindle switch on and off (if one is defined)
The ```=1/2``` button will set the WCS of the currently selected axis to half the current position. (eg if WCS is set to 0 at left edge and spindle is at right edge it would set the WCS X to half the current value so then going to G0 X0 it would move the spindle to the center X position)

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

