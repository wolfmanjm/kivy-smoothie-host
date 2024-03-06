#!/usr/bin/python3 -u
# save current WCS and restore it

import sys
import time

wcs = []


def version_file(file_spec):
    """ rename existing files to next in sequence"""
    import os

    if os.path.isfile(file_spec):
        root = file_spec
        # Find last file version
        last_file_num = 0
        for i in range(1, 5):
            new_file = '%s.%02d' % (root, i)
            if os.path.isfile(new_file):
                last_file_num = i
            else:
                break

        # rename all files up so lowest number is newest
        if last_file_num > 0:
            for x in range(last_file_num + 1, 1, -1):
                nfn = '%s.%02d' % (root, x)
                lfn = '%s.%02d' % (root, x - 1)
                os.rename(lfn, nfn)
                # print(f"renamed({lfn, nfn})")

        os.rename(root, '%s.%02d' % (root, 1))
        # print(f"renamed({root, '%s.%02d' % (root, 1)})")


def save():
    sys.stdout.write("$#\n")
    while True:
        ll = sys.stdin.readline()   # read a line

        if ll.startswith('['):
            wcs.append(ll[1:-2])  # strip trailing ] and \n
        elif ll.startswith('ok'):
            break

    fn = "saved_wcs"
    version_file(fn)
    with open(fn, 'w') as f:
        for x in wcs:
            # sys.stderr.write(f"{x}\n")
            f.write(f"{x}\n")

    sys.stderr.write(f"Saved WCS to file {fn}\n")


"""
get wcs
[current WCS: G54]
[G54:38.8023,49.8394,1.3405]
[G55:0.0000,0.0000,0.0000]
[G56:0.0000,0.0000,0.0000]
[G57:0.0000,0.0000,0.0000]
[G58:0.0000,0.0000,0.0000]
[G59:0.0000,0.0000,0.0000]
[G59.1:0.0000,0.0000,0.0000]
[G59.2:0.0000,0.0000,0.0000]
[G59.3:0.0000,0.0000,0.0000]
[G28:0.0000,0.0000,0.0000]
[G30:0.0000,0.0000,0.0000]
[G92:0.0000,0.0000,43.7300]
[TLO:0.0000,0.0000,-0.1000]
[PRB:0.0000,0.0000,0.1831:1]
"""


def restore():
    fn = "saved_wcs"
    with open(fn, 'r') as f:
        for ll in f:
            ll = ll.rstrip()
            if ll:
                g, v = ll.split(':', 1)
                if g.startswith('G'):
                    vl = v.split(',')
                    if g.startswith('G5'):
                        # set WCS
                        if '.' in g:
                            n = int(g[4:]) + 6
                        else:
                            n = int(g[1:]) - 53

                        cmd = f"G10 L2 P{n} X{vl[0]} Y{vl[1]} Z{vl[2]}"
                        sys.stdout.write(f"{cmd}\n")
                        # sys.stderr.write(f"{cmd}\n")
                        sys.stdin.readline()  # consume ok

                    elif g == 'G92':
                        # set G92
                        cmd = f"{g} X{vl[0]} Y{vl[1]} Z{vl[2]}"
                        sys.stdout.write(f"{cmd}\n")
                        # sys.stderr.write(f"{cmd}\n")
                        sys.stdin.readline()  # consume ok

                elif g == 'current WCS':
                    # set working WCS
                    sys.stdout.write(f"{v[1:]}\n")
                    sys.stdin.readline()  # consume ok

    sys.stderr.write("Restored WCS\n")


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        restore()
    else:
        save()

    time.sleep(1)
