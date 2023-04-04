# Development of the Retail Automation Demo

This Readme is designated to explaining the design and implementation of this application.

It is assumed that those following this guide and attempting to reproduce have moderate familiarity with bash scripts/linux, python, and machine learning fundamentals. This guide goes a step deeper than the surface level how-it's-done to explain more about the underlying tools -- it is intentionally verbose.


## 1. Creating the Dataset

The first step of model creation is to create/curate a dataset. Without good data, one cannot have a good model. Searching online for premade and annotated datasets to recognize a collection of foods yielded few usable datasets. Most were created by pooling images from online searches or from larger research databases composed of images taken in restaurants. Most images were either low quality, did not show the items of interest, or had so much variation (and low # of images) that a model was unlikley to train well. Given 2 weeks effort to curate a dataset built from multiple others, model quality was extremely poor, and this approach was scrapped.

To have reproducible results, the best method was to collect images in the same setting that foods would be recognized in: bright lighting, overhead camera, consistent set of objects (foods like banana, orange, bowl of rice, etc.). See the image below for an example of one of the images. Most of these food items are realistic fakes to maintain consistency such that a smaller dataset is usable for training and the results reproducible in the future. 

<img src=./image-from-dataset.jpg width=500>

The dataset can be downloaded using the [download_food_dataset.sh script](../download_food_dataset.sh). This should be done on the host instead of the EVM, as the [data_manipulation.py](../model-creation/data_manipulation.py) script is meant to run on an host Linux machine.

Approimately 350 images were collected and manually labeled for the dataset (see categories.json for the list). Each image had multiple food items within it, and there are at least 100 instances of each object. To improve robustness to small variations in the environment like lighting, camera angle, lens parameters, etc., the camera was moved to different positions and orientations, and additional lighting was added to produce shadows, reflections, etc. Some real versions of food were added in, like bananas, apples, and oranges. Around 100 "null" images were also added of random scenes and empty trays/food area to provide more false instances; this is also to improve robustness. The downloaded dataset does not include the null images.

Images were manually labelled in [label-studio](https://labelstud.io/), a software that provides a GUI for annotating data for machine learning tasks, particularly image processing. The output ZIP archive contains a directory of images and a JSON file in COCO format for describing the bounding boxes and classes. 

A dataset of 350 labelled images is fairly small for training deep learning, even if it's post-training on a pretrained network (in this case the full COCO dataset). To improve robustness and artifically expand the dataset, we use image augmentation. This makes multiple copies of an original image, but applies transformations to add noise, rotations, stretching/shearing, zoom/shrink, and other filters. In the final version of the model, the dataset was expanded by a factor of 8. A test-train split of 20/80 was done *before* image augmentation to avoid corrupting the testing set. 

The set of augmentations (using imaug python3 library) are in the following list, and an example of an augmented image is below. Note that not all augmentations are performed on each image - a set of them is randomly selected and applied with randomized parameters. These are chosen to match potential effects that may be experienced in practice. See [data_manipulation.py](../model-creation/data_manipulation.py) to see the Python code used.

  *  Flip left-right
  *  Flip up-down
  *  Shear
  *  Perspective Transform
  *  Gaussian Blur
  *  Gaussian Noise
  *  Motion Blur
  *  Contrast
  *  Add Saturation
  *  JPEG Compression
  *  Rotation +- 90 degrees
  *  Autocontrast
  *  Gamma contrast
  *  Sharpen
  *  Multiply Hue and Saturation
  *  Change Color Temperature

The imgaug library will maintain these bounding boxes, even with rotations and other transformations so that relabeling is not required.

<img src=./augmented-image.jpg width=500>

Performing these augmentations did require manual manipulation of the COCO-format JSON file to add in the new entries. This is also included in the data_manipulation.py script.


## 2. Selecting the model

The next step was to select which model to use for this object detection task. 

To get the most performance out of the hardware accelerator, every layer within the network must be supported within the deep learning accelerator. Models from the [TI model zoo](https://github.com/TexasInstruments/edgeai-modelzoo/) fit this requirement. This project was intended for AM62A; a limited set of models was available at the initial launch of this processor. 

For a new SoC (at the time), the models supported was changing rapidly, but after some sleuthing, we discovered the [download_models.sh script in edgeai-gst-apps](https://github.com/TexasInstruments/edgeai-gst-apps/blob/main/download_models.sh) pulled from a CSV file that listed the currently downloadable models. We selected "od-8020_onnxrt_coco_edgeai-mmdet_ssd_mobilenetv2_lite_512x512_20201214_model_onnx", which the CSV listed as "recommended" given it's accuracy vs. performance (in FPS) and full layer support. This model will act as the starting point for retraining. From the model name, we can learn a few things:

  * It is for Object Detection (od). 
     * "8020" is a unique number to distinguish models for faster reference when working with many. There is not much significance in this value
  * ONNX runtime is the runtime/APIs to use for this running neural network
  * The original version was trained on the COCO dataset, which contains 80+ everyday objects like people, automobiles, bananas(!), home appliances, etc.
  * The training framework was edgeai-mmdetection
  * The model architecture is based on MobilenetV2 (backbone/spine) with single-shot detection (SSD) head
  * "lite" means it was slightly modified from the original architecture to be friendlier to TI's accelerator architecture
  * Input images are 512x512 resolution


## 3. Training the model

The next step is to train the selected model on this new dataset. 

In theory, any training framework should be usable. The model can then be brought back to TI's tool for compilation. For simiplicity, we used the [edgeai-modelmaker](https://github.com/TexasInstruments/edgeai-modelmaker) tool. Note that in 2Q 2023, TI is releasing a cloud-based, no-code tool for labeling, training, compiling, and evaluating models. The training stage uses edgeai-modelmaker as the backend. For the actual training of models, one of several frameworks will be used. For this model, it was edgeai-mmdetection, which is a fork of mmdetection from OpenMMLab. This references torchvision in Python.

To train the model, the steps are to: 

  * Setup the modelmaker repository, which includes setting up other training frameworks and TI tools. They will be held in the same parent directory. There is a setup_all.sh script in the edgeai-modelmaker repo that will handle this installation. 
  * Place the files for training into edgeai-modelmaker/data/projects/PROJECT_NAME. Run one of the examples to see the structure of these directories
  * Create a config file that points to the right data, selects the model, training parameters, etc. See [config_detect_foods.yaml](../model-creation/config_detect_foods.yaml) for the configuration used to train this model. Use the PROJECT_NAME for the project-name. Training files will then be in that directory under 'run' within that PROJECT_NAME directory
  * Run the run_modelmaker.sh script using the config file above as the first and only argument. 
    * Note that AM62A requires different compilation tools from the default -- those were downloaded separately and the run_modelmaker.sh script was modified to use that path for env variable "TIDL_TOOLS_PATH". 
    * If edgeai-tidl-tools was setup with AM62A already, then it should not be necessary to modify this environment variable. 

If a GPU is present, make sure that is referenced in the config file by setting the number of GPUs (or setting to zero if there is none). It is important that the driver/CUDA version matches against the torchvision install. The one shipped with modelmaker is CUDA 11.3. Unfortunately, setting this up can be a pain-point, but getting it setup is worth the increase in speed if a GPU is present. 

For the several thousand image dataset with 30 epochs, running on NVIDIA A2000 GPU took 1.5 hours. Running on CPU would likely take >1 day.

It was noted that the directory with images needs to be flat (no subdirectories), even if the image path in the json file uses a valid path (relative or absolute). There should just be an "annotations" and "images" directory under your project folder within "projects". 

An additional optimization (which is loosely documented at time of writing) is "input_optimization". Floating point models often try to center values around 1 to keep exponents consistent and ease quanitzation later. On the input (typically 8-bit ints for R, G, B on each pixel), a mean is subtracted and multiplied by a scaling factor to reach this value range. Input_optimization is a technique to fold these add and multiply operations into the network itself. This keeps the input into the deep learning accelerator smaller than 32-bit floats and reduces computations done on the less-efficient CPU. This is not crucial, but is helpful for later. This step can be done at any point, and modelmaker includes this convenience.

On this dataset, the validation phase showed mean average precision (mAP, a common metric for object detection networks) at 0.68. mAP-50 (50% or greater similarity between labelled box and detected box) is 0.97. This is extremely high, and largely results from the stability of the environment. See the [COCO leaderboards](https://cocodataset.org/#detection-leaderboard) for the extremely large COCO dataset - current leaders are around 0.58. We'll call that a successful model! However, a better test would be to use the designated training set, since modelmaker will do a training-validation split automatically, which both contain augmented versions of the same image.


## 4. Compiling the model

Compilation can be done within the previous step when using modelmaker. If not using TI's training framework, the model needs to be compiled on its own. [edgeai-tidl-tools](https://github.com/TexasInstruments/edgeai-tidl-tools) will serve this purpose. This must run on an x86 host computer.

There are several ways to compile a model within edgeai-tidl-tools, including using a Jupyter notebook and using python scripts; this can be done on your machine (running Linux like ubuntu 18.04 LTS) or TI's [Edge AI Cloud](https://dev.ti.com/edgeaisession/). View the [docs on custom model compilation](https://github.com/TexasInstruments/edgeai-tidl-tools/blob/master/docs/custom_model_evaluation.md) for more information.

The flow is to run a set of images through the runtime of your model (ONNX, based on the one selected). As this is run, it will generate "artifacts" in the form of compiled files for running the model on the deep learning accelerator (DLA). This includes an "io" file for how CPUs pass information to/from the DLA and a "net" file which encodes the network layers itself. In this process, the set of images are used to calibrate the quantization from native 32-bit floating points to fixed-point integers (8 or 16-bit). Using a larger set of images to be encountered in practice will improve the quality of this quantization, but will take longer. 

The calibration images need to be preprocessed to match what the network expects, e.g. RGB in planar format as float32's with mean subtracted and multiplied by a scaling factor. Looking at the examples/jupyter_notebooks/custom_model_onnx.ipynb, there is a preprocessing function for resnet18. 

*  **NB:** We found that Jupyter's kernel does fail more often on certain models, and was not found to work well for mobilenetv2SSD compilation without crashing. Jupyter's kernel fails more frequently on long running or highly intensive tasks.

The script examples/osrt_python/ort/onnxrt-ep.py was easier to use because it will handles this preprocessing automatically, but is less clear on what is happening with preprocessing, configuration, etc. Using this required a few changes for compilation to complete:

*  There is a list of models (variable called "models") that lists which ones to compile. Change this to only include 'od-8020_onnxrt_coco_edgeai-mmdet_ssd_mobilenetv2_lite_512x512_20201214_model_onnx'
*  The configurations for models are held in a large dict from model_configs.py in the parent folder. This needs to be changed. The key is the string from the previous bullet.
    *  model_path needs to point to your trained model from the custom dataset.
    *  meta_layers_names_list needs to point to the PROTOTXT file that describes some model architecture features. 
    *  If the two above files are not present, they will be downloaded. This is *not* what we want for a model of our own training.

Before running, ensure that the environment variable TIDL_TOOLS_PATH is set to point to the correct location for the target device's modeling tools. If the SOC env variable was set to "am62a" when running initial setup, this should be correct already (within edgeai-tidl-tools/tidl_tools).

Once complete, the compiled artifacts should be in a directory with the model's full name under edgeai-tidl-tools/model-artifacts. Under this repo's retail-shopping directory is food-detection-model-mobv2ssd; this is the same as the directory from model-artifacts.

One last (optional) item before we continue: getting class labels aligned between model output and text name. This is only necessary if using edgeai-gst-apps for testing or the tidlpostprocess GST plugin. When modelmaker attempts to compile a model, it creates a dataset.yaml file to describe the dataset, which includes mapping the output class integer to a text label. The param.yaml file needs to also provide a mapping (['metric']['label_offset_pred']) from the output of the model to the index in dataset.yaml. For this dataset, it is one-to-one since all classes trained on are used. Note that edgeai-tidl-tools does not create this on its own, because it has no insight into what the classes are called, whereas training does.


## 5. Using the model

Now to the fun part - demonstrating the model on the target device. 

The fastest way to do this is to add a config file and run one of the stock edgeai-gst-apps (cpp or python) on this newly generated model. This is valuable proof of concept for evaluating accuracy in practice and without writing new code. Simply go into a config like [object_detection](../../configs/object_detection.yaml) and swap one of the model paths for the newly trained one. Make sure that model is being used in the 'flows' at the bottom of the file. You can point the input to be a directory of images (such as the test set) or the camera. A USB camera is easiest.


Output will look something like this: 

<img src=./food-model-test-gstapps.jpg width=500>

In the first iteration of this design, gstreamer flow created from the YAML file was used as a starting point. Similar to [edgeai-gst-apps/apps_python](https://github.com/TexasInstruments/edgeai-gst-apps/tree/main/apps_python), an appsink/appsrc pair was used to do the preprocessing, inference, post-processing, and extra application code. We'll discuss in the next section how this was improved to better pipeline these tasks and improve performance.

## 6. Building the Application

Now that the model is working, an application needs to be built around it. That means input images, preprocessing, running the model itself, and doing *something* with the output that is suited to a real-life use-case. Here, that *something* will be using the identified objects to populate an order for a user.

To build the majority of thise data processing pipeline, gstreamer (GST) is used. With the GST plugins used across this edgeai-gst-apps repo, everything but the application code can be done purely in a GST pipeline. For the application, gstreamer can use an "appsink" and "appsrc" to expose an interface into and out of application code, respectively. 

In the program (see [gst_configs.py](../gst_configs.py)), a reference to an appsink is retreived and used to "pull samples" that hold a raw byte array, representing the chunk of data, i.e., an image. The structure of this array needs to be known before-hand, such as size, pixel format. For typical data like images (raw/x-video), the "caps" which describe the input and output of a GST plugin give information about the resolution and pixel format. 

When first designing the application, this was used heavily - images from the camera were converted to RGB images in full resolution from the camera, and preprocessing, inference, postprocessing, and adding a receipt-like subframe to the image was all done in Python. The application borrowed liberally from the main apps_python code, but the extra processing within [display.py](../display.py) was slow and had highly variable latency due to many opencv calls for drawing text/boxes. This works, but was a huge bottleneck. The pipeline ran at only a few fps with 2-3 seconds of latency (on a model that runs at >60fps and a 30fps camera). Hardly an interactive application. Let's look at how this could be pipelined and optimized to improve the framerate.


### 6.1 Optimizing the application

The ["OpTIflow"](../../scripts/optiflow/) plugins (tidlpreproc, tidlinferer, tidlpostproc) are instrumental in better pipelining since they offload the single-threaded python program (we tried multiprocessing but GST's appsink/appsrc did not play well). Even though some of these plugins use CPU, they spread the load across multiple processes that take advantage of the multiple Arm A cores.

The [pipeline graph](./pipeline.png) shows what the overall pipeline looks like. This is using a USB camera for simplicity.  See the pipeline's string description below:


`v4l2src device=/dev/video2  ! image/jpeg,width=1920,height=1080 ! jpegdec ! tiovxdlcolorconvert  !  video/x-raw, format=NV12 ! tiovxmultiscaler name=split_resize   split_resize. ! video/x-raw, width=512, height=512, format=NV12   ! tiovxdlpreproc data-type=uint8 ! application/x-tensor-tiovx,  channel-order=NCHW, tensor-format=RGB, tensor-width=512, tensor-height=512  ! tidlinferer model=./model/food-detection-model/ ! tee name=model_out_tensor   model_out_tensor. ! queue max-size-buffers=2 leaky=2 ! postproc.tensor  split_resize. ! video/x-raw, width=1440, height=1080, format=NV12 ! postproc.sink  tidlpostproc name=postproc model=./model/food-detection-model/  ! queue leaky=2 max-size-buffers=1 name=queue-mosaicsink0 ! mosaic.sink_0 model_out_tensor. ! queue name=queue-tensor-in leaky=2 max-size-buffers=1 ! appsink name=tensor_in max-buffers=1 drop=true sync=false   appsrc format=GST_FORMAT_TIME is-live=true block=false  name=out ! video/x-raw,  format=RGB, width=480, height=1080 ! tiovxdlcolorconvert ! video/x-raw, format=NV12   ! queue name=queue-mosaicsink1 leaky=2 max-size-buffers=1 ! mosaic.sink_1   tiovxmosaic name=mosaic   sink_0::startx="<480>" sink_0::starty="<0>" sink_0::heights="<1080>" sink_0::widths="<1440>"  sink_1::startx="<0>" sink_1::starty="<0>" sink_1::heights="<1080>" sink_1::widths="<480>" ! kmssink`

Now to break this down into more manageable chunks: 

Input from camera:
`v4l2src device=/dev/video2  ! image/jpeg,width=1920,height=1080 ! jpegdec !  tiovxdlcolorconvert  !  video/x-raw, format=NV12`

*	v4l2src is used to pull images using the device at /dev/video2. 
*	For the USB camera used at this stage, frames are JPEG encoded and need jpegdec to convert back into the raw image
*	Video conversion using tiovxdlcolorconvert changes the pixel format to NV12, which is the preferred format for TI’s GST plugins. 
    *	The string starting with raw/x-video is describing the caps that go between plugins on both sides. This helps the two plugins negotiate which format and resolution to expect from each other. In some cases, this is inferred. When changing formats or resolutions, it is important for this to be included so the plugin that actually makes the change knows what its output needs to be.

Splitting the pipeline with rescaling:
`tiovxmultiscaler name=split_resize  ` 
*	The tiovxmultiscaler plugin can take in up to 2 inputs and produce up to 10 in different resolutions. This leverages the MSC hardware accelerator for scaling down images – this includes interpolation. 
    `*	This plugin is given a name (split_resize) so it can be used as a source (src) for later plugins. Naming for specific instances of a plugin allows them to referenced later and therefore create splits and merges within the pipeline for more advanced use-cases like this one.

Model preprocessing and Inference:
`split_resize. ! video/x-raw, width=512, height=512, format=NV12 ! tiovxdlpreproc data-type=uint8 ! application/x-tensor-tiovx,  channel-order=NCHW, tensor-format=RGB, tensor-width=512, tensor-height=512 ! tidlinferer model=./model/food-detection-model/ ! tee name=model_out_tensor `
*	“split_resize.” is used to indicate the source for this component
*	The output for one path from scaling is set to 512x512, which is the model’s input resolution. 
*	The preproc plugin converts the RGB image from interleaved channel values (R1G1B1, R2G2B2, … RnGnBn for each pixel in the image) to planar (R1R2 … Rn , G1G2 … Gn, B1B2 … Bn), which the model expects. The params.yaml file includes this information by setting input format as NCHW for number, channel, height, width of the input tensor format. 
    *	The output is a tensor (application/x-tensor-tiovx).
    *	Note that ifberb the input_optimization step was not done prior, then the data-type would change (float32) and there would be a mean to subtract and a scale factor to multiply by. The preproc plugin can do this, but is less efficient than the deep learning accelerator. 
*	The 3x512x512 tensor goes to the tidlinferer plugin for inference on the deep learning accelerator. The path to the model directory is provided; it will use the artifacts, YAML, and .ONNX file to run inference on the new tensor.
*	The tensor out of tidlinferer is split and named (model_out_tensor) so that application code and tidlpostproc can both use it.

Postprocessing for visualizing inference results:
`model_out_tensor. ! queue max-size-buffers=2 leaky=2 ! postproc.tensor  `
AND
`split_resize. ! video/x-raw, width=1440, height=1080, format=NV12 ! postproc.sink  tidlpostproc name=postproc model=./model/food-detection-model/  ! queue leaky=2 max-size-buffers=1 name=queue-mosaicsink0 ! mosaic.sink_0`
*	A merge happens with postproc .
    *	One input is an application tensor and an image coming from the tiovxmultiscaler.
    *	The second output from tiovxmultiscaler is 1440x1080 resolution, and is the base image that the output that bounding boxes from the tidlinferer will be drawn onto.
    *	The dataset.yaml file must be in the model’s directory for this to find classnames.
*	The output image from postproc goes into the tiovxmosaic sink (see below) so that the labelled image here can be merged with the output from application code (appsrc).
    *	A queue helps smooth performance and allow frames to be dropped in case the application code is running slower than this portion of the pipeline.

Interface to application code (tensor from inference input, image with receipt/order output):
`model_out_tensor. ! queue name=queue-tensor-in leaky=2 max-size-buffers=1 ! appsink name=tensor_in max-buffers=1 drop=true sync=false   appsrc format=GST_FORMAT_TIME is-live=true block=false  name=out ! video/x-raw,  format=RGB, width=480, height=1080 ! tiovxdlcolorconvert ! video/x-raw, format=NV12   ! queue name=queue-mosaicsink1 leaky=2 max-size-buffers=1 ! mosaic.sink_1`
*	The tensor from dlinferer contains information about which items are recognized. This is provided to application code via the appsink.
    *	Appsink is given a name so it can be retrieved from the python program – see gst_configs.py (FIXME: link)
*	The application code between appsink and appsrc is entirely dependent on the application. 
    *	In the retail scanner application, use a small finite state machine to represent different stages of a transaction like creating the order, “paying”, and waiting for the next customer to arrive. Text is shown on the screen to provide feedback to the user. 
*	The output from application from appsrc is in RGB format and needs to be converted back to NV12. It is more efficient to convert with tiovxdlcolorconvert than to do so in application code
*	The converted image, which contains text showing user instructions and recognized items, is provided to the mosaic so it can be combined with labelled output.

Stitch postprocessed output and application code output into one frame and display to screen:
`tiovxmosaic name=mosaic   sink_0::startx="<480>" sink_0::starty="<0>" sink_0::heights="<1080>" sink_0::widths="<1440>"  sink_1::startx="<0>" sink_1::starty="<0>" sink_1::heights="<1080>" sink_1::widths="<480>" ! kmssink driver-name=tidss sync=false`
*	The tiovxmosaic plugin can combine multiple input sources, which arrive at the multiple “sinks”. These sinks need information about the dimensions and start locations. Scaling can happen within the plugin.
*	The final output is sent to the display via kmssink plugin – the driven-name must be provided, and sync=false allows frames to be dropped.

This pipeline runs at 18-20 fps on the AM62A74 processor SDK version 8.6. The C7xMMA Deep learning accelerator is loaded 25-30%, quad A53 CPU at 30-40% and DDR at 20% on the 8.6 release of the Linux SDK for AM62A on the starter kit (SK) EVM, revision E2. Based on this load, we could swap the AM62A7 for AM62A3 (2 TOPS vs. 1 TOPS, respectively) for cost optimization. Further, the 2 core variant AM62A32 may suffice, this would require additional profiling to ensure the reduced multiprocessing (and thus, pipelining) capability does not drastically reduce FPS. This can be tested by disabling two CPU cores temporarily.

The updates to the pipeline represent at least a 3x improvement in performance by utilizing gstreamer pipelining more effectively. 


### 6.2 Adding a Camera with ISP (IMX219 a.k.a. Raspberry PiCam v2)

TI's Edge AI Processors, e.g. AM62A, TDA4VM, AM68A, include an ISP and additional hardware accelerators for scaling images (multiscaler MSC) and dewarping distortions from wide-angle lens (Lens Distortion Correction LDC). The ISP, MSC, and LDC are all TI-designed IP within the Vision Processor Accelerator (VPAC). 

  * **NB:** this demo also works with USB cameras in 720 and 1080p. When running the main application [retail_vision_app.py](../retail_vision_app.py), use the -c tag with either c270 or logi-1080 for 720 or 1080p USB input, respectively. See the help -h dialog for more.

An ISP (image signal processor) is necessary to take the raw output of an image sensor and process it into a more typical format like RGB. Raw output sensors are cheaper and external ISP's (including integrated ones like TI's) are more readily tunable than ISP's built into the image sensor. The ISP can be tuned based on lighting conditions, lens effects, auto-exposure, etc. TI has a tuning tool for the integrated ISP and [supporting documentation](https://www.ti.com/lit/pdf/sprad86).

The IMX219 is a low-cost sensor that is supported out-of-box for AM62A, and it can capture at up to 8MP at 15fps or 2MP at 60fps. Supporting a sensor includes several components: a driver (if lucky, one that's upstreamed to mainline Linux), ISP tuning, and a module. All three of these are available for this sensor. However, the journey to using this sensor has a few unexpected issues:
  * The driver has limited support for different resolutions and formats
    * The typical 16:9 aspect ratio 1920x1080 (2MP) resolution does not have full field of view - it is a cropping the full 8MP frame, and thus appears artificially zoomed in
    * Full FOV with 4:3 aspect ratio is possible with 1640x1232 (half resolution in width and height; still 2 MP). However, the upstreamed driver only works as-is with 10-bit pixel values (RGGB10)
    * 60 fps is not supported at 2MP resolutions - it runs at 30 fps
  * Different resolutions may require changes to the ISP files (typically under /opt/imaging/imx219) - this required the "DCC" files to be regenerated. That process is not covered in this document.

The above issues were fixed in the 8.6 SDK release for AM62A, and the scripts/setup_cameras.sh script was modified to use the 1640x1232 RGGB10 format.



## Closing Notes

This demo and documentation above shows a pipeline from selecting a model to building an end-to-end application on a custom dataset. Optimizing the application (without extensive effort) was possible through gstreamer pipelines that offload single-threaded application code and improve performance enough for human interaction to feel real-time. 

To build a more effective and robust version of this application, we'll note some areas of improvement:
  * Larger dataset with items in more contexts and with more false examples. mAP is very high for this model, but that's tied to the fact that the background/setting is highly consistent. Try the model on a black or reflective table and see how it performs.
    * i.e., Add more instances of the same items and add several new items, especially real-life examples of foods in different "life" stages, e.g. green/yellow/browning banana.
  * Port to CPP for more efficient processing, including threading. Python does not handle threading/multiprocessing well. 
    * Even better, make the application code into its own plugin to eliminate unnecessary buffer copies.
    * The main bottleneck is OpenCV calls for drawing text in Python
  * Add more user interaction, such as point of sale (real or simple), buttons
    * Ability to add a new item by taking a video, encoding/compressing, and sending over network link to machine with training capability
    * Theft detection - secondary camera facing user that alerts if order is filled out but user doesn't "pay"


If you made it this far, we hope you learned plenty about designing an application on TI's Vision Edge AI MPUs like AM62A!
