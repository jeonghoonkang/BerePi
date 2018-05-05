# openTSDB 를 위한 자바 설치에 주의
# 실행시에 경로 문제가 많이 발생하기 때문에
# JAVA 설치 상태를 주의하고 있어야 함

sudo apt-get purge openjdk*
sudo add-apt-repository ppa:webupd8team/java
sudo apt-get update

#Java 8 설치
sudo apt-get install oracle-java8-installer

#Java 7 설치
#sudo apt-get install oracle-java7-installer

#Java 6 설치
#sudo apt-get install oracle-java6-installer
