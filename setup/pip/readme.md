
# Linux에서 설치

## pip
- easy_install은 Python Setuptools에 포함되어 있기 때문에 이를 설치하면 사용할 수 있다. 다음과 같은 명령을 실행하여 easy_install을 설치하자.

    - sudo apt-get install python-setuptools
    - sudo apt-get install python-pip


- 만일 Python 3를 사용하고 있는 경우에는 다음과 같은 명령으로 easy_install과 pip 설치

    - sudo apt-get install python3-setuptools
    - sudo easy_install3 pip

- sudo apt-get install python3-pip

- Python 2.x
  - sudo easy_install 모듈명
  - sudo pip install 모듈명
- Python 3.x
  - sudo easy_install3 모듈명
  - sudo pip3 install 모듈명

## virtualenv
- python 2.7 
  - pip install virtualenv 
  
- python 3.5 
  - pip3 install virtualenv
  
- Python2 virtual env
  - python -m virtualenv venv 
  - virtualenv venv --python=python 
  - virtualenv venv --python=python2.7
  
- Python3 virtual env
  - python3 -m virtualenv venv 
  - virtualenv venv --python=python3 
  - virtualenv venv --python=python3.5
