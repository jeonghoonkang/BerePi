# Darknet, YOLO

## darknet, deep learning framework
- https://pjreddie.com/darknet/

## YOLO, object detection
- Yolo, Cam Streaming, Learning, etc.
  - https://j-remind.tistory.com/58?category=693866

### RaspberryPi : installation instruction
- https://j-remind.tistory.com/48?category=693866
- stretch upgrade

### Windows and Linux installation
- https://github.com/AlexeyAB/darknet
- Ubuntu 18.04 installation : https://j-remind.tistory.com/57?category=693866
  - note :  ln -s /usr/local/lib/python2.7/dist-packages/numpy/core/include/numpy numpy

### Movidius
- https://www.pyimagesearch.com/2019/04/08/openvino-opencv-and-movidius-ncs-on-the-raspberry-pi/


- /darknet detect cfg/yolov3.cfg yolov3.weights data/dog.jpg

## Streamlit human detect

- File: `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/yolo/human_detect.py`
- Purpose:
  - Read image files from a remote WebDAV folder
  - Detect people with YOLO, allowing GPU selection when multiple NVIDIA GPUs are available and defaulting to the first GPU
  - Save two result images when a person is found:
    - original image with capture time footer
    - person-box image with capture time footer
  - Copy the saved outputs to multiple WebDAV folders and multiple local folders
  - Delete the source WebDAV file after successful distribution so it behaves like a move

### Run

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/yolo
pip install -r requirements.txt
streamlit run human_detect.py
```
