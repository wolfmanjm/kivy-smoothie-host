# Pendant README
Supported pendants are documented here.

## Pendants
There is support for a home made MPG pendant using a Teensy as a rawhid device. Also the LHB04 Mach3 pendant and the WHB04B (wired and wireless)

### Home made
Project here...
* https://github.com/wolfmanjm/mpg-usb
* install as described there

Then you need to do the following on the rpi...

* sudo apt-get install libffi-dev
* sudo apt-get install libhidapi-libusb0 libhidapi-hidraw0
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

### HB04 wired USB (old one)
Support for the wired LHB04 MACH3 USB pendant is available.
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
    #rewind = 
    # predefined buttons can be overriden
    #start = runs last file viewed or run
    #safez = G91 G0 Z20 G90
    #origin = G90 G0 X0 Y0
    #probez = G38.3 Z-25
    #zero = G10 L20 P0 {axis}0
    #home = $H
    #spindle = M3 or M5 depending on whether spindle switch is on or off
    #half = "G90 G0 {}{}".format(axis, self.app.wpos[axis-88]/2)

Python Easyhid needs to be installed...

* sudo apt-get install libffi-dev
* sudo apt-get install libhidapi-libusb0 libhidapi-hidraw0
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

### WHB04B wired or wireless with USB dongle
Support for the wired and wireless WHB04B MACH3 USB pendant is available in both the -4 and -6 axis versions.

add the following to the smoothiehost.ini file...

    [modules]
    whb04b = 0x10ce:0xeb93

The macro button functions can be defined in the whb04b.ini file (for starting you can copy and rename the sample_whb04b.ini file)...

    [macros]
    # user defined macro buttons
    (see the sample file)

NOTE that if ```{axis}``` appears in the macro it will be replaced by the currently selected axis.

Python Easyhid needs to be installed...

* sudo apt-get install libffi-dev
* sudo apt-get install libhidapi-libusb0
* git clone https://github.com/ahtn/python-easyhid
* cd python-easyhid
* sudo python3 setup.py install

then add this to ```/etc/udev/rules.d/50-whb04b.rules```...

    SUBSYSTEMS=="usb", ATTRS{idVendor}=="10ce", ATTRS{idProduct}=="eb93", MODE:="0666"

Plug in the WHB04B or the dongle and turn the unit on, then run smoopi.

The Fn buttons (hold down Fn key) have hard coded actions to match the printed function.

The other hard coded buttons are the ```step``` button which sets the mode to step mode. The Continuous button sets continuous mode (which currently does nothing), and Fn Continuous will set the MPG mode which also currently does nothing.

The Stop button will send a kill/halt (control X) to smoothie and the Reset will send ```$X``` to unkill.

The Start and Pause button will run the last viewed or Run file.

Fn and the Macro10 button will toggle the display from WCS to MCS display.
