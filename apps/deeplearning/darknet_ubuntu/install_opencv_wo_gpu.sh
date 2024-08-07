sudo apt install build-essential cmake git libgtk2.0-dev pkg-config libavcodec-dev libavformat-dev libswscale-dev
sudo apt install python3-dev python3-numpy
git clone https://github.com/opencv/opencv.git
cd opencv
mkdir build
cd build
cmake -D CMAKE_BUILD_TYPE=RELEASE \
      -D CMAKE_INSTALL_PREFIX=/usr/local \
      -D BUILD_EXAMPLES=ON \
      -D WITH_CUDA=OFF \
      -D WITH_OPENCL=OFF \
      -D WITH_OPENGL=OFF ..
make -j$(nproc)
sudo make install
sudo ldconfig



# MAC OSX
# /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# brew install opencv
# import cv2
# print(cv2.__version__)

#pip install opencv-python
