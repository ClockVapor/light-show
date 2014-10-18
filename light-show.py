"""
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

****************************************************a********************
"""

# ----------------------------------------------------------------------
# - GLOBALS - change these to customize script

# At and below what brightness level (0.0 to 1.0) should we just clamp brightness to 0?
ZERO_THRESHOLD = 0.005

# Cycles per second for PWM (pulse-width modulation). Values below ~80
# will result in visible flickering for most people.
PWM_FREQUENCY = 120

# How quickly to fade between actual brightness and target brightness.
# A value of 1 means instantly snap to target brightness on update.
# A value of 0.5 means fade half of the difference each update.
FADE_FACTOR = 0.48

# ** Function relating volume to brightness: B(V) = av^b **
# b - What exponent to apply to the volume.
VOLUME_EXPONENT = 5
# a - What to multiply the volume by after applying the volume exponent.
VOLUME_MULTIPLIER = 50.0

# Angular frequencies of each RGB when shifting hue (degrees per second).
RGB1_HUE_FREQUENCY = 360 / 30.0
RGB2_HUE_FREQUENCY = 360 / 30.0

# ----------------------------------------------------------------------


from RPi import GPIO
from time import sleep, time
import alsaaudio
from audioop import rms
from colorsys import hsv_to_rgb


def main(args):
    audio_input = None
    device_name = None

    # If no arguments, try each audio device until one works
    if len(args) == 1:
        error_message = "No suitable device found. Exiting."
        for device in alsaaudio.cards():
            audio_input = initialize_audio_device(device)
            if audio_input is not None:
                device_name = device
                break

    # Else if one argument, use the given audio device
    elif len(args) == 2:
        error_message = "Given device could not be initialized. Exiting."
        audio_input = initialize_audio_device(args[1])
        device_name = args[1]

    # Else, print usage
    else:
        error_message = r"""Usage: python %s [INPUT-DEVICE-NAME]
If no input device is given, all devices are tested until one works.""" % args[0]

    # Let user know which device is being used
    if audio_input is None:
        print(error_message + "\n")
        print_sound_cards()
        exit(1)
    else:
        print("Using device: " + device_name)
        del device_name

    # Initialize RPi GPIO pins and RGB outputs
    GPIO.setmode(GPIO.BOARD)
    rgb1 = RGB(11, 12, 13, FADE_FACTOR, ZERO_THRESHOLD, PWM_FREQUENCY)
    rgb2 = RGB(15, 16, 18, FADE_FACTOR, ZERO_THRESHOLD, PWM_FREQUENCY)

    # Run program until Ctrl-C interrupt
    try:
        time_old = time()
        rgb1_hue = 0
        rgb2_hue = 0

        while True:
            # Calculate time delta
            time_now = time()
            time_delta = time_now - time_old
            time_old = time_now

            # Read audio data
            length, data = audio_input.read()
            magnitude = 0
            if length > 0:
                # Get percentile magnitude of audio and apply transform
                magnitude = (rms(data, 2) / 65535.0)
                magnitude = VOLUME_MULTIPLIER * (magnitude ** VOLUME_EXPONENT)
                magnitude = max(min(magnitude, 1.0), 0.0)

            # Cycle hues
            rgb1_hue += RGB1_HUE_FREQUENCY * time_delta / 360.0
            rgb2_hue += RGB2_HUE_FREQUENCY * time_delta / 360.0
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


def initialize_audio_device(device_name):
    try:
        device = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, device_name)
        device.setchannels(1)
        device.setrate(8000)
        device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    except Exception:
        return None
    else:
        return device


def print_sound_cards():
    print("Valid devices found:")
    for d in alsaaudio.cards():
        print("\"" + d + "\"")
    print("")


class RGB:
    """ Represents a three-channel PWM collection. """

    @property
    def brightness(self):
        return (self.red.brightness + self.green.brightness + self.blue.brightness) / 3.0

    def __init__(self, red_pin, green_pin, blue_pin, fade_factor, zero_threshold, pwm_frequency):
        self.red = ColorChannel(red_pin, fade_factor, zero_threshold, pwm_frequency)
        self.green = ColorChannel(green_pin, fade_factor, zero_threshold, pwm_frequency)
        self.blue = ColorChannel(blue_pin, fade_factor, zero_threshold, pwm_frequency)

    def cleanup(self):
        self.red.cleanup()
        self.green.cleanup()
        self.blue.cleanup()

    def update(self, red_target_brightness, green_target_brightness, blue_target_brightness):
        self.red.update(red_target_brightness)
        self.green.update(green_target_brightness)
        self.blue.update(blue_target_brightness)


class ColorChannel:
    """ Represents a single color channel PWM object with an actual and target brightness. """
    
    @property
    def brightness(self):
        return self._brightness

    def __init__(self, pin_num, fade_factor, zero_threshold, pwm_frequency):
        GPIO.setup(pin_num, GPIO.OUT)
        self._fade_factor = fade_factor
        self._zero_threshold = zero_threshold
        self._pwm = GPIO.PWM(pin_num, pwm_frequency)
        self._pwm.start(0)
        self._brightness = 0

    def cleanup(self):
        self._pwm.stop()

    def update(self, target_brightness):
        # 1. Clamp target brightness to [0, 1].
        # 2. Fade actual brightness toward target brightness.
        # 3. Update PWM frequency.
        target_brightness = max(min(target_brightness, 1.0), 0.0)
        self._brightness += (target_brightness - self._brightness) * self._fade_factor
        self._brightness = 0 if self._brightness <= self._zero_threshold else self._brightness
        self._pwm.ChangeDutyCycle(self._brightness * 100.0)


if __name__ == "__main__":
    import sys
    exit(main(sys.argv))