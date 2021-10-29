#!/usr/bin/python
import json, os
config_json = os.path.join(os.environ['NODE_PATH'], 'config.json')

IS_PI4 = os.path.exists('/sys/bus/platform/drivers/vc4-drm')

with open(config_json) as f:
    rotation = json.load(f)['rotation']

with open('xorg.conf', 'wb') as f:
    if IS_PI4:
        def screen_resolution():
            with open("/sys/class/graphics/fb0/virtual_size", "rb") as f:
                return [int(val) for val in f.read().strip().split(',')]

        width, height = screen_resolution()

        f.write("""
            Section "Monitor"
               Identifier "Monitor"
               Option "Rotate" "%(rotate)s"
            EndSection

            Section "Screen"
               Identifier "Screen"
               Monitor "Monitor"
               SubSection "Display"
                  Modes "%(width)dx%(height)d"
               EndSubSection
            EndSection
        """ % dict(
            rotate = {
                0: 'normal',
                90: 'right',
                180: 'inverted',
                270: 'left',
            }[rotation],
            width = width,
            height = height,
        ))
    elif rotation == 0:
        f.write("# empty")
    else:
        f.write("""
            Section "Device"
                Identifier "Device"
                Option "Rotate" "%(rotate)s"
            EndSection

            Section "Screen"
               Identifier "Screen"
               Device "Device"
            EndSection
        """ % dict(
            rotate = {
                90: 'CW',
                180: 'UD',
                270: 'CCW',
            }[rotation]
        ))
