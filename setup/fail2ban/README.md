# fail2ban

외부 공격 (ex. ssh 해킹)을 차단하는 소프트웨어



## 1. INSTALL

```bash
apt update
sudo apt install -y fail2ban
```



## 2. RUN

```bash
sudo systemctl start fail2ban
```



## 3. 차단 목록 조회

```bash
wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup/fail2ban/fail2ban_listr/docker_compose.md
wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup/fail2ban/install.sh
./install.sh
```


```bash
fail2ban_list
```

<img src="https://user-images.githubusercontent.com/4587330/210972256-8eab6bba-3813-42d5-8fc9-4d9043f111a1.png" />

- 120.25.171.85 IP 공격자가 1번 차단되었다.
- 8.218.67.187 IP 공격자가 1번 차단되었다.
