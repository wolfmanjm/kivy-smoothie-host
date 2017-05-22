# kivy-smoothie-host
A Smoothie host, written in Kivy for running on rpi with touch screen.

This is a work in progress

This uses python >= 3.4.3

## Goal
The goal here is to have a small touch screen host that can run a smoothie and is better than an LCD Panel, and almost as good as a host PC running pronterface.
It is not meant to be a replacement for say Octoprint whose goals are different.

An RPI with 7" touch screen is about the same price as the better LCD panels, and makes a great standalone controller for a 3D printer.

I have had a 10" linux tablet called a pengpod running my delta printer for years as the only Host, it runs a hacked version of Pronterface to make it more tolerable to use on a touch screen. However Pengpods are no longer available and there are no other linux tablets I can find. A raspberry PI with touch screen is pretty close.

I'm was running with the very first RPI model A, but it runs pretty slowly.
I upgraded to an RPI-3 Model B and it runs much better, so I recommend them they are only about $10 more expensive.
I suspect an RPI-2 Model B will also run pretty well.

## Usage

To select the port to connect to click the System menu and select Port, then select the serial port from the list, or for a network connection select Network...
then enter the host or ip optionally followed by the port :23 (23 is the default if not specified), eg smoothieip or 192.168.0.2:23
Once you have selected a port to connect to it is ssave in the ini file, and you can then click the connect menu item to connect.

The left screen is the console and displays messages from smoothie, the right screen is a selection of panels (Modes) which can be switched to by swiping up or down
(or use the modes menu to select the panel you want) you can scroll up and down by swiping up or down.

There is a status bar at the bottom left showing status, DRO and print ETA when printing.

- The Console panel has a keyboard for entering gcodes and if you touch the edit field a keyboard will pop up for typing commands (non gcodes).
- The Extruder Panel is used to control temperatures and extuder.
- The Jog Panel has the usual jog controls.
- The Macro Panel is user configurable buttons panel to control whatever you want. (Edit the `macros.ini` file)
  There is a `sample-macros.ini` just copy that to `macros.ini` and edit as appropriate to define your own macro buttons.

There is a gcode visualizer window that shows the layers, or for CNC allows setting WPOS and moving the gantry to specific parts of the Gcode...
Click the Viewer menu item, select the file to view, then the layers can be moved up or down.
To set the WPOS as a point in the view click the set WPOS button then touch the screen and cross haors will appear and track your finger, release on the point and that point will be set as WPOS. To move the gantry to a point on the view click the move gantry button then touch and drag until you get the point and release and the gantry will move to that point.


## Install on RPI

I use kivypi from here  http://kivypie.mitako.eu/ and the official 7" touch screen, pretty much runs out-of-the-box.
Recommended to do a sudo apt-get update and sudo apt-get upgrade.

You need the latest python serial and pyserial-asyncio from here https://github.com/pyserial/pyserial-asyncio.git
(git install).

(make sure pip3 is installed.. sudo apt-get python3-pip)

- sudo python3 -m pip install --upgrade pyserial
- python3 -m pip install --user aiofiles
(or simply pip3 install pyserial aiofiles)

Install the asyncio stuff:-
(May first need to do sudo apt-get python3-setuptools)
- git clone https://github.com/pyserial/pyserial-asyncio.git
- cd pyserial-asyncio/
- python3 setup.py install --user
alternatively this may work (make sure it is at least version 0.4)...
- pip install pyserial-asyncio


Run with...

> kivy main.py

### On linux Desktop (and maybe windows/macos)

Install kivy for python3 from your distro:-

https://kivy.org/docs/installation/installation.html

1. sudo add-apt-repository ppa:kivy-team/kivy
2. sudo apt-get update
3. sudo apt-get install python3-kivy

Install pyserial which you probably already have:-
(make sure pip is installed.. sudo apt-get python3-pip)

4. sudo python3 -m pip install --upgrade pyserial

Install the asyncio stuff to a user repo :-
(May first need to do sudo apt-get python3-setuptools)
5. git clone https://github.com/pyserial/pyserial-asyncio.git
6. cd pyserial-asyncio/
7. python3 setup.py install --user

Install the aio file stuff
8. python3 -m pip install --user aiofiles

(or simply install globally `sudo pip3 install pyserial pyserial-asyncio aiofiles`)

Run as
> cd kivy-smoothie-host
> python3 main.py


# Screen shots
![Extruder Screen](screen1.png)
![Command Screen](screen2.png)
![Jog Screen](screen3.png)
![Macro Screen](macro-screen.png)
![Gcode Viewer Screen](viewerscreen.png)

