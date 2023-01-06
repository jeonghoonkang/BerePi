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


