## Tunneling by SSH

- Local Tunnel (-L 옵션)
  - 포워드 터널링
  - 접속 시작 호스트 부터 순차적으로 포워딩 진행  
- Remote Tunnel (-R 옵션)
  - 리버스 터널링 
  - 시작 호스트가 파이어월 안쪽의 호스트, 안쪽에서 reverse proxy가 외부로 연결하여 터널 형성


![tun](https://user-images.githubusercontent.com/4180063/214148347-39dc681c-be2a-4fd8-8bad-ec14e9acdba9.png)


## Tunnel check
- netstat -tulpn
