### apt error

- error message
  
<img width="1436" alt="image" src="https://github.com/jeonghoonkang/BerePi/assets/4180063/d72990cf-358c-4664-b407-6cd103d4fac5">

- how to solve it
  
<pre>
sudo rm -rf /var/lib/apt/lists/*
sudo apt-get update -o Acquire::CompressionTypes::Order::=gz
sudo apt update && sudo apt upgrade
</pre>
