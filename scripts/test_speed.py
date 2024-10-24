# inspired by the test speed in klipper reimplemented as a script for Smoopi on a SBV2

import sys
from argparse import ArgumentParser

arg_parser = ArgumentParser(prog="test_speed", description="Speed tester script")

arg_parser.add_argument(
    "--debug",
    help="do not wait for ok (default: %(default)s)",
    default=False
)
arg_parser.add_argument(
    "--speed",
    help="specify feedrate in mm/sec (default: %(default)s)",
    default='100',
    type=int
)
arg_parser.add_argument(
    "--iter",
    help="specify iterations (default: %(default)s)",
    default='2',
    type=int
)
arg_parser.add_argument(
    "--accel",
    help="specify acceleration in mm/sec^2 (default: %(default)s)",
    default='2000',
    type=int
)
arg_parser.add_argument(
    "--radius",
    help="specify radius to test (default: %(default)s)",
    default='130',
    type=int
)
arg_parser.add_argument(
    "--z_height",
    help="specify height to run test at (default: %(default)s)",
    default='100',
    type=int
)

args = arg_parser.parse_args()
speed = args.speed
iterations = args.iter
accel = args.accel
z_height = args.z_height
debug = args.debug

smallpatternsize = 20

# Large pattern
radius = args.radius
xy_max_pos = ((radius ** 2) / 2) ** 0.5
x_min = xy_max_pos * -1
x_max = xy_max_pos
y_min = xy_max_pos * -1
y_max = xy_max_pos
# display(f"x_min: {x_min}, x_max: {x_max}, y_min: {y_min}, y_max: {y_max}")

# Small pattern at center
# Set small pattern box around center point
x_center_min = smallpatternsize / 2 * -1
x_center_max = smallpatternsize / 2
y_center_min = smallpatternsize / 2 * -1
y_center_max = smallpatternsize / 2


def send(str):
    sys.stdout.write(str + '\n')
    if not debug:
        # wait for ok
        while True:
            ll = sys.stdin.readline()   # read a line
            if ll.startswith('ok'):
                break
            else:
                sys.stderr.write(f'> {ll}')
                sys.stderr.flush()


def display(str):
    sys.stderr.write(str + '\n')


def get_pos():
    sys.stdout.write('get pos\n')
    raw = ""
    while True:
        ll = sys.stdin.readline()   # read a line
        if ll.startswith('ok'):
            return raw
        elif ll.startswith('RAW:'):
                raw = ll


# Save current gcode state (absolute/relative, etc)
send('M120')

# Output parameters to g-code terminal
display("TEST_SPEED_DELTA: starting %d iterations at speed %d, accel %d" % (iterations, speed, accel))

# Home and get position for comparison later:
send('M400')  # Finish moves
send('G28')
send('G90')
send('G4 P1000')

p = get_pos()
sys.stderr.write(f'pos: {p}\n')
sys.stderr.flush()

# Go to starting position
send(f"G0 X{x_min} Y{y_min} Z{z_height} F{speed*60}")

'''
    # Set new limits
    {% if printer.configfile.settings.printer.minimum_cruise_ratio is defined %}
        SET_VELOCITY_LIMIT VELOCITY={speed} ACCEL={accel} MINIMUM_CRUISE_RATIO={min_cruise_ratio}
    {% else %}
        SET_VELOCITY_LIMIT VELOCITY={speed} ACCEL={accel} ACCEL_TO_DECEL={accel / 2}
    {% endif %}
'''

for i in range(iterations):
    # Large pattern diagonals
    send(f'G0 X{x_min} Y{y_min} F{speed * 60}')
    send(f'G0 X{x_max} Y{y_max} F{speed * 60}')
    send(f'G0 X{x_min} Y{y_min} F{speed * 60}')
    send(f'G0 X{x_max} Y{y_min} F{speed * 60}')
    send(f'G0 X{x_min} Y{y_max} F{speed * 60}')
    send(f'G0 X{x_max} Y{y_min} F{speed * 60}')

    # Large pattern box
    send(f'G0 X{x_min} Y{y_min} F{speed * 60}')
    send(f'G0 X{x_min} Y{y_max} F{speed * 60}')
    send(f'G0 X{x_max} Y{y_max} F{speed * 60}')
    send(f'G0 X{x_max} Y{y_min} F{speed * 60}')

    # Small pattern diagonals
    send(f'G0 X{x_center_min} Y{y_center_min} F{speed * 60}')
    send(f'G0 X{x_center_max} Y{y_center_max} F{speed * 60}')
    send(f'G0 X{x_center_min} Y{y_center_min} F{speed * 60}')
    send(f'G0 X{x_center_max} Y{y_center_min} F{speed * 60}')
    send(f'G0 X{x_center_min} Y{y_center_max} F{speed * 60}')
    send(f'G0 X{x_center_max} Y{y_center_min} F{speed * 60}')

    # Small pattern box
    send(f'G0 X{x_center_min} Y{y_center_min} F{speed * 60}')
    send(f'G0 X{x_center_min} Y{y_center_max} F{speed * 60}')
    send(f'G0 X{x_center_max} Y{y_center_max} F{speed * 60}')
    send(f'G0 X{x_center_max} Y{y_center_min} F{speed * 60}')

'''
    # Restore max speed/accel/accel_to_decel to their configured values
    {% if printer.configfile.settings.printer.minimum_cruise_ratio is defined %}
        SET_VELOCITY_LIMIT VELOCITY={printer.configfile.settings.printer.max_velocity} ACCEL={printer.configfile.settings.printer.max_accel} MINIMUM_CRUISE_RATIO={printer.configfile.settings.printer.minimum_cruise_ratio} 
    {% else %}
        SET_VELOCITY_LIMIT VELOCITY={printer.configfile.settings.printer.max_velocity} ACCEL={printer.configfile.settings.printer.max_accel} ACCEL_TO_DECEL={printer.configfile.settings.printer.max_accel_to_decel}
    {% endif %}
'''

# Re-home and get position again for comparison:
send('M400')  # Finish moves
send('G28')
send('G4 P1000')
p = get_pos()
sys.stderr.write(f'pos: {p}\n')
sys.stderr.flush()

# Restore previous gcode state (absolute/relative, etc)
send('M121')
send('G4 P1000')
