# Python test

#딕셔너리 key value 개념

#문제. dict 의 모든 key, value 값을 출력하는 for 루프 코딩

my_dict = {"apple": 1, "banana": 2, "orange": 3} 

for key in my_dict.keys(): 
  print(key, my_dict[key])

print()

for k,v in my_dict.items(): 
  print(k, v)

print()

import time

now = time.time
tm = time.strftime('%Y-%m-%d %H:%M:%S')
print (tm)


print ()

my_dict[tm] = "날씨" 

print (my_dict)
