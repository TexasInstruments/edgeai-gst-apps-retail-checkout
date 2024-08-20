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

import os, sys, time
import yaml, json

def get_categories():
    '''
    Get the set of categories from a COCO format JSON file. 
    It is assumed there is a categories.json file in the calling directory.
    '''
    categories = json.load(open('categories.json', 'r'))['categories']
    return categories

def create_empty_item_list(categories):
    '''
    Create an empty list (technically dict) for storing information about the items detected
    '''
    items = {item['name']:{"num":0, "cost":item["cost"], "row":item['id']} for item in categories}
    
    return items

def count_items(items):
    '''
    Count the number of items detected

    Returns the number of items detected per the list supplied. 
    '''

    num_items = 0
    for i in items.keys():
        num_items += items[i]['num']
        
    return num_items

def get_items_from_tensors(output_boxes_tensor, output_classes_tensor, classes):
    '''
    Extract the set of classes recognized from the tensors.

    The tensor formats below are specific to mobilenetv2SSD.
    
    param output_boxes_tensor: a N by 5 float32 tensor. first 4 values are box coordinates, 5th is a confidence [0,1)
    param output_classes_tensor: a N by 1 float32 tensor. Values are class indices, and should be integers
    param classes: the set of classes as read from the get_categories() function

    Returns a dictionary of items with item names, costs, and number of the item type found.
    '''
    items = create_empty_item_list(classes)
    conf_thresh = 0.6

    for i, out in enumerate(output_boxes_tensor):
        conf = out[-1]
        if conf > conf_thresh:
            try:     
                cls_index = output_classes_tensor[i] 
                class_name = classes[int(cls_index)]['name']
                items[class_name]['num'] += 1  
            except: pass
    return items