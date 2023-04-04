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

import os, time
from pprint import pprint
import numpy as np
import yaml
import threading
import argparse
import math

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GstApp, GLib, GObject
Gst.init(None)

import gst_configs, model_runner, display, utils, state_machine

# global variables to help control the GST thread
stop_threads = False
infer_thread = None


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--camera', default='imx219', help='name of camera device to use. options are usb-720p from logitech, usb-1080p (c920 or c922 from logitech), and IMX219 (RPi cam v2)')
    parser.add_argument('-m', '--modeldir', default='./model/', help='location of the model directory. Assumed to have dataset.yaml, param.yaml, model as model.onnx, and subdir for artifacts. See typical format of directories from /opt/model_zoo for example')
    parser.add_argument('-d', '--device', default='/dev/video2', help="location of the camera device under /dev")
    
    parser.add_argument('-l', '--list-receipt-full', action='store_true', dest='list_receipt_full', help='print all types of items in the list receipt rather than only the ones recognized')
    parser.add_argument('-nl', '--list-receipt-short', action='store_false', dest='list_receipt_full', help='display only the items recognized in the receipt image')
    parser.set_defaults(list_receipt_full=False)

    args = parser.parse_args()
    pprint(args)
    
    return args


def application_thread(gst_conf:gst_configs.GstBuilder, model_obj:model_runner.ModelRunner, drawer:display.DisplayDrawer, args):
    '''
    This is where all the appsrc/appsink code lies
    '''
    fsm = state_machine.RetailAppFSM(model_obj.params, drawer)

    if not hasattr(gst_conf, 'gst_str'): gst_conf.build_gst_strings(model_obj)

    print('Starting with in_gst: \n%s\n' % gst_conf.gst_str)
    gst_conf.start_gst()
    
    #we'll collect some statistics on where time is spent in the application
    stats = {'count':0, 'total_pre_stage_s':0, 'total_output_stage_s':0, 'total_pre_stage_sq':0, 'total_output_stage_sq':0}

    #run to init
    receipt_image = fsm.run_fsm(utils.create_empty_item_list(drawer.classes))
    print(receipt_image.shape)


    global stop_threads
    while not stop_threads:

        #push an image from the last iteration first so we're able to create the display output immediately
        drawer.push_to_display(receipt_image)
        print('pull')
        t_start_loop = time.time()
        sample_tensor, _ = gst_conf.pull_sample(gst_conf.app_in_tensor, loop=True)
        if not sample_tensor: continue

        print('got sample tensor')
        # tensor is the output of dlinferer. If so, format is model dependent. View tidlpostproc and tidlinferer to  see how this structure is encoded into a buffer. If there are multiple tensors, there will be offsets. Values below are specific to mobilvenetv2SSD-lite 
        t_pre_draw = time.time()

        #decode the tensor
        num_boxes = 200
        len_boxes_tensor = num_boxes*5*4 #5-tuple of float32's
        boxes_data = sample_tensor[0:len_boxes_tensor]
        boxes_tensor = np.ndarray((num_boxes, 5), np.float32, boxes_data)

        len_classes_tensor = num_boxes*1*8 #1-tuple of int64's
        #there is an offset for the start of the next tensor. This was found by printf's in postproc plugin
        classes_data = sample_tensor[model_obj.tensor_class_offset:model_obj.tensor_class_offset+len_classes_tensor]
        classes_tensor = np.ndarray(len(classes_data)//8, np.int64, classes_data)

        #extract a list of items from the tensors
        items = utils.get_items_from_tensors(boxes_tensor, classes_tensor, categories)
        # pprint(items) #pprint has terrible performance. Showing a dict can  take 50+ ms. Only for debug

        # create the receipt image - output from an FSM
        receipt_image = fsm.run_fsm(items)
        t_final = time.time()
        
        #collect some stats    
        stats['count'] += 1
        stats['total_pre_stage_s'] += t_pre_draw - t_start_loop
        stats['total_pre_stage_sq'] += (t_pre_draw - t_start_loop)**2
        stats['total_output_stage_s'] += t_final - t_pre_draw
        stats['total_output_stage_sq'] += (t_final - t_pre_draw)**2

    # raises an error if stopped before an iteration of inference completed
    print('\nRan %i frames' % stats['count'])
    mean_inf = stats['total_pre_stage_s'] / stats['count']
    mean_out = stats['total_output_stage_s'] / stats['count']
    std_inf = math.sqrt(stats['total_pre_stage_sq'] / stats['count'] - mean_inf**2)
    std_out = math.sqrt(stats['total_output_stage_sq'] / stats['count'] - mean_out**2)
    print('Pulling input time (ms): avg %d +- %d' % (mean_inf*1000, std_inf*1000))
    print('Output (draw, post-proc) time (ms): avg %d +- %d' % (mean_out*1000, std_out*1000))


if __name__ == '__main__':
    args = parse_args()
    
    # camera parameters and information assumed based on device in CLI args
    cam_params = gst_configs.CamParams(args.camera, device=args.device)

    #load model's params'yaml file
    modeldir = args.modeldir
    paramsfile = os.path.join(modeldir, 'param.yaml')
    model_params = yaml.safe_load(open(paramsfile, 'r'))

    #the set of classes/categories recognized by the model
    categories = utils.get_categories()

    # setup the model for inference. Parameters used by gst_config
    model_obj = model_runner.ModelRunner(modeldir, paramsfile=paramsfile, tensor_class_offset=4096)
    model_obj.load_model() #load model to get info about input data type
    
    #create the gstreamer pipeline based on model and camera parameters
    gst_conf = gst_configs.GstBuilder(model_params, cam_params, preprocess=False, display_dims=(1920,1080), receipt_dims=(480, 1080), image_dims=(1440,1080)) 
    gst_conf.build_gst_strings(model_obj)
    # start the pipeline and saves references to appsrc/appsink
    gst_conf.setup_gst_appsrcsink()
    
    # Use for pushing information to the display. Assuming 1920x1080p display
    display_width = 1920
    display_height = 1080
    print(int(display_width*1/4))
    drawer = display.DisplayDrawer(display_width, display_height, int(display_width*1/4), display_height, int(display_width*3/4), display_height, gst_conf.app_out, categories, gst_conf.gst_caps, list_receipt_full=args.list_receipt_full)

    # fork into an application thread to make KB interrupts easier to catch
    app_thread = threading.Thread(target=application_thread, args=[gst_conf, model_obj, drawer, args])
    app_thread.start()

    try: 
        while not stop_threads:
            pass
    except KeyboardInterrupt:
        print('KB shortcut caught')
        stop_threads = True

    gst_conf.pipe.set_state(Gst.State.PAUSED)
