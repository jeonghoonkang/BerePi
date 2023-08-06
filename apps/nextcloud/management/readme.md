
- sudo docker logs -n 30 {컨테이너 이름} # IP 주소 확인 30 라인 
- sudo docker exec -it -u 33 {컨테이너 이름} php occ security:bruteforce:reset {IP주소, 0.0.0.0 형식}
