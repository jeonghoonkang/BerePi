# Wire Guard 

## 1. Requirements

  - Docker

## 2. Configuration

  - docker-compose.yml

## 3. Run

  ```
  docker compose -f docker-compose.yml -d
  web browser <IP>:51821
  ```

## 4. VPN client

  ```
  https://www.wireguard.com/install/
  ```

### 4-1. Ubuntu

  ```
  sudo apt install -y wireguard
  sudo cp <conf> /etc/wireguard
  ```

#### 4-1-1. 접속

  ```
  sudo wg-quick up <conf>
  ```

#### 4-1-2. 해제

  ```
  sudo wg-quick down <conf>
  ```
