Usually M3 and M5 will be used to start and stop a spindle, however quite
often a VFD is used that takes a 0 - 10v signal to set the spindle speed, and
a PWM to 0-10v adapter is used to generate that signal.

Smoothie can use a HWPWM switch to generate this PWM to set the spindle speed
but it uses a M3 S50 for instance to set a 50% duty cycle, whereas the CAM
might generate M3 S4000 to set 4000RPM.

Smoopi can handle this as well as mapping a potentially non-linear PWM to the
control voltage.

We do this by generating a spindle.ini file which provides a calibration table
of PWM duty cycle in percent to the Motor RPM generated. This may or may not
be linear.

When the spindle.ini file is present it enables the spindle_handler code,
which will intercept any M3 Sxxx sent to the smoothie and convert the M3 Sxxx to
the correct PWM value required.

For instance if the gcode file has M3 S5000 to set the spindle to 5000 RPM,
Smoopi will lookup the RPM and find the matching PWM required and then
actually send M3 S55 for instance to Smoothie, seting the PWM duty cycle to
55% which would produce about 5.5volts and the VFD would then set the RPM to
the 5000RPM required. (Of course you should calibrate the table with several
PWM to RPM values).

Additionally you may have multiple belt positions on a multi step pulley in
addition to the VFD, (mainly because VFDs lose a lot of torque at low RPM, or
the maximum RPM of the 3 phase motor may be well under the maximum spindle RPM required).

To handle this case the spindle.ini file can have different ratios for
different belt positions, with the prefereed range of RPMs to use for each
belt position. In this case the [calibration] section has the Motor RPM to
PWM mapping, and the ratio is used to find the spindle RPM.

For instance...
        # spindle.ini

        [setup]
        enabled = true
        translate = M3

        [belt 3]
        ratio = 0.5
        rpm_low = 200
        rpm_high = 2100

        [belt 2]
        ratio = 1.0
        rpm_low = 1120
        rpm_high = 4200

        [belt 1]
        ratio = 2.1
        rpm_low = 2000
        rpm_high = 8820

        [calibration]
        # RPM = PWM duty cycle%, in RPM ascending order, and is RPM of motor
        # first must be the lowest allowed and last must be the highest allowed
        0 = 0
        260 = 1
        1120 = 20
        2000 = 40
        2700 = 60
        3600 = 80
        4200 = 98

This would setup 3 belt positions and the calibration table mapping motor RPM
to PWM duty cycle percentage.

When setting a specific spindle RPM Smoopi would find the RPM in the range of
each belt position, and set the ratio accordingly. In the case the belt
position changes from the previous M3 seen, it will put up a dialog and wait
for you to change the belt position, then dismissing the dialog would send
the M3 to start the spindle. It only does this prompt if the belt position
has changed.

The order of the belt sections is important as you want to use the lowest
ratio for a given RPM to maximize the Torque.

There is a builtin tool called set_rpm that allows you to set a specific RPM
manually as well. This can be added as a macro by adding the following to the
macros.ini file...

        [toolscript spindle speed]
        name = set RPM
        exec = set_rpm
        args = RPM

It will also prompt to set the belt position if it has changed before turning on the spindle.

The console will also display the mapping information and the belt position
needed.

