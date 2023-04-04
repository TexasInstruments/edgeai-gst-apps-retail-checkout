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

import os
import onnxruntime
import tflite_runtime.interpreter as tfl

import cv2 as cv
import yaml

onnxruntime.set_default_logger_severity(3) #suppress some warnings that the logger prints

class ModelRunner():
    def __init__(self, modeldir, paramsfile=None, modelfile=None, tensor_class_offset=4096):
        self.modeldir = modeldir

        if not paramsfile or not os.path.exists(paramsfile):
            self.params = yaml.safe_load(open(os.path.join(modeldir, 'param.yaml'), 'r'))
        else:
            self.params = yaml.safe_load(open(paramsfile, 'r'))

        if not modelfile or not os.path.exists(modelfile):
            self.modelfile = os.path.join(modeldir, 'model', 'model.onnx')
        elif self.params['session']['model_path']:
            self.modelfile = os.path.join(modeldir, self.params['session']['model_path'])
        else: 
            self.modelfile = os.path.join(modeldir, modelfile)


        self.model_width, self.model_height = self.params['preprocess']['resize']
        self.tensor_class_offset = tensor_class_offset

    def load_model(self):
        ext = self.modelfile.split('.')[-1]

        if 'onnx' in ext:
            self.model_type = 'onnx'

            sess_options = onnxruntime.SessionOptions()
            ep_list = ['CPUExecutionProvider']
            provider_options = [{}]

            self.model = onnxruntime.InferenceSession(self.modelfile, providers=ep_list, provider_options=provider_options, sess_options=sess_options)
            self.input_details = self.model.get_inputs()

            i = self.input_details[0]
            self.input_type = i.type.split('(')[-1][:-1] #format of type is "tensor($TYPE)", e.g. "tensor(uint8)"
            if self.input_type == 'float':
                self.input_type = 'float32'

        elif 'tflite' in ext:
            self.model_type = 'tflite'

            raise NotImplementedError()

    def run_onnx(self, input_tensor):
        result = self.model.run(None, {self.input_details[0].name: input_tensor}) #format depends on model. mobilenetv2SSD

        return result
