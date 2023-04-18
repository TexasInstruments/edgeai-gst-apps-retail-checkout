##FAQ

Here's a little FAQ/list of potential hiccups to help:

* My camera isn't doing anything, what's wrong!
  * Check that your camera is recognized. Run 'v4l2-ctl --list-devices'. If there is no /dev/video2, then the camera is probably not connected correctly. This is common with CSI cameras on ribbon cables. Try reseating
  * If you have multiple cameras, make sure the one you want to use is the one at /dev/video2. Else, change that with the -d tag for command-line options
* The screen looks weird and too small. Is using a 720p camera wrong?
  * It won't break, but may look strange. The display expects 1080 pixel height and there is no up-sizing possible as-is. 720p throws this off. The main function in retail_vision_app.py can be modified to better reflect 720p cameras and display sizes
* There's no frames being pulled/processed, and I saw a long weird printout at the start of the application. It mentioned some failures but the app didn't quit. What do I do?
  * OpenVX will print errors like these but will not halt the application. OpenVX let's the processing cores on this architeture talk to each other, and sometimes not every core has a graceful exit. This only happens when an OpenVX-related application starts and restarts too many times (>3 minimum; TI's GST plugins use OpenVX). Long running applications are not affected by this issue. Reboot the processor. 
* I changed the model and its not working. What do I do?
  * Try testing the model with the other applications in the edgeai-gst-apps, especially optiflow. 
    * Postprocessing plugins can give errors and not tell exactly why (typically coredumps if that is at fault). Often, it's errors in the YAML files describing a model