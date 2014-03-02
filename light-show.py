'''
************************************************************************

 Light Show
 Copyright (C) 2014 Nick Lowery (nick.a.lowery@gmail.com)

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 www.gnu.org/copyleft/gpl.html

************************************************************************
'''

# ----------------------------------------------------------------------
# - GLOBALS - change these to customize script

# At and below what volume level (0.0 to 1.0) should we just clamp 
# volume to 0 (done before applying brightness function)?
g_zeroThreshold = 0.07

# ** Function relating volume to brightness: B(V) = av^b **
# b - What exponent to apply to the volume. Higher exponent means bigger
# difference between volume levels.
g_volumeExponent = 5.0
# a - What to multiply the volume by after applying the volume exponent.
g_volumeMultiplier = 30.0

# How quickly to fade between actual brightness and target brightness.
# A value of 1 means instantly snap to target brightness on update.
# A value of 0.5 means fade half of the difference each update.
g_fadeFactor = 0.5

# Angular frequencies of each RGB when shifting hue (degrees per second).
g_rgb1_hueFrequency = 360 / 30.0
g_rgb2_hueFrequency = 360 / 30.0

# Cycles per second for PWM (pulse-width modulation). Values below ~80
# will result in visible flickering for most people.
g_pwmFrequency = 120.0

# ----------------------------------------------------------------------


from RPi import GPIO
from time import sleep, time
import alsaaudio
from audioop import rms
from colorsys import hsv_to_rgb

	
def main(args):
	# Make sure a valid audio input was given in args
	if len(args) is not 2 or args[1] not in alsaaudio.cards():
		print("Usage: python scriptName [\"input-device-name\"]\n")
		printSoundCards()
		exit(1)
	
	# Initialize audio input
	try:
		audioInput = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, args[1])
		audioInput.setchannels(1)
		audioInput.setrate(8000)
		audioInput.setformat(alsaaudio.PCM_FORMAT_S16_LE)
	except:
		print("Failed to initialize input from device \"" + args[1] + ".\" Please make sure the given device receives input.\n")
		printSoundCards()
		exit(1)

	# Initialize RPi GPIO pins and RGB outputs
	GPIO.setmode(GPIO.BOARD)
	rgb1 = RGB(11, 12, 13)
	rgb2 = RGB(15, 16, 18)
	
	# Run program until Ctrl-C interrupt
	print("Please use CTRL-C when you want to exit the program.")
	try:
		oldTime = time()
		rgb1_hue = 0
		rgb2_hue = 0

		while True:
			# Calculate time delta
			nowTime = time()
			deltaTime = nowTime - oldTime
			oldTime = nowTime
		
			# Read audio data
			length, data = audioInput.read()
			magnitude = 0
			if length > 0:		
				# Get percentile magnitude of audio and apply transform
				magnitude = (rms(data, 2) / 65535.0)
				magnitude = 0 if magnitude <= g_zeroThreshold else magnitude
				magnitude = g_volumeMultiplier * (magnitude ** g_volumeExponent)
				magnitude = max(min(magnitude, 1.0), 0.0)
				
			# Cycle hues
			rgb1_hue += g_rgb1_hueFrequency * deltaTime / 360.0
			rgb2_hue += g_rgb2_hueFrequency * deltaTime / 360.0
			rgb1_hue = rgb1_hue - 1.0 if rgb1_hue > 1.0 else rgb1_hue
			rgb2_hue = rgb2_hue - 1.0 if rgb2_hue > 1.0 else rgb2_hue
			
			# Convert hues to RGB values
			rgb1_rgb = hsv_to_rgb(rgb1_hue, 1, magnitude)
			rgb2_rgb = hsv_to_rgb(rgb2_hue, 1, magnitude)
			
			# Update RGB outputs
			rgb1.update(*rgb1_rgb)
			rgb2.update(*rgb2_rgb)
				
	except KeyboardInterrupt:
		pass

	# Clean up RGB objects and reset RPi GPIO pins
	rgb1.cleanup()
	rgb2.cleanup()
	GPIO.cleanup()
	print("\nGoodbye!")

	
def printSoundCards():
	print("Valid device names:")
	for d in alsaaudio.cards():
		print("\"" + d + "\"")
	
	
class RGB:
	''' Represents a three-channel PWM collection. '''

	def __init__(self, redPin, greenPin, bluePin):
		self.red = ColorChannel(redPin)
		self.green = ColorChannel(greenPin)
		self.blue = ColorChannel(bluePin)
		
	def cleanup(self):
		self.red.cleanup()
		self.green.cleanup()
		self.blue.cleanup()
		
	def update(self, rtb, gtb, btb):
		self.red.update(rtb)
		self.green.update(gtb)
		self.blue.update(btb)

		
class ColorChannel:
	''' Represents a single color channel PWM object with an actual and target brightness. '''
	
	def __init__(self, pinNum):
		GPIO.setup(pinNum, GPIO.OUT)
		self._PWM = GPIO.PWM(pinNum, g_pwmFrequency)
		self._PWM.start(0)
		self._brightness = 0
		
	def cleanup(self):
		self._PWM.stop()
		
	def update(self, targetBrightness):
		# 1. Clamp target brightness to [0, 100].
		# 2. Fade actual brightness toward target brightness.
		# 3. Update PWM frequency.
		targetBrightness *= 100.0
		targetBrightness = max(min(targetBrightness, 100.0), 0.0)
		self._brightness += (targetBrightness - self._brightness) * g_fadeFactor
		self._brightness = 0 if self._brightness <= 0.01 else self._brightness
		self._PWM.ChangeDutyCycle(self._brightness)
		
	
if __name__ == "__main__":
	import sys
	main(sys.argv)