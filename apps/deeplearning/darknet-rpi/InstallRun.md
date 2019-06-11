# YOLO & Camera 연동 with RPi3 B+

- 재실 감지 시스템
1. RPi에 Camera을 연동하고 YOLO System을 RPi에 설치함
2. Camera로 실시간 상태를 촬영하고 이 사진을 YOLO에 연동하여 object를 detection을 확인
3. capture 사진을 파일이름을 시간으로 저장

## Step1 Camera Test
&nbsp; &nbsp; &nbsp; 터미널 창에서 : vcgencmd get_camera <br>
&nbsp; <img width="300" src="./images/camera_test1.jpg"></img><br>

## Step2 Rpi State
&nbsp; 1. os-release 버전 확인 <br>
&nbsp; &nbsp; &nbsp; 터미널 창에서 : vcgencmd get_camera <br>
&nbsp; <img width="600" src="./images/os-release.png"></img><br>
&nbsp; 2. rpi_update_upgrade<br>
&nbsp; &nbsp; &nbsp; 터미널 창에서 : sudo apt-get update <br>
&nbsp; &nbsp; &nbsp; 터미널 창에서 : sudo apt-get upgrade <br>
&nbsp; <img width="600" src="./images/rpi_update_upgrade.png"></img><br>

## Step3 Install required library
&nbsp; 1. PeachPy 설치<br>
&nbsp; &nbsp; &nbsp; 터미널 창에서 :sudo pip install --upgrade git+https://github.com/Maratyszcza/PeachPy<br>
&nbsp; <img width="600" src="./images/PeachPy.png"></img><br>

&nbsp; 2. confu<br>
&nbsp; <img width="600" src="./images/confu.png"></img><br>

&nbsp; 3. ninja_git<br>
&nbsp; <img width="600" src="./images/ninja_git.png"></img><br>
&nbsp; 4. ninja_install_export<br>
&nbsp; <img width="600" src="./images/ninja_install_export.png"></img><br>

&nbsp; 5. clang_install<br>
&nbsp; <img width="600" src="./images/clang_install.png"></img><br>
&nbsp; 5. clang_install_done<br>
&nbsp; <img width="600" src="./images/clang_install_done.png"></img><br>

nnpack-darknet_git<br>
&nbsp; <img width="600" src="./images/nnpack-darknet_git.png"></img><br>
nnpack-darknet_confu<br>
&nbsp; <img width="600" src="./images/nnpack-darknet_confu.png"></img><br>
nnpack-darknet_configure<br>
&nbsp; <img width="600" src="./images/nnpack-darknet_configure.png"></img><br>
nnpack-darknet_ninja_1<br>
&nbsp; <img width="600" src="./images/nnpack-darknet_ninja_1.png"></img><br>
nnpack-darknet_ninja_2<br>
&nbsp; <img width="600" src="./images/nnpack-darknet_ninja_2.png"></img><br>
nnpack-darknet_cp<br>
&nbsp; <img width="600" src="./images/nnpack-darknet_cp.png"></img><br>

## Step4 Install darknet_nnpack
darknet_nnpack_git<br>
&nbsp; <img width="600" src="./images/darknet_nnpack_git.png"></img><br>
darknet_nnpack_make1<br>
&nbsp; <img width="600" src="./images/darknet_nnpack_make1.png"></img><br>
darknet_nnpack_make2<br>
&nbsp; <img width="600" src="./images/darknet-nnpack_make2.png"></img><br>

## Step5 Download yolov file
yolov3_download<br>
&nbsp; <img width="600" src="./images/yolov3_download.png"></img><br>
yolov3_download2<br>
&nbsp; <img width="600" src="./images/yolov3_download2.png"></img><br>
yolov2-tiny_download<br>
&nbsp; <img width="600" src="./images/yolov2-tiny_download.png"></img><br>
yolov3-tiny_download<br>
&nbsp; <img width="600" src="./images/yolov3-tiny_download.png"></img><br>

## Step6 Run darknet App
darknet_test_person<br>
&nbsp; <img width="600" src="./images/darknet_test_person.png"></img><br>

## Step7 재실감지 시스템
python_run<br>
&nbsp; <img width="600" src="./images/python_run.png"></img><br>
save_screenshot<br>
&nbsp; <img width="600" src="./images/save_screenshot.png"></img><br>
