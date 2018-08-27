# -*- coding: utf-8 -*-
# Author : Jeonghoonkang, github.com/jeonghoonkang

hexstr = '123456'

# 1) [ for ... ]
hlist = [hexstr[i:i+2] for i in range(0,len(hexstr),2)]

#2) re.findall
hlist = re.findall(r'..',hexstr)

#3) map, zip, iter 이용
hlist = map(''.join, zip(*[iter(hexstr)]*2))


'''
iter(hxstr) 는 글자 하나씩 가져오는 이터레이터 함수
[ 'a' ] * 2 는 [ 'a', 'a'] 이고,
함수 호출 시 f(['a','a'])는 목록이 넘어가지만,
f(*['a','a'])는 f('a','a') 와 동일합니다. 즉, 괄호를 벗기는 역할을 합니다.
그러면 결국 zip(iter(hxstr)결과, iter(hxstr)결과) 와 같은 식인데,
첫번째 패러미터와 두번째 패러미터의 값을 한번씩 호출하게 되어있습니다.

그런데 동일한 이터레이터 이므로 하나씩 꺼내게 되므로,
(('1','2'), ('3','4'),('5','6')) 의 결과가 나옵니다.
이를 각 항목에 대하여 ''.join <=> cat 을 시키니
['12','34','56'] 
'''
