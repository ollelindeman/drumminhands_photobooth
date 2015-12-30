#!/usr/bin/env python
# created by chris@drumminhands.com
# see instructions at http://www.drumminhands.com/2014/06/15/raspberry-pi-photo-booth/

import os
import glob
import time
import traceback
from time import sleep
import RPi.GPIO as GPIO
import picamera # http://picamera.readthedocs.org/en/release-1.4/install2.html
import atexit
import sys
import socket
import pytumblr # https://github.com/tumblr/pytumblr
import config
from signal import alarm, signal, SIGALRM, SIGKILL

########################
### Variables Config ###
########################
led1_pin = 15 # LED 1
led2_pin = 19 # LED 2
led3_pin = 21 # LED 3
led4_pin = 23 # LED 4
button1_pin = 22 # pin for the big red button
button2_pin = 18 # pin for button to shutdown the pi
button3_pin = 16 # pin for button to end the program, but not shutdown the pi

post_online = 0 # default 1. Change to 0 if you don't want to upload pics.
total_pics = 8 # number of pics to be taken
capture_delay = 0.5 # delay between pics
prep_delay = 3 # number of seconds at step 1 as users prep to have photo taken
gif_delay = 50 # How much time between frames in the animated gif
restart_delay = 5 # how long to display finished message before beginning a new session

test_server = 'www.google.com'
real_path = os.path.dirname(os.path.realpath(__file__))

# Setup the tumblr OAuth Client
client = pytumblr.TumblrRestClient(
    config.consumer_key,
    config.consumer_secret,
    config.oath_token,
    config.oath_secret,
);

####################
### Other Config ###
####################
GPIO.setmode(GPIO.BOARD)
GPIO.setup(led1_pin,GPIO.OUT) # LED 1
GPIO.setup(led2_pin,GPIO.OUT) # LED 2
GPIO.setup(led3_pin,GPIO.OUT) # LED 3
GPIO.setup(led4_pin,GPIO.OUT) # LED 4
GPIO.setup(button1_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # falling edge detection on button 1
GPIO.setup(button2_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # falling edge detection on button 2
GPIO.setup(button3_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # falling edge detection on button 3
GPIO.output(led1_pin,False);
GPIO.output(led2_pin,False);
GPIO.output(led3_pin,False);
GPIO.output(led4_pin,False); #for some reason the pin turns on at the beginning of the program.

#################
### Functions ###
#################

def cleanup():
  print('Ended abruptly')
  GPIO.cleanup()
atexit.register(cleanup)

def shut_it_down(channel):  
    print "Shutting down..." 
    GPIO.output(led1_pin,True);
    GPIO.output(led2_pin,True);
    GPIO.output(led3_pin,True);
    GPIO.output(led4_pin,True);
    time.sleep(3)
    os.system("sudo halt")

def exit_photobooth(channel):
    print "Photo booth app ended. RPi still running" 
    GPIO.output(led1_pin,True);
    time.sleep(3)
    sys.exit()
    
def clear_pics(foo): #why is this function being passed an arguments?
    #delete files in folder on startup
	files = glob.glob(config.file_path + '*')
	for f in files:
		os.remove(f) 
	#light the lights in series to show completed
	print "Deleted previous pics"
	GPIO.output(led1_pin,False); #turn off the lights
	GPIO.output(led2_pin,False);
	GPIO.output(led3_pin,False);
	GPIO.output(led4_pin,False)
	pins = [led1_pin, led2_pin, led3_pin, led4_pin]
	for p in pins:
		GPIO.output(p,True); 
		sleep(0.25)
		GPIO.output(p,False);
		sleep(0.25)
      
def is_connected():
  try:
    # see if we can resolve the host name -- tells us if there is
    # a DNS listening
    host = socket.gethostbyname(test_server)
    # connect to the host -- tells us if the host is actually
    # reachable
    s = socket.create_connection((host, 80), 2)
    return True
  except:
     pass
  return False    

# define the photo taking function for when the big button is pressed 
def start_photobooth(): 
	################################# Begin Step 1 ################################# 
	print "Get Ready"
	GPIO.output(led1_pin,True);
	sleep(prep_delay) 
	GPIO.output(led1_pin,False)

	camera = picamera.PiCamera()
	pixel_width = 500 #use a smaller size to process faster, and tumblr will only take up to 500 pixels wide for animated gifs
	pixel_height = 500
	camera.resolution = (pixel_width, pixel_height) 
	camera.vflip = True
	camera.hflip = False
	#camera.saturation = -100 # comment out this line if you want color images
	camera.start_preview()
	
	sleep(2) #warm up camera

	################################# Begin Step 2 #################################
	print "Taking pics" 
	now = time.strftime("%Y-%m-%d-%H:%M:%S") #get the current date and time for the start of the filename
	try: #take the photos
		for i, filename in enumerate(camera.capture_continuous(config.file_path + now + '-' + '{counter:02d}.jpg')):
			GPIO.output(led2_pin,True) #turn on the LED
			print(filename)
			sleep(0.25) #pause the LED on for just a bit
			GPIO.output(led2_pin,False) #turn off the LED
			sleep(capture_delay) # pause in-between shots
			if i == total_pics-1:
				break
	finally:
		camera.stop_preview()
		camera.close()
	########################### Begin Step 3 #################################
	print "Creating an animated gif" 

	GPIO.output(led3_pin,True) #turn on the LED
	graphicsmagick = "gm convert -delay " + str(gif_delay) + " " + config.file_path + now + "*.jpg " + config.file_path + now + ".gif" 
	os.system(graphicsmagick) #make the .gif
	print "Uploading to tumblr. Please check " + config.tumblr_blog + ".tumblr.com soon."

	if post_online: # turn off posting pics online in the variable declarations at the top of this document
		connected = is_connected() #check to see if you have an internet connection
		while connected: 
			try:
				file_to_upload = config.file_path + now + ".gif"
				client.create_photo(config.tumblr_blog, state="published", tags=["drumminhandsPhotoBooth"], data=file_to_upload)
				break
			except ValueError:
				print "Oops. No internect connection. Upload later."
				try: #make a text file as a note to upload the .gif later
					file = open(config.file_path + now + "-FILENOTUPLOADED.txt",'w')   # Trying to create a new file or open one
					file.close()
				except:
					print('Something went wrong. Could not write file.')
					sys.exit(0) # quit Python
	GPIO.output(led3_pin,False) #turn off the LED
	
	########################### Begin Step 4 #################################
	GPIO.output(led4_pin,True) #turn on the LED
	print "Done"
	GPIO.output(led4_pin,False) #turn off the LED
	
	time.sleep(restart_delay)

####################
### Main Program ###
####################

# when a falling edge is detected on button2_pin and button3_pin, regardless of whatever   
# else is happening in the program, their function will be run   
#GPIO.add_event_detect(button2_pin, GPIO.FALLING, callback=shut_it_down, bouncetime=300) 

#choose one of the two following lines to be un-commented
#GPIO.add_event_detect(button3_pin, GPIO.FALLING, callback=exit_photobooth, bouncetime=300) #use third button to exit python. Good while developing
#GPIO.add_event_detect(button3_pin, GPIO.FALLING, callback=clear_pics, bouncetime=300) #use the third button to clear pics stored on the SD card from previous events

# delete files in folder on startup
files = glob.glob(config.file_path + '*')
for f in files:
    os.remove(f)

print "Photo booth app running..." 
GPIO.output(led1_pin,True); #light up the lights to show the app is running
GPIO.output(led2_pin,True);
GPIO.output(led3_pin,True);
GPIO.output(led4_pin,True);
time.sleep(3)
GPIO.output(led1_pin,False); #turn off the lights
GPIO.output(led2_pin,False);
GPIO.output(led3_pin,False);
GPIO.output(led4_pin,False);

while True:
        GPIO.wait_for_edge(button1_pin, GPIO.FALLING)
	time.sleep(0.2) #debounce
	start_photobooth()
