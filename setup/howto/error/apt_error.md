### apt error

- error message
  
<img width="1436" alt="image" src="https://github.com/jeonghoonkang/BerePi/assets/4180063/d72990cf-358c-4664-b407-6cd103d4fac5">

- how to solve it
  
<pre>
sudo rm -rf /var/lib/apt/lists/*
sudo apt-get update -o Acquire::CompressionTypes::Order::=gz
sudo apt update && sudo apt upgrade
</pre>

- some other error
<pre>
/var/lib/dpkg/lock-fronted 잠금 파일을 얻을 수 없습니다. - open (11: 자원이 일시적으로 사용 불가능함)
위와 같이 업그레이드를 할 때 에러가 나오면 위에서 쓴 명령어 옵션 -rf를 -vf 옵션으로 바꿔서 사용하면 해결된다.
sudo rm -vf /var/lib/apt/lists/*
  
</pre>
