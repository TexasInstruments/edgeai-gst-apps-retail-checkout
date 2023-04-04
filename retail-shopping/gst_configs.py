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

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GstApp, GLib, GObject
Gst.init(None)


class CamParams():

    def __init__(self, cam_name, device='/dev/video2'):
        if cam_name == 'imx219': 
            self.width = 1640
            self.height = 1232
            self.draw_image_width = 1440
            self.draw_image_height = 1080
            self.fps = '30/1'
            self.pixel_format = 'RGB'

            self.input_gst_str = f'v4l2src device={device}  io-mode=dmabuf-import ! video/x-bayer, width={self.width}, height={self.height}, format=rggb10 ! tiovxisp sink_0::device=/dev/v4l-subdev2 sensor-name=SENSOR_SONY_IMX219_RPI dcc-isp-file=/opt/imaging/imx219/dcc_viss_10b_1640x1232.bin sink_0::dcc-2a-file=/opt/imaging/imx219/dcc_2a_10b_1640x1232.bin format-msb=9 ' 

            # c280 webcam settings
        elif cam_name=='usb-720':
            self.width = 1280
            self.height = 720
            self.draw_image_width = 960
            self.draw_image_height = 720 
            self.fps = '30/1'
            self.pixel_format = 'RGB'

            self.input_gst_str = f'v4l2src device={device}  ! image/jpeg,width={self.width},height={self.height} ! jpegdec '
            
        elif cam_name=='usb-1080':
            self.width = 1920
            self.height = 1080
            self.draw_image_width = 1440
            self.draw_image_height = 1080 
            self.fps = '30/1'
            self.pixel_format = 'RGB'

            self.input_gst_str = f'v4l2src device={device}  ! image/jpeg,width={self.width},height={self.height} ! jpegdec '
        else: 
            raise ValueError('cam_name not recognized: ' + cam_name)


class GstBuilder():
    def __init__(self, model_params, camera_params, appsink_tensor_name='tensor_in', appsink_image_name='image_in', appsrc_name='out', preprocess=True, display_dims=(1920,1080), receipt_dims=(480, 1080), image_dims=(1440, 1080)):
        '''
        GST pipeline builder class. Requires information about the input, model, and output. Dimensions are all (width, height)
        '''
        self.model_params = model_params
        self.camera_params = camera_params

        self.appsink_tensor_name = appsink_tensor_name
        self.appsink_image_name = appsink_image_name
        self.appsrc_name = appsrc_name

        self.appsrc_output_format = 'RGB'
        
        self.preprocess = preprocess
        self.display_width  = display_dims[0]
        self.display_height = display_dims[1]

        if receipt_dims and image_dims:
            #check that the dimensions add up to the full display
            assert receipt_dims[0] + image_dims[0] == display_dims[0] and \
                receipt_dims[1] == image_dims[1] == display_dims[1]
            self.receipt_width, self.receipt_height = receipt_dims
            self.image_width, self.image_height = image_dims


    def build_gst_strings(self, model_obj):
        '''
        Build a GST string that pulls input, preprocesses, runs inference, post 
        processing, exposes interface to application code, and merges app output 
        with postproc output for display.

        param model_obj: Holds information about the model object, primarily 
        data type. Most parameters instead come from self.model_params, 
        which is set in __init__
        '''
    
        video_conv = 'tiovxdlcolorconvert' # videoconvert # tiovxdlcolorconvert #tiovxdl are Neon optimized
        
        model_width, model_height = self.model_params['preprocess']['resize']

        # input from camera and get ready to split into two 
        gst_str = self.camera_params.input_gst_str 
        gst_str+= f'! {video_conv}  !  video/x-raw, format=NV12 ! tiovxmultiscaler name=split_resize  ' 
        
        tensor_format=self.model_params['preprocess']['data_layout']
        data_type = model_obj.input_type
        
        # pipeline to do DL inference on. Requires preprocessing to match model
        gst_str+= f' split_resize. ! video/x-raw, width={model_width}, height={model_height}, format=NV12  '
        gst_str += f' ! tiovxdlpreproc data-type=uint8 ! application/x-tensor-tiovx,  channel-order={tensor_format}, tensor-format=RGB, tensor-width={model_width}, tensor-height={model_height} '
        
        if self.preprocess or data_type == 'float32':
            # subtract mean and multiply by scale in the tiovxdlpreproc
            params_mean = self.model_params['session']['input_mean']
            params_scale = self.model_params['session']['input_scale'] 
            preproc_param_str = ' mean-0=%f mean-1=%f mean-2=%f scale-0=%f scale-1=%f scale-2=%f ' % (params_mean[0], params_mean[1], params_mean[2], params_scale[0], params_scale[1], params_scale[2])
            gst_str += preproc_param_str
            
        #run inference and split at tensor output
        gst_str += f' ! tidlinferer model={model_obj.modeldir} ! tee name=model_out_tensor  '

        # Enqueue and postprocess the tensor on the original images so boxes are drawn
        gst_str += f' model_out_tensor. ! queue max-size-buffers=2 leaky=2 ! postproc.tensor '
        gst_str += f' split_resize. ! video/x-raw, width={self.camera_params.draw_image_width}, height={self.camera_params.draw_image_height}, format=NV12 ! postproc.sink  tidlpostproc name=postproc model={model_obj.modeldir}  ! queue leaky=2 max-size-buffers=1 name=queue-mosaicsink0 ! mosaic.sink_0'

        # Provide the tensor to application code via appsink
        gst_str += f' model_out_tensor. ! queue name=queue-tensor-in leaky=2 max-size-buffers=1 ! appsink name={self.appsink_tensor_name} max-buffers=1 drop=true sync=false  '
        # gst_str += f' model_out_tensor. ! appsink name={self.appsink_tensor_name} max-buffers=1 drop=true sync=false  '

        # Application output (the receipt iamge) will come from appsrc and go to mosaic
        gst_str += f' appsrc format=GST_FORMAT_TIME is-live=true block=false  name={self.appsrc_name} ! video/x-raw,  format={self.appsrc_output_format}, width={self.receipt_width}, height={self.receipt_height} ! {video_conv} ! video/x-raw, format=NV12  '

        gst_str += f' ! queue name=queue-mosaicsink1 leaky=2 max-size-buffers=1 ! mosaic.sink_1 ' 

        # Create a mosaic to stitch together images from postproc and appsrc
        gst_str += f'  tiovxmosaic name=mosaic '
        gst_str += f'  sink_0::startx="<0>" sink_0::starty="<0>" sink_0::heights="<{self.image_height}>" sink_0::widths="<{self.image_width}>"'
        gst_str += f'  sink_1::startx="<{self.image_width}>" sink_1::starty="<0>" sink_1::heights="<{self.receipt_height}>" sink_1::widths="<{self.receipt_width}>"' 
        gst_str += f' ! kmssink sync=false driver-name=tidss'


        self.gst_str = gst_str

        # define output caps for the receipt image coming from appsrc
        self.gst_caps = Gst.caps_from_string("video/x-raw, " + \
            "width=%d, " % self.receipt_width + \
            "height=%d, " % self.receipt_height + \
            "format=%s, " % self.appsrc_output_format + \
            "framerate=%s" % '0/1')

        return gst_str
    

    def setup_gst_appsrcsink(self):
        '''
        Parse the GST pipeline string and launch. 
        Retrieve application interfaces (appsink input, appsrc output) 
        '''


        print('Parsing GST pipeline: \n%s\n' % self.gst_str)


        self.pipe = Gst.parse_launch(self.gst_str)

        self.app_in_tensor = self.pipe.get_by_name(self.appsink_tensor_name)
        self.app_out = self.pipe.get_by_name(self.appsrc_name)


    def start_gst(self):
        '''
        Set the GST pipeline to start playing
        '''
        print('Starting GST pipeline')
        s = self.pipe.set_state(Gst.State.PLAYING)
        print(s)

    def pull_sample(self, app, loop=True):
        '''
        Retrieve a sample from the appsink 'app' and return a buffer of data.
        The pipeline and appsink instance must be PLAYING state

        param app: The appsink obtained from a valid pipeline
        '''
        data = None
        struct = None
        sample = app.try_pull_sample(50000000)
    
        if type(sample) != Gst.Sample:
            # Poll endlessly for a sample
            if loop:
                while type(sample) != Gst.Sample:
                    sample = app.try_pull_sample(50000000)

        if type(sample) == Gst.Sample:
            buffer = sample.get_buffer()
            _, map_info = buffer.map(Gst.MapFlags.READ)
            # the buffer of data
            data = map_info.data
            # release the sample and map to GST memory
            buffer.unmap(map_info)
            
            # get caps to help learn about input structure
            appsink_caps = sample.get_caps()
            struct = appsink_caps.get_structure(0)

        return data, struct