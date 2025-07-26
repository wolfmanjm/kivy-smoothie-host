# Installation instructions

The easiest installation for an RPI3a or RPI3b is to use the presetup image [here](https://github.com/wolfmanjm/kivy-smoothie-host/releases/tag/V1.1-image)

Flash it to a sdcard and boot.

Another easy method is to use the rpi-imager to install 64-bit Bookworm lite, and setup the wifi in that then flash it. Then...

    sudo apt install git
    git clone https://github.com/wolfmanjm/kivy-smoothie-host.git smoopi
    cd smoopi
    ./install-smoopi-on-bookworm

**NOTE** If installing the 64-bit version on a RPI3b then the following needs to be appended to the ```/boot/firmware/cmdline.txt```, which fixes a reported kernel bug affecting USB.

    dwc_otg.fiq_enable=0 dwc_otg.fiq_fsm_enable=0


## Install on RPI

**NOTE** Get a good sdcard for the rpi as it makes a significant difference in performance, an A1 rating is best like sandisk ultra 16gb A1 or the 32gb version.
Samsung Evo+ are also supposed to be very fast in an RPI.

**WARNING** Backup the sdcard regularly (I use rpi-clone), as the cards do fail quite quickly (I've had one fail after 9 months), the Sandisk ultras seem especially prone to early failure, and apparently using them on RPI invalidatesc the cards warranty.

**NOTE** on the older versions of raspbian (like bulldog or stretch) you need to add the following, however this is optional on a recent Bullseye install if you run as the user setup during install.

    > sudo nano /etc/udev/rules.d/90-smoothie.rules
    and add this...

    SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666"
    SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666", SYMLINK+="smoothie%n"
    ACTION=="add", SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", RUN+="/bin/stty -F /dev/ttyACM%n -echo -echoe -echok"

The last line is quite important otherwise you get a whole lot of ok's echoed back to smoothie when it opens. This does not appear to be needed on a desktop probably due to the speed it is setup vs the rpi.

### Raspbian running bookworm on RPI3x/RPI4xx/RPI5

Bookworm seems to have changed the way python packages are installed, so it maybe easier to do the following...

    sudo apt update
    sudo apt upgrade
    sudo apt install python3-kivy python3-aiofiles python3-serial git xclip xsel
    git clone https://github.com/wolfmanjm/kivy-smoothie-host.git smoopi

    cd smoopi
    python main.py


That seems to work if running with or without X.

*optional*
This installs a slightly older version of Kivy. To install the latest version of kivy do the following...

    cd ~
    python3 -m venv smoopivenv
    ~/smoopivenv/bin/pip3 install kivy[base]
    cd ~/smoopi
    ~/smoopivenv/bin/python main.py


You can skim the rest of the README if you run into issues

You may also want to disable the modem manager to stop it interfering with serial ports...

    sudo systemctl disable ModemManager


### Raspbian/Buster (or Bullseye) on RPI3x (NOT RPI4b)

**NOTE** This is not recommended, it is best to use bookworm. Left here for posterity.

(Tested on RPI3a+ and 3b+, genuine RPI 7" multitouch screen and external HDMI LCD monitor).

(This may work on older RPI versions but is not tested, please read this https://www.raspberrypi.org/documentation/hardware/display/legacy.md).

Install the latest raspbian buster lite (or Bullseye lite)... (No XWindows) either 32bit or 64bit version.

The touch display does not seem to work very reliably under Bullseye so for now I recommend Buster.

You can also create an image for your raspi using the raspi imager from here. https://www.raspberrypi.com/software/, using the advanced menu
(type Ctrl-Shift-X) you can quickly presetup your wifi and make it heabdless. (Do not enable or install X Windows if you are using the raspi 7" touch screen). Select the Buster lite OS.

You need to install kivy version 2.2.1 to get the wheel...

    sudo apt update
    sudo apt upgrade (maybe reboot)
    sudo apt install python3-pip
    python3 -m pip install --user kivy==2.2.1
    # you also need to do the following to install the required support libraries
    sudo apt install libjpeg-dev libsdl2-2.0-0 libsdl2-ttf-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libmtdev1 libgl1-mesa-dev libgles2-mesa xclip xsel


Then skip to the Smoopi install and setup [section below](https://github.com/wolfmanjm/kivy-smoothie-host#smoopi-install-and-setup)

After running smoopi the first time a default ```~/.kivy/config.ini``` will be created and may need editing as below.

On an rpi3b+ (and better) it seems the double tap time needs to be increased to be usable..

    # in file ~/.kivy/config.ini
    [postproc]
    double_tap_distance = 20
    double_tap_time = 400 # <-- increase this from the 200 default
    triple_tap_distance = 20
    triple_tap_time = 600 # <- and this to be > than double_tap_time

Also if the touch screen does not work then you need to make sure that this is set in the kivy config.ini...

    # in file ~/.kivy/config.ini
    [input]
    mtdev_%(name)s = probesysfs,provider=mtdev

**NOTE** if installing on Bullseye with a touch screen and RPI3

    Edit the /boot/config.txt and add the following, then reboot...

    [all]
    # Disable compensation for displays with overscan
    disable_overscan=1

    # to force lcd detection on RPI1
    ignore_lcd=0
    dtoverlay=vc4-fkms-v3d

#### RPI4b/RPI400/RPI5 and Raspbian Buster or Bullseye

**NOT** recommended, use Bookworm

#### Running under XWindows on RPI for Bullseye and Buster (NOT Bookworm)

**NOTE** This also is no longer recommended, use bookworm.

On RPI3b make sure that you run `raspi-config` and enable the fake KMS driver, otherwise Smoopi will run really slowly under S/W emulated GL.
On RPI4b with Bullseye this is not needed, the default driver works fine.

If using a mouse make sure that in `~/.kivy/config.ini`

    [input]
    mouse = mouse

is the only entry under `[input]` otherwise you will get multiple cursors and click events will go to unexpected places.

When running under XWindows the cursor module is not required nor are the hidinput input drivers.

If running as a resizable window under X you need to make sure the following are set in the `~/.kivy/config.ini`

    [kivy]
    desktop = 1

    [graphics]
    fullscreen = 0
    borderless = 0
    resizable = 1
    show_cursor = 1

(also make sure to set ```[UI] touch_screen = false``` in ```smoothiehost.ini```)

If you are using a touch screen under XWindows you need to run smoopi full screen, and in `~/.kivy/config.ini`
you have the following settings...

    [kivy]
    desktop = 1

    [graphics]
    fullscreen = 1
    show_cursor = 0
    borderless = 1
    resizable = 0

    [input]
    mtdev_%(name)s = probesysfs,provider=mtdev

(also make sure to set ```[UI] touch_screen = true``` in ```smoothiehost.ini```)

If the resolution is 1024x600 the RPI Full Screen layout is preferable.
If you have 1024x800 or better then the wide screen layout is preferable.
Either way when running under XWindows one of the Desktop screen layouts should be used.

#### Keyboard and Mouse support when running from console (egl-rpi)
Kivy uses a module called the HIDInput for an external (USB) Mouse and keyboard.
You will  need to add the following line to your ```~/.kivy/config.ini``` ...

    [kivy]
    keyboard_mode = system

    [input]
    %(name)s = probesysfs,provider=hidinput

    [modules]
    cursor = 1


### Smoopi install and setup
It is recommended to do this first...

    > sudo apt update
    > sudo apt upgrade

Then install some smoopi dependencies...

    > python3 -m pip install --user --upgrade pyserial aiofiles

Install Smoopi itself

    > sudo apt install git
    > git clone https://github.com/wolfmanjm/kivy-smoothie-host.git smoopi

Run with...

    > cd ./smoopi
    > python3 main.py

NOTE when using the touch panel make sure the ```~/.kivy/config.ini``` has the following set so the virtual keyboard works in a usable fashion on an RPI touch screen...

    [kivy]
    keyboard_mode = systemanddock
    desktop = 0

If your ```~/.kivy/config.ini``` is empty then the ```~/.kivy``` directory should be removed (if it is there), and run smoopi once and the default config.ini will be created.

To allow the program to shutdown the RPI when the shutdown menu entry is selected you need to do the following, unless smoopi is running as root/superuser.


    Use policykit make sure policykit-1 is installed > sudo apt install policykit-1

    Create as root /etc/polkit-1/localauthority/50-local.d/all_all_users_to_shutdown_reboot.pkla with the
    following content:

    [Allow all users to shutdown and reboot]
    Identity=unix-user:*
    Action=org.freedesktop.login1.power-off;org.freedesktop.login1.power-off-multiple-sessions;org.freedesktop.login1.reboot;org.freedesktop.login1.reboot-multiple-sessions
    ResultAny=yes

### Autostart Smoopi (Optional)

To autostart smoopi on boot but run as the pi user follow these directions...

1. Install runit (sudo apt install runit).
2. On Raspbian Stretch/Buster do ```sudo apt-get install runit-systemd``` (not needed on Bullseye)
3. in the /home/pi directory run ```tar xvf ./smoopi/runit-setup-stretch.tar``` (presuming you checked out the smoopi source into /home/pi/smoopi)
4. sudo ln -s /home/pi/sv/smoopi /etc/service


To allow Smoopi to connect to the smoothie when auto start by runit you need to do this...

    sudo nano /etc/udev/rules.d/90-smoothie.rules
    and add this...

    SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666"
    SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", MODE="0666", SYMLINK+="smoothie%n"
    ACTION=="add", SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6015", RUN+="/bin/stty -F /dev/ttyACM%n -echo -echoe -echok"

smoopi is now managed by runit. (This has the side effect of restarting smoopi if it crashes).

The smoopi app will start, and will also start on boot. (To stop it you type ```sudo sv stop /etc/service/smoopi```)

### Shutdown and Startup button for RPI (Optional)
Optionally to add a button to boot and to shutdown the rpi install a NORMALLY OPEN push button on pins 5 and 6 on the header,
then you need to add the shutdown script to autostart... ```sudo ln -s /home/pi/sv/shutdown /etc/service```. NOTE you may need a capacitor across the button to stop noise shutting down the system.

### Backlight on RPI Touchscreen
To allow Smoopi to turn on/off the backlight of the official touch screen you need to do this...

    sudo nano /etc/udev/rules.d/backlight-permissions.rules
    and add this...
    SUBSYSTEM=="backlight",RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"

If you are using bookworm the actual path maybe different, you will need to look in `/sys/class/backlight` and see if there is a subdirectory and then you will need to specify that in the config file.
For example on bookworm using the rpi touch screen 2 you need to add...

    [general]
    backlight_path = /sys/class/backlight/10-0045


NOTE the default is for no blanking, there is a setting under the settings menu that allows you to set the timeout for blanking the screen, it is initially set to 0 which is no blanking. If it blanks then touching the screen will unblank it.

NOTE if you are using an HDMI touch screen then you do not need to do the permissions above, however you need to set ```hdmi = true``` under the ```[general]``` section of the ```smoothiehost.ini``` file.

### Builtin webserver and optional camera
In Settings you can turn on the webserver (at port 8000) which will simply allow you to get current progress from any web browser, nothing fancy.
Also in Settings you can enable the video option which uses mjpg-streamer
(which needs to be built and installed, See https://github.com/jacksonliam/mjpg-streamer.git for instructions on that). If enabled and running then the video will show up in the progress web page.
There is also a camera option in the system menu which allows a preview of the camera view. The url for the camera is in the settings, and should be the url which gets a video stream from the camera. If the camera is local it should be set to '''localhost''' which will get replaced with the actual IP when a remote browser requests it. (The default '''http://localhost:8080/?action=stream''' is to get the frame from the locally running mjpg-streamer, but can actually be any URL of any webcam that can stream mjpg video).

You can flip the camera image vertically and/or horizontally by adding to ```smoothiehost.ini``` :

    [web]
    camera_flip_y = true
    camera_flip_x = true

If there is an error in the logs when you open the camera that says that authentication is required then add to the web section of the ```smoothiehost.ini``` in addition to the url already added:

    [web]
    camera_realm = REALM
    camera_user = user
    camera_password = password
    camera_singleshot = 0

replacing the REALM with the realm specified in the error log, and the user and password that the camera needs. If the camera only supplies one snapshot per request then set the ```camera_singleshot = 1```.

If you are using the supplied image and want the streamer to auto start then..

    1. from the home directory
    2. '''> tar xvf smoopi/runit-setup-mjpegstreamer.tar'''
    3. edit '''~/sv/streamer/run''' and make sure the path is correct to the mjpeg streamer directory
    4. edit '''~/sv/streamer/env/LD_LIBRARY_PATH''' and make sure the path is correct there too
    5. delete '''~/sv/streamer/down'''

It should auto start then.

## Install on Linux Desktop

(and maybe windows/macos)

Install on recent Linux (Ubuntu/Debian etc) with python >= 3.7.x and <= 3.13.x using the fast wheels installation...

    sudo apt install python3-pip
    python3 -m pip install --upgrade --user pip setuptools
    python3 -m pip install --user --upgrade kivy[base]

On a recent ArchLinux the following worked...

        sudo pacman -S python-pip
        sudo pacman -S python-kivy
        sudo pacman -S python-pyserial
        sudo pacman -S python-aiofiles
        sudo pacman -S xclip


See https://kivy.org/doc/stable/installation/installation-linux.html#using-wheels

However if you want to see video from cameras (the spindle cam for instance) you need to build it yourself as below and make sure gstreamer is installed.

If that does not work then install from source...

    sudo apt-get update
    sudo apt-get install libsdl2-dev libsdl2-image-dev \
       libsdl2-mixer-dev libsdl2-ttf-dev \
       pkg-config libgl1-mesa-dev libgles2-mesa-dev \
       python3-setuptools libgstreamer1.0-dev git-core \
       gstreamer1.0-plugins-{bad,base,good,ugly} \
       gstreamer1.0-{omx,alsa} python3-dev libmtdev-dev \
       xclip xsel
    python3 -m pip install --user --upgrade Cython==0.28.2 pillow
    python3 -m pip install --user --upgrade git+https://github.com/kivy/kivy.git@stable-2.2.0

Install some dependencies we need...

    python3 -m pip install --user --upgrade pyserial aiofiles


Install Smoopi itself

    > mkdir smoopi
    > cd smoopi
    > git clone https://github.com/wolfmanjm/kivy-smoothie-host.git ./smoopi

Run as

    > cd smoopi
    > python3 main.py

In settings set the desktop layout to Wide Desktop (or Small Desktop or Large Desktop) and restart.  The larger desktop layouts can also have a size specified by editing the smoothiehost.ini file and changing eg ```screen_size = 1024x900``` under the [UI] section. Set ```screen_size``` and
```screen_pos``` to ```none``` if you do not want the screen size and position to be saved and restored. You may need to set ```screen_offset = 30,4``` if you notice that the saved position shifts everytime you start, this is due to a bug in Kivy where it does not take into account the window manager decorations, you would change the ```30,4``` to whatever the screen shift on your system actually is.

By specifying a command line argument you can select a different config file eg
```python3 main.py cnc``` will select ```smoothiehost-cnc.ini``` instead of ```smoothiehost.ini``` so different settings can be used for different machines.

Make sure that under ```~/.kivy/config.ini``` in the ```[input]``` section that only ```mouse = mouse``` is set otherwise you will get multiple cursors and click events will go to unexpected places. The hidinput input driver is also not required (or wanted).

__NOTE__ all the files are coded UTF-8 so make sure your locale (LANG=en_US.utf8 or even LANG=C.UTF-8) is set to a UTF-8 variety otherwise you will get weird errors from deep within python/kivy.
