# kivy-smoothie-host
A Smoothie host, written in Kivy for running on rpi with touch screen.

This is a work in progress

This uses python >= 3.4.3

## Goal
The goal here is to have a small touch screen host that can run a smoothie and is better than an LCD Panel, and almost as good as a host PC running pronterface.
It is not meant to be a replacement for say Octoprint whose goals are different.

An RPI with 7" touch screen is about the same price as the better LCD panels, and makes a great standalone controller for a 3D printer.

I have had a 10" linux tablet called a pengpod running my delta printer for years as the only Host, it runs a hacked version of Pronterface to make it more tolerable to use on a touch screen. However Pengpods are no longer available and there are no other linux tablets I can find. A raspberry PI with touch screen is pretty close.

I was running with the very first RPI model A, but it runs pretty slowly.
I upgraded to an RPI-3 Model B and it runs much better, so I recommend them they are only about $10 more expensive.
I suspect an RPI-2 Model B will also run pretty well.

## Usage

To select the port to connect to click the System menu and select Port, then select the serial port from the list, or for a network connection select Network...
then enter the host or ip optionally followed by the port :23 (23 is the default if not specified), eg smoothieip or 192.168.0.2:23
Once you have selected a port to connect to it is saved in the ini file, and you can then click the connect menu item to connect.

The left screen is the console and displays messages from smoothie, the right screen is a selection of panels (Modes) which can be switched to by swiping up or down
(or use the tabs to select the panel you want) you can scroll up and down by swiping up or down.

There is a status bar at the bottom left showing status, DRO and print ETA when printing.

You can select 3d printer mode or CNC mode from the Settings menu, this can affect what Panels are available amongst other minor changes.

- The Console panel has a keyboard for entering gcodes and if you touch the edit field a keyboard will pop up for typing commands (non gcodes).
- The Extruder Panel is used to control temperatures and extuder.
- The Jog Panel has the usual jog controls.
- The Macro Panel is user configurable buttons panel to control whatever you want. (Edit the `macros.ini` file)
  There is a `sample-macros.ini` just copy that to `macros.ini` and edit as appropriate to define your own macro buttons.
- The DRO Panel shows current MCS and WCS, and allows easy selection of the WCS to use, and allows setting of WCS
- The MPG Panel (in CNC mode) is a simulation of an MPG pendant, it allows control of movement via a simulated rotary knob.

There is a gcode visualizer window that shows the layers, or for CNC allows setting WPOS and moving the gantry to specific parts of the Gcode...
Click the Viewer menu item, select the file to view, then the layers can be moved up or down.
To set the WPOS as a point in the view click the set WPOS button then touch the screen and cross haors will appear and track your finger, release on the point and that point will be set as WPOS. To move the gantry to a point on the view click the move gantry button then touch and drag until you get the point and release and the gantry will move to that point.

The Kivy file browser is pretty crude and buggy. To allow it to be usable on a touch panel I had to set it so directory changes require double taps on the directory. I also do not enable the Load button unless a valid file is selected by tapping the file. This allows swiping to scroll the file lists to work reliably.

The Update System menu entry requires git to be installed and the running directory be a valid git repo pointing to github.

## Install on RPI

I use kivypi from here  http://kivypie.mitako.eu/ and the official 7" touch screen, pretty much runs out-of-the-box.
Recommended to do a sudo apt-get update and sudo apt-get upgrade.

If you do not have kivypi, but have jessie installed and just want kivy for rpi then...

    $ echo "deb http://archive.mitako.eu/ jessie main" > /etc/apt/sources.list.d/mitako.list
    $ curl -L http://archive.mitako.eu/archive-mitako.gpg.key | apt-key add -
    $ apt-get update
    $ sudo apt-get install python3-kivypie

(make sure pip3 is installed.. sudo apt-get install python3-pip)

- sudo python3 -m pip install pyserial pyserial-asyncio aiofiles
or
- pip3 install pyserial pyserial-asyncio aiofiles

Run with...

> kivy main.py

NOTE make sure the ```/home/sysop/.kivy/config.ini``` has the following set so the virtual keyboard works in a usable fashion...

    [kivy]
    keyboard_mode = systemanddock
    desktop = 0

If your config.ini is empty then here is an example that works https://gist.github.com/4f9c23c7e66f391b8c2d32c01e8a8d14


To allow the program to shutdown the RPI when the shutdown menu entry is selected you need to do the following, unless smoopi is running as root/superuser.


    Use policykit (make sure policykit-1 is installed).

    Create as root /etc/polkit-1/localauthority/50-local.d/all_all_users_to_shutdown_reboot.pkla with the 
    following content:

    [Allow all users to shutdown and reboot]
    Identity=unix-user:*
    Action=org.freedesktop.login1.power-off;org.freedesktop.login1.power-off-multiple-sessions;org.freedesktop.login1.reboot;org.freedesktop.login1.reboot-multiple-sessions
    ResultAny=yes

### Autostart Smoopi (Optional)

To autostart smoopi on boot but run as the sysop user follow these directions...

1. Install runit (sudo apt-get install runit)
2. in the sysop home directory run ```tar xvf INSTALLDIR/runit_setup.tar``` (where INSTALLDIR is where you checked out the smoopi source)
3. sudo ln -s /home/sysop/sv/smoopi /etc/service

To allow Smoopi to connect to the smoothie when auto start by runit you need to do this...
    
    sudo jove /etc/udev/rules.d/90-smoothie.rules
    and add this...

    SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666"
    SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666", SYMLINK+="smoothie%n"


smoopi is now managed by runit. (This has the side effect of restarting smoopi if it crashes).

The smoopi app will start, and will also start on boot. (To stop it you type ```sudo sv stop /etc/service/smoopi```)

### Shutdown and Startup button for Rpi (Optional)
Optionally to add a button to boot and to shutdown the rpi install a NORMALLY OPEN push button on pins 5 and 6 on the header, 
then you need to add the shutdown script to autostart... ```sudo ln -s /home/sysop/sv/shutdown /etc/service```

### Backlight on RPI
To allow Smoopi to turn on/off the backlight you need to do this...

    sudo nano /etc/udev/rules.d/backlight-permissions.rules
    and add this...
    SUBSYSTEM=="backlight",RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"

NOTE the default is for no blanking, there is a setting under the settings menu that allows you to set the timeout for blanking the screen, it is initially set to 0 which is no blanking. If it blanks then touching the screen will unblank it.

### Builtin webserver and optional video
In Settings you can turn on the webserver which will simply allow you to get current progress from any web browser, nothing fancy.
Also in Settings you can enable the video option which uses mjpg-streamer 
(which needs to be built and installed, See https://github.com/jacksonliam/mjpg-streamer.git for instructions on that). If enabled and running then the video will show up in the progress web page.

## On linux Desktop (and maybe windows/macos)

Install kivy for python3 from your distro:-

https://kivy.org/docs/installation/installation.html

1. sudo add-apt-repository ppa:kivy-team/kivy
2. sudo apt-get update
3. sudo apt-get install python3-kivy

or get the latest version of kivy if the distro version is too old (currently using  1.10.x)

    sudo pip3 install kivy


Install some dependencies we need...

    sudo pip3 install pyserial pyserial-asyncio aiofiles

Run as

    > cd kivy-smoothie-host
    > python3 main.py

## Smoothie version required

This requires the latest FirmwareBin/firmware-latest.bin from Smoothie github, (or FirmwareBin/firmware-cnc-latest.bin).

__NOTE__ to use the T0 and T1 buttons in the Extruder panel the temperature controls need to have the following designators 'T' and 'T1'. The temperature for the currently selected tool will show, and the set temp will apply to that tool.

# Screen shots
![Extruder Screen](screen1.png)
![DRO Screen](dro_mode.png)
![Command Screen](screen2.png)
![Jog Screen](screen3.png)
![Macro Screen](macro-screen.png)
![MPG Screen](mpg-mode.png)
![Gcode Viewer Screen](viewerscreen.png)

