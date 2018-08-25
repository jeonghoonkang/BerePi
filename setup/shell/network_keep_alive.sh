## 더이상 사용하지 않음 2018.8.20
## network-manager 를 설치하여 기능 사용

#라즈베리파이3 부터는 해당 코드가 있어야 지속적으로 네트워크 유지함. 부팅시에 원인 파악이 안된 에러때문에, 네트워크 연결이 안되는 경우가 있음 
#아래 코드를 /etc/rc.local 에 넣어서 재부팅시에 네트워크 접속이 되도록 실행하여 문제 
sudo systemctl restart dhcpcd
sudo systemctl daemon-reload
