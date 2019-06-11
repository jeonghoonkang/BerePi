# YOLO & Camera 연동 with RPi3 B+

- 재실 감지 시스템
1. RPi에 Camera을 연동하고 YOLO System을 RPi에 설치함
2. Camera로 실시간 상태를 촬영하고 이 사진을 YOLO에 연동하여 object를 detection을 확인
3. capture 사진을 파일이름을 시간으로 저장

## Step1 Camera Test
&nbsp; &nbsp; &nbsp; 터미널 창에서 : vcgencmd get_camera <br>
&nbsp; <img width="300" src="./images/camera_test1.jpg"></img><br>

## Step2 Rpi State
1. os-release 버전 확인 <br>
&nbsp; 터미널 창에서 : vcgencmd get_camera <br>
&nbsp; <img width="600" src="./images/os-release.png"></img><br>
2. rpi_update_upgrade<br>
&nbsp; 터미널 창에서 : sudo apt-get update <br>
&nbsp; 터미널 창에서 : sudo apt-get upgrade <br>
&nbsp; <img width="800" src="./images/rpi_update_upgrade.png"></img><br>

## Step3 Install required library
1. PeachPy 설치<br>
&nbsp; 터미널 창에서 : sudo pip install --upgrade git+https://github.com/Maratyszcza/PeachPy<br>
&nbsp; <img width="800" src="./images/PeachPy.png"></img><br>

2. confu 설치<br>
&nbsp; 터미널 창에서 : sudo pip install --upgrade git+https://github.com/Maratyszcza/confu<br>
&nbsp; <img width="800" src="./images/confu.png"></img><br>

3. ninja_git 다운로드<br>
&nbsp; 터미널 창에서 : git clone https://github.com/ninja-build/ninja.git<br>
&nbsp; <img width="600" src="./images/ninja_git.png"></img><br>
4. ninja_install_export 설치 및 설정<br>
&nbsp; 터미널 창에서 : cd ninja<br>
&nbsp; 터미널 창에서 : checkout release<br>
&nbsp; 터미널 창에서 : ./configure.py –bootstrap<br>
&nbsp; 터미널 창에서 : export NINJA_PATH=$PWD<br>
&nbsp; <img width="800" src="./images/ninja_install_export.png"></img><br>

5.1. clang_install 설치<br>
&nbsp; 터미널 창에서 : sudo apt-get install clang<br>
&nbsp; <img width="800" src="./images/clang_install.png"></img><br>
5.2. clang_install_done<br>
&nbsp; <img width="800" src="./images/clang_install_done.png"></img><br>

6. nnpack-darknet_git 다운로드<br>
&nbsp; 터미널 창에서 : git clone https://github.com/digitalbrain79/NNPACK-darknet.git<br>
&nbsp; <img width="800" src="./images/nnpack-darknet_git.png"></img><br>
7. nnpack-darknet_confu 설치<br>
&nbsp; 터미널 창에서 : confu setup<br>
&nbsp; <img width="800" src="./images/nnpack-darknet_confu.png"></img><br>
8. nnpack-darknet_configure 설치<br>
&nbsp; 터미널 창에서 : python ./configure.py –backend auto<br>
&nbsp; <img width="800" src="./images/nnpack-darknet_configure.png"></img><br>
9.1. nnpack-darknet_ninja_1 설치<br>
&nbsp; 터미널 창에서 : $NINJA_PATH/ninja<br>
&nbsp; <img width="600" src="./images/nnpack-darknet_ninja_1.png"></img><br>
9.2. nnpack-darknet_ninja_2 설치<br>
&nbsp; <img width="600" src="./images/nnpack-darknet_ninja_2.png"></img><br>
10. nnpack-darknet_cp 복사<br>
&nbsp; 터미널 창에서 : sudo cp -a lib/* /usr/lib/<br>
&nbsp; 터미널 창에서 : sudo cp include/nnpack.h /usr/include/<br>
&nbsp; 터미널 창에서 : sudo cp deps/pthreadpool/include/pthreadpool.h /usr/include/<br>
&nbsp; <img width="800" src="./images/nnpack-darknet_cp.png"></img><br>

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
