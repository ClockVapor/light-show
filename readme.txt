Light Show v0.1.0 (2 March 2014)
Copyright (C) 2014 Nick Lowery (nick.a.lowery@gmail.com)
See license.txt for full license.

Light Show is a Python program designed to run on Raspberry Pi. It listens to mono audio input from a specified device and uses PWM (pulse-width modulation) to adjust the brightness and color of any RGB light system according to what it hears.

Required extra Python modules:
	- RPi.GPIO
	- alsaaudio

By default, the program is set up to control two RGB lights connected to the Raspberry Pi's GPIO pins 11, 12, 13, 15, 16, and 18 respectively for R1, G1, B1, R2, G2, B2 channels. The brightness of both lights is determined by the function B(V) = aV^b, where B(V) is the brightness, V is the volume of audio heard, a is the volume multiplier, and b is the volume exponent. The color of both lights rotates through the color wheel once every thirty seconds. All of these values are listed as globals at the top of the script and may be modified.