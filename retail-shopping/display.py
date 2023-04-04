#  Copyright (C) 2023 Texas Instruments Incorporated - http://www.ti.com/
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#
#    Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#    Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the
#    distribution.
#
#    Neither the name of Texas Instruments Incorporated nor the names of
#    its contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import numpy as np
import cv2 as cv

import utils


import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GstApp, GLib, GObject
Gst.init(None)

RECEIPT_FONT = cv.FONT_HERSHEY_SIMPLEX
HEADING_FONT = cv.FONT_HERSHEY_TRIPLEX


class DisplayDrawer():
    '''
    Class to manage the images displayed to the screen. This primarily means the
    subframe that holds a pseudo-receipt of the items recognized and directions
    for the user.

    This is written for 1920 x 1080 display. The receipt image may not look entirely
    correct on smaller displays

    '''
    def __init__(self, screen_width, screen_height, list_width, list_height, image_width, image_height, app_out, classes, gst_caps, list_receipt_full):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.list_width = list_width
        self.list_height = list_height
        self.image_width = image_width
        self.image_height = image_height

        self.gst_app_out = app_out
        self.gst_caps = gst_caps

        self.display_all_items = list_receipt_full

        self.classes = classes
        self.create_default_receipt_images(classes)


    def push_to_display(self, image):
        '''
        Push an image to the display through the appsrc

        param image: and image whose dimensions and pixel format matches self.gst_caps
        '''

        buffer = Gst.Buffer.new_wrapped(image.tobytes())

        self.gst_app_out.set_caps(self.gst_caps)

        self.gst_app_out.push_buffer(buffer)
        
    def create_default_receipt_images(self, classes):
        '''
        Pregenerate the receipt image as a starting point for modifications.
        This is to save cycles. 

        param classes: The set of classes/food objects that can be recognized.
        '''
        #initialize the image as a white screen (pixels all 255)
        list_image = np.full((self.list_height, self.list_width, 3), 255, np.uint8)
        black = (0,0,0)

        # define some locations for columns, rows on the frame
        title_x = 10
        title_y = 40
        item_x = 20
        num_x = 250
        cost_x = 360
        first_item_y = 360
        
        # Title and header
        list_image = cv.putText(list_image, 'TI AM62A Vision MPU', (title_x, title_y), HEADING_FONT, 1.28, black, thickness=2)
        list_image = cv.putText(list_image, 'Grab-n-Go Edge AI Demo', (title_x, title_y+45), HEADING_FONT, 1.0, black, thickness=2)
        list_image = cv.putText(list_image, 'Welcome to the CafeTIeria!', (title_x,title_y+90), HEADING_FONT, 0.95, black, thickness=2)

        #save a version of this image
        self.list_image_headers_only = list_image.copy()
        
        # write the table column names
        start_text_location = (item_x, first_item_y-45)
        list_image = cv.putText(list_image, 'Item', start_text_location, RECEIPT_FONT, 1.0, black, thickness=2)
        list_image = cv.putText(list_image, '#', (num_x, start_text_location[1]), RECEIPT_FONT, 1.0, black, thickness=2)        
        list_image = cv.putText(list_image, 'Cost', (cost_x, start_text_location[1]), RECEIPT_FONT, 1.0, black, thickness=2)


        start_text_location = (item_x, first_item_y)

        if self.display_all_items is True:
            for c in classes:
                list_image = cv.putText(list_image, c['name'].upper(), start_text_location, RECEIPT_FONT, 1.0, black )
                
                start_text_location = (start_text_location[0], start_text_location[1]+50)
            
        # Add line for total cost.
        start_text_location = (item_x, list_image.shape[0]-20)
        list_image = cv.putText(list_image, 'TOTAL:', start_text_location, RECEIPT_FONT, 1.0, black, thickness=2)


        # draw a black line along one size
        list_image = cv.line(list_image, (1,0), (1, list_image.shape[1]), (0,0,0), thickness=2)
        # draw a rectangle around the receipt area
        list_image = cv.rectangle(list_image, (10, first_item_y-75), (list_image.shape[1]-10, list_image.shape[0]-10), color=(0,0,0), thickness=2)

        self.list_image = list_image
        return list_image
        
        
    def fill_receipt_image(self, items, frame, extra_text=None, extra_text_color=(0,0,0)):
        '''
        Fill in the receipt image with a set of items

        param items: dictionary of items in format from utils, including how 
        many are recognized from each class
        param frame: The frame to draw text onto
        param extra_text: Additional Text to draw onto the screen for user directions
        param extra_text_color: Color to use for extra text
        '''
        print('creating list of items in frame')
        # defining some constants for columns and row locations. Should match values in create_default_receipt_images
        black = (0,0,0)
        title_x = 10
        title_y = 40
        item_x = 20
        num_x = 250
        cost_x = 360
        heading_y = 110
        first_item_y = 360
        
        # Total cost for the customer's orders
        total = 0.00

        # draw in the item name, count, and cost to the receipt
        if self.display_all_items:
            # write in every single recognizable item, even if there is none recognized.
            for key in items.keys():
                item = items[key]
                start_text_location = (num_x, first_item_y+(50*item['row']))
                frame = cv.putText(frame, str(item['num']), start_text_location, RECEIPT_FONT, 1.0, black )
                start_text_location = (cost_x, first_item_y+(50*item['row']))
                cost = item['cost'] * item['num']
                total += cost
                frame = cv.putText(frame, '$ %0.2f' % cost, start_text_location, RECEIPT_FONT, 1.0, black )
        else:
            start_text_location = (item_x, first_item_y)

            for key in items.keys():
                item = items[key]
                #only draw if at least one of this item was recognized
                if item['num'] > 0:
                    start_text_location = (item_x, start_text_location[1])
                    frame = cv.putText(frame, key.upper(), start_text_location, RECEIPT_FONT, 1.0, black )

                    start_text_location = (num_x, start_text_location[1])
                    frame = cv.putText(frame, str(item['num']), start_text_location, RECEIPT_FONT, 1.0, black )

                    cost = item['cost'] * item['num']
                    total += cost
                    start_text_location = (cost_x, start_text_location[1])
                    frame = cv.putText(frame, '$ %0.2f' % cost, start_text_location, RECEIPT_FONT, 1.0, black )

                    start_text_location = (start_text_location[0], start_text_location[1]+50)

        # write in the extra text for user directions.
        if extra_text is not None:
            y = title_y + 170
            frame = self.draw_extra_text(frame, extra_text, extra_text_color, x=title_x, y=y)

        # write in the total cost
        start_text_location = (cost_x, frame.shape[0]-20)
        frame = cv.putText(frame, '$ %.2f' % total, start_text_location, RECEIPT_FONT, 1.0, black, thickness=2)

        return frame
            
    def draw_extra_text(self, frame, text, color=(0,0,0), x=10, y=200):
        '''
        Draw extra text to the frame

        param frame: the numpy image array to draw to
        param text: The string of text to draw. Newlines ('\n) will be respected 
        param color: Color of the text
        param x: X location to start from.
        param y: Y location to start from. Text is draw above this line.
        '''
        for text in text.split('\n'):
            location = (x, y)
            frame = cv.putText(frame, text, location, HEADING_FONT, 1.075, color, thickness=3)
            y += 35

        return frame
