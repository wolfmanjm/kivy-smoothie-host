# Restarting a failed print from where it left off.

When a print fails there will be a message in the main windows and in the log that shows
at which line the file was at when it failed.

You will need to edit the gcode file and go to that line. remember that the
print may not actually have reached that line, as there is a buffer in Smoothie.

Scroll back in the gcode file and find the start of the layer that is preceding that last line read.

Delete all lines prior to that Layer (except for required startup gcode).

Save this file as the restart file, and then you can print that file and it
should start at the layer it was printing.

It is a good idea to measure the current height of the print with a caliper, and cross check that it matches
the layer height in the gcode file.

