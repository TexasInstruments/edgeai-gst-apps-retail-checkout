# Reproducing the Demo

This doc is to help others reproduce the demo by obtaining the items which the deep learning model is trained to recognize, as well as mounting hardware to hold up the board and camera.

Disclaimer: Many of these items are swappable for others of similar form. Some links may stop working as online stores change


## Shopping List

To run this demo on the same items it was trained on, we'll need some groceries:


### Fake Foods
* Fries
	- https://www.amazon.com/gp/product/B099RR4CDS
* Cakes
	- https://www.amazon.com/gp/product/B09PFNVSSD
* Rice
	- https://www.amazon.com/gp/product/B09NVFB86L
	- Probably better to use uncooked rice
* Fruits (use only banana, orange, grapes, apple)
	- https://www.amazon.com/gp/product/B07MQDS2L4
* Corn (These are ugly but still part of the dataset. Not crucial)
	- https://www.amazon.com/gp/product/B081VRBYFS
* Noodles (Also ugly. Not crucial)
	- https://www.amazon.com/gp/product/B093R87Y7Y
* Salad (This was cut into small pieces and placed into a red bowl)
    - https://www.amazon.com/gp/product/B07L9DQVWG

### Real Foods

These can be found at a grocery or convenience store. 

* Soda can is a 7.5 oz coca-cola can.
* Pringles is a snack size can.
* Bags of chips are the small snack-size packs in grocery stores. Training included bags of Doritos, Lays, Ruffles, and Cheetos.


### Containers (Not crucial)
* Food trays:
	- https://www.amazon.com/gp/product/B008CORVLM
* Paper food basket (for holding fries, grapes, etc.:
	- https://www.amazon.com/Disposable-Carnivals-Festivals-Picnics-Nachos/dp/B0108WTMHQ
* Plastic food bowl (for rice, grapes, etc.)
	- https://www.amazon.com/Creative-Converting-28103151-Plastic-Classic/dp/B001GQJZQW


### Electronics
Raspberry Pi IMX219 camera: 
	- https://www.amazon.com/dp/B09V576TFN
	- Make sure there is a 22-pin to 15-pin cable! There typicall is

AM62A EVM
	- https://www.ti.com/tool/SK-AM62A-LP

A 1080p monitor with HDMI input

### Mounting Hardware

This is not crucial, but is very convenient for displaying the demo effectively. Importantly, it keeps the camera very close to the processor (MIPI-CSI cables must be short).

The 3D printed mount does not have screw holes, but they can be added  using threaded inserts. These inserts are pushed into holes in the plastic by heating them with a solder iron. The "top" that holds the EVM uses M2.5 (5 or 6 holes within build-in plastic standoffs), and the bottom uses M2 (4 holes for the camera, sized for IMX219 module from Arducam)

[STL file for 3D printing the board mount](./AM62A-SK-3D-Mount.stl)

* Adjustable mounting arm with 1/4'' screw
  -  https://www.amazon.com/gp/product/B07X3KMYW2
* 1/4'' threaded insert
  - https://www.amazon.com/Z-LOK-Threaded-Plastic-Tapered/dp/B08PVQX853
  - Inserted into the side of the mount. Only 1 needed
  - This is where the mount screws into a standard camera mount
* M2.5 threaded insert
  - https://www.amazon.com/gp/product/B07HKT5W7S
  - Goes into the small plastic 'standoffs' that hold the EVM
* M2 threaded insert 
  - https://www.amazon.com/gp/product/B0B8GN63S2
  - Goes into the holes flush with the bottom side (4 all near each other, and near the large cutout in the board). 


In case screws are needed too, here are a few kits that have everything needed.
* M2.5 fastener kit
  - https://www.amazon.com/gp/product/B07CLQFQ4C
* M2 fastener kit 
  - https://www.amazon.com/gp/product/B07B9X1KY6
  - Recommended to use a standoff and screw


#### Connecting it together

Recommended steps:

1. Screw M2 standoffs into the 4 holes on the bottom for the camera
2. Place CSI camera over standoffs and carefully screw in with small M2 screws
3. Connect CSI cable into camera. Take care to ensure of the cable and connector are correctly facing and touching.
4. Thread the CSI cable through the hole
5. Place the EVM on top and screw into the threaded inserts. There is only one orientation that will allow all screws to be inserted.
6. Finish threading the camera cable through to the CSI connector on the EVM and connect. Again. ensure the contacts are correctly touching inside the connector.
7. Screw the entire assembly into the 1/4'' mount
8. Connect cables (Power last)
9. Boot as normal, and run the demo
