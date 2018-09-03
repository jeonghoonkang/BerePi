# Zabbix agent 설치 방법 (Linux)



## 1. zabbiz-agent 다운로드

  * [링크](http://repo.zabbix.com/zabbix/3.4/ubuntu/pool/main/z/zabbix/)에서 OS 버전에 따라 zabbix-agent 다운로드
  * 아래는 zabbix agent 3.4.9 Ubuntu 14.04 LTS 64bit 의 다운로드 경로임

```Shell
$ mkdir ~/zabbix_bin
$ mkdir ~/zabbix_bin/zabbix_agent
$ cd ~/zabbix_bin/zabbix_agent
$ wget http://repo.zabbix.com/zabbix/3.4/ubuntu/pool/main/z/zabbix/zabbix-agent_3.4.9-1%2Btrusty_amd64.deb
```

## 2. conf 파일 설정

   1. conf 파일 다운로드

   ```Shell
   $ wget https://raw.githubusercontent.com/ipmstyle/zabbix_on_raspberry_pi/master/conf/zabbix_agentd.linux.conf
   ```

   2. conf 파일 수정

   ```Shell
   $ vi zabbix_agentd.linux.conf
   ```


   ```conf
   Hostname=<Your hostname>
   ```

   3. Zabbix agent 설치

    * ubuntu 14.04 이상에서 설치에 문제가 생기는 경우 libc6 가 2.17 이상인지 확인할 것
    * ubuntu 14.04 이하에서는 libc6 를 2.17 이상으로 설치해야함

    ```Shell
    $ sudo dpkg -i zabbix-agent_3.0.4-1+trusty_amd64.deb
    ```

   4. 설정파일 적용

```Shell
$ cp /etc/zabbix/zabbix_agentd.conf /etc/zabbix/zabbix_agentd.conf.bak
$ mv zabbix_agentd.linux.conf /etc/zabbix/zabbix_agentd.conf
$ sudo /etc/init.d/zabbix-agent restart
```


## 4. Zabbix Server 에 등록

      1. Configuration > Hosts > Create host

      2. Host 항목 입력

      * Host name : \<Your name>
      * Groups : 소유 그룹 선택
      * Agent interfaces
          * 고정 IP 인 경우 IP 입력
          * Active 모드의 경우 0.0.0.0 입력

      3. Templates 항목 입력

     * 'Select' 버튼
     * 'Template OS Linux Active' 선택

      4. 'Add' 버튼 클릭

      5. Monitoring > Graphs 에서 신규 등록된 Host 선택 후 데이터 수신 여부 확인

## 5. 추가

      1. Template 선택시 참고 사항

     * Template OS Linux : Zabbix Server 에서 Host 로 연결이 가능한 경우 (Public IP) 선택, Server 에서 Host 제어 가능함
     * Template OS Linux Active : private address 로 연결되어 Server 에서 연결이 어려운 경우 선택

      2. Zabbix agent 테스트

```Shell
$ sudo /etc/init.d/zabbix-agent status

$ zabbix_agentd -t user.proc.allcpu[<프로세스명>]
```

[참고자료](http://www.zabbix.com/download.php)
