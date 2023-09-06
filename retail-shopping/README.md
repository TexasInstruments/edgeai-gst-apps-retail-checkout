# Retail Shopping Demo README

This is the Retail Automation demo on AM62A Processor, which was used at Embedded World 2023 to showcase this new SoC. The demo is release specific, although changes are minimal. Ensure the git commit tag's version matches the SDK version. 

## How to run this demo

Run [run_demo.sh](./run_demo.sh) to run this demo. 

This demo runs on the AM62A Starter-Kit EVM. It requires a 1920x1080 HDMI display and a camera. The camera can be a 720p/1080p USB camera or an IMX219 module with CSI connection. Copy the files within this directory (and subdirectories) to the device - it is not important where within the device's file system. 

The run_demo.sh script assumes a 1080p USB camera is connected and that the model to use for inference is at [food-detection-model-mobv2ssd](./food-detection-model-mobv2ssd). If the trained food recognition neural network is not already present at food-detection-model-mobv2ssd, it will be downloaded. **The base python file is retail_vision_app.py. The -h tag will print the full readout for command-line options**. Additional CLI tags can be added to the run_demo.sh call, which will be passed on to the python command. These command line options allow users to select the camera (type and device location), model file location, etc.

Note that using the IMX219 or another CSI camera requires the camera to be enabled via a device tree overlay (DTBO file). Add ti/k3-am62a7-sk-csi2-imx219.dtbo to name_overlays at /run/media/BOOT-mmcblk1p1/uEnv.txt to enable this.

![](./doc/demo-at-EW.gif)


## What is this demo?

This application was developed using edgeai-gst-apps as a starting point for a smart retail demo. Foods are recognized with deep learning to fill a customer's order quickly and autonomously. Images are captured, preprocessed, inferenced using a custom-trained neural network, and are displayed to the screen with text emulating a receipt readout.

This application was developed for the AM62A, a quad-core microprocessor from Texas Instruments with 2 TOPS of deep learning acceleration, integrated ISP, and video codec. The food-recognition neural network is compiled for this deep learning accelerator. If using a different TI Edge AI Processor, the neural network will need to be recompiled. See [TI's Edge AI repo](https://github.com/TexasInstruments/edgeai/blob/master/readme_models.md) and [edgeai-tidl-tools](https://github.com/TexasInstruments/edgeai-tidl-tools) to learn more about this process.

This demo is written in Python3 and leverages the ONNX runtime with TIDL Execution Provider to utilize the deep learning engine. It uses gstreamer with TI's custom plugins for accessing hardware accelerators within the SoC as well as OpenCV for additional image processing. The IMX219 is supported as a raw camera input sensor, as are 1080p and 720p USB cameras (logitech c920 and c270, respectively). Output is displayed to an HDMI screen, and 1920x1080 resolution is assumed. 

### Help! The Demo isn't Running!

See the [FAQ](./doc/FAQ.md) 

### Reproducing the demo in full 

See the [guide on reproducing the demo](./doc/REPRODUCE.md) to find all compoents used in the making and displaying of this demo, including the food items the model was trained to recognize as well as mounting hardware.


## Demo Development

To learn more about how this demo was made, please see [HOW_ITS_MADE.md](./doc/HOW_ITS_MADE.md)