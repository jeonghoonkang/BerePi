# CT 센서의 경우
  - sudo apt-get update
  - sudo apt-get install build-essential python-dev python-smbus python-pip (이것은 필요 없을수도 있음)
  - sudo pip install adafruit-mcp3008
  - wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/apps/meter/kang_simpletest.py
  - sudo python kang_simple_test.py  
  
  - 계산방법
    - 전류값 수식 : mA Output  = (VRR ADC 값(ADC7 측정수치) - ADC0) * 13.765 mA
      - 1 A 당 72.64666 DN
    - 1번 12 bit ADC 할 경우 1레벨당 13.765mA의 전류 정밀도를 가짐
