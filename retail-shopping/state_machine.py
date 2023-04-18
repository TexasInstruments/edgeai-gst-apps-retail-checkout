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

import  time
from enum import Enum
from queue import deque

import utils

class States(Enum):
    IDLE_NO_FOODS = 1
    DETECTED_FOODS = 2
    STABILIZE_FOOD_LIST = 3
    CREATE_RECEIPT = 6
    AWAIT_PAYMENT = 4
    NEXT_CUSTOMER = 5
    
class Colors(Enum):
    
    ''' assume these are RGB'''
    BLACK = (0,0,0)
    RED = (255, 0, 0)
    YELLOW = (255, 255, 0)
    GREEN = (32, 128, 0)

class RetailAppFSM(): 
    '''
    While AI acceleration, the object detection models run >60 fps and camera at least 30fps. 
    Changing text drawn to the screen too quickly is confusing and glitchy. 
    
    This state machine is intended to smooth this over and insert simple app logic
    and text to give user directions on the screen. 

    Drawing text to the screen is a slow and variable-latency task/call. This FSM
    also reduces how after this is done to improve average FPS.

    '''
    PAYMENT_STATE_DURATION_SECONDS = 3.5
    WAIT_FOR_NEXT_CUSTOMER_STATE_DURATION_SECONDS = 2.5
    NUM_FRAMES_TO_STABILIZE = 15
    ITEMS_CONTINUITY_THRESH = 0.5
    MAX_LAST_ITEMS_MEMORY = 5

    def __init__(self, model_params, display_drawer):

        #state variables
        self.state = States.IDLE_NO_FOODS
        self.item_stabilize_counter = 0
        self.last_items_deque = deque()
        self.last_items = utils.create_empty_item_list(utils.get_categories())
        self.last_frame = None

        self.timer_start = 0
        self.model_params = model_params
        self.model_height = self.model_params['preprocess']['crop'][0]
        self.model_width = self.model_params['preprocess']['crop'][1]

        # display drawer creates the receipt image and pushes to GST
        self.display_drawer = display_drawer


    def run_fsm(self, items):
        '''
        Run the FSM on a new set of items

        param items: dictionary of recognizable items and how many were recognized

        Returns an image that can be pushed to the display
        '''
        out_text_receipt_color = None
        out_text_receipt_text = None
        out_items = items
        out_receipt_image = None
        

        if self.state == States.IDLE_NO_FOODS:
            # no foods are recognized
            out_text_receipt_color = Colors.BLACK
            out_text_receipt_text = 'Awaiting New Customer'
            out_receipt_image = self.display_drawer.draw_extra_text(self.display_drawer.list_image_headers_only.copy(), out_text_receipt_text, out_text_receipt_color.value)


            if utils.count_items(items) > 0:
                self.state = States.DETECTED_FOODS
            else: 
                self.state = States.IDLE_NO_FOODS
        
        elif self.state == States.DETECTED_FOODS:
            # some foods are detected
            out_text_receipt_color = Colors.BLACK
            out_text_receipt_text = 'Hello!\nPlease hold tray still'
            out_receipt_image = self.display_drawer.draw_extra_text(self.display_drawer.list_image_headers_only.copy(), out_text_receipt_text, out_text_receipt_color.value)

            if utils.count_items(items) == 0:
                self.state = States.IDLE_NO_FOODS
            elif self.filter_items_list(items):
                self.state = States.STABILIZE_FOOD_LIST
                self.item_stabilize_counter = 0
            else:
                self.state = States.DETECTED_FOODS
        
        elif self.state == States.STABILIZE_FOOD_LIST:
            # stay in this state while the list of foods stabilizes so we're certain of the order
            out_text_receipt_color = Colors.BLACK
            out_text_receipt_text = 'Hello!\nPlease hold tray still'
            out_receipt_image = self.display_drawer.draw_extra_text(self.display_drawer.list_image_headers_only.copy(), out_text_receipt_text, out_text_receipt_color.value)

            if utils.count_items(items) == 0:
                self.state = States.IDLE_NO_FOODS
            elif self.filter_items_list(items):
                if self.item_stabilize_counter > RetailAppFSM.NUM_FRAMES_TO_STABILIZE:
                    self.state = States.CREATE_RECEIPT
                    self.item_stabilize_counter = 0
                    self.timer_start = time.time() # save time for running a timer
                else: 
                    self.state = States.STABILIZE_FOOD_LIST
                    self.item_stabilize_counter += 1
            
            else: 
                self.state = States.DETECTED_FOODS
                self.item_stabilize_counter = 0
                    
        elif self.state == States.CREATE_RECEIPT:
            # Create the receipt image with all the recognized foods
            out_text_receipt_text = 'Your Order is Finalized!'
            out_text_receipt_color = Colors.BLACK
            
            # slow function call, intentially run only once 
            out_receipt_image = self.display_drawer.fill_receipt_image(items, self.display_drawer.list_image.copy())

            # hold onto this frame. New "extra text" for user directions will be added later
            self.last_frame = out_receipt_image

            #write next set of directions/user feedback
            out_receipt_image = self.display_drawer.draw_extra_text(self.last_frame.copy(), out_text_receipt_text, out_text_receipt_color.value)

            self.state = States.AWAIT_PAYMENT


        elif self.state == States.AWAIT_PAYMENT:
            out_text_receipt_color = Colors.RED
            out_text_receipt_text = 'Your Order is Finalized!\nPlease Provide Payment'
            out_items = self.last_items
            
            #reuse last frame and draw new user feedback text
            out_receipt_image = self.display_drawer.draw_extra_text(self.last_frame.copy(), out_text_receipt_text, out_text_receipt_color.value)

            
            current_time = time.time()
            #check timer started in STABILIZE_FOOD_LIST
            if (current_time - self.timer_start) > RetailAppFSM.PAYMENT_STATE_DURATION_SECONDS:
                self.state = States.NEXT_CUSTOMER
                self.timer_start = current_time
            else:
                self.state = States.AWAIT_PAYMENT
        
        elif self.state == States.NEXT_CUSTOMER:
            out_text_receipt_color = Colors.GREEN
            out_text_receipt_text = 'Payment Received.\nHave a Nice Day!'            
            out_items = self.last_items
            out_receipt_image = self.display_drawer.draw_extra_text(self.last_frame.copy(), out_text_receipt_text, out_text_receipt_color.value)

            current_time = time.time()
            #check timer started in AWAIT_PAYMENT
            if (current_time - self.timer_start) > RetailAppFSM.WAIT_FOR_NEXT_CUSTOMER_STATE_DURATION_SECONDS:
                self.state = States.IDLE_NO_FOODS
                self.timer_start = 0
                if utils.count_items(items) > 0:
                    self.state = States.DETECTED_FOODS
                else: 
                    self.state = States.IDLE_NO_FOODS
            else: 
                self.state = States.NEXT_CUSTOMER
        
        else: 
            raise ValueError("Unrecognized state: " + str(self.state))

        self.last_items = out_items
        
        return out_receipt_image
    
    def filter_items_list(self, new_items):
        '''
        Items may not be correctly recognized every frame. Operate a psuedo-lowpass 
        filter

        Maintains a Queue (as deque, for easier peeking and manipulation)

        return True if items are similar enough to past iteration(s)
        '''        
        is_new_items_in_list = False
        count_same = 0

        # if empty, assume true
        if len(self.last_items_deque) == 0: 
            self.last_items_deque.append(new_items)
            return True
        
        # count number of perfect matches between lists. Should not consider where
        #   item is in the image
        for items in list(self.last_items_deque):
            if items == new_items:
                count_same += 1
              
        # compare percentage of matches to threshold for required consistency/continuity between frames
        if count_same / len(self.last_items_deque) >= RetailAppFSM.ITEMS_CONTINUITY_THRESH:
            is_new_items_in_list = True

        # add newest to the list
        self.last_items_deque.append(new_items)

        # maintain max size of the data storage
        while len(self.last_items_deque) >= RetailAppFSM.MAX_LAST_ITEMS_MEMORY:
            self.last_items_deque.popleft()


        return is_new_items_in_list