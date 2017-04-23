# kivy-smoothie-host
A Smoothie host, written in Kivy for running on rpi with touch screen.

This is a work in progress

This uses python >= 3.4.3

## Goal
The goal here is to have a small touch screen host that can run a smoothie and is better than an LCD Panel, and almost as good as a host PC running pronterface.
It is not meant to be a replacement for say Octoprint whose goals are different.

An RPI with 7" touch screen is about the same price as the better LCD panels, and makes a great standalone controller for a 3D printer.

I have had a 10" linux tablet called a pengpod running my delta printer for years as the only Host, it runs a hacked version of Pronterface to make it more tolerable to use on a touch screen. However Pengpods are no longer available and there are no other linux tablets I can find. A raspberry PI with touch screen is pretty close.

I'm running with the very first RPI model A, but this would probably work better with with the newer models, but may even work with the raspberry PI zero.


## Install
I use kivypi from here  http://kivypie.mitako.eu/ and the official 7" touch screen, pretty much runs out-of-the-box.
Recommended to do a sudo apt-get update and sudo apt-get upgrade.

You need the latest python serial and pyserial-asyncio from here https://github.com/pyserial/pyserial-asyncio.git
(git install).

Run with...

> kivy main.py

### On linux (and maybe windows/macos)

Install kivy for python3 from your distro

Run as

> python3 main.py


