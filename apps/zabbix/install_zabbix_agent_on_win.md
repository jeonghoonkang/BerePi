# Zabbix agent 설치 방법 (Windows)

## 1. zabbiz-agent 설치
   * http://www.zabbix.com/download.php > Zabbix pre-compiled agents > Zabbix 3.4 > Windows 다운로드 **or** [직접 다운로드](https://www.zabbix.com/downloads/3.4.6/zabbix_agents_3.4.6.win.zip)
   * C:\ 에 압축해제 (conf 파일 경로를 위해 C:\ 설치를 추천)

   ```diretory
.C:\
¦---- zabbix_agents_3.4.6.win
¦     ¦---- bin
¦     ¦    ¦---- win32
¦     ¦    ¦---- win64
¦     ¦---- conf
   ```

## 2. conf 파일 수정
   ※  **Hostname 은 중복되어서는 안되며, zabbix server 에 등록된 Host 명과 일치해야함**
      1. config 파일 다운로드
     * [다운로드](https://raw.githubusercontent.com/jeonghoonkang/PDM/master/doc/zabbix_monitoring_system/conf/zabbix_agentd.win.conf)
      2. config 파일 수정

   ```
LogFile=c:\zabbix_agents_3.4.6.win\zabbix_agentd.log
Server=118.129.98.184
ServerActive=118.129.98.184
Hostname=<Your Hostname>
   ```

## 3. Zabbix agent 설치

  * 설치하는 경우 시스템이 재시작되어도 agent 가 자동실행됨
  * 무설치 실행의 경우 '추가' 항목을 참조할 것

  * 시작메뉴 -> 명령프롬프트(관리자) 실행
  ```
cd c:\zabbix_agents_3.4.6.win\bin\win64
zabbix_agentd.exe --config c:\zabbix_agents_3.4.6.win\conf\zabbix_agentd.win.conf --install
zabbix_agentd.exe --start
  ```

## 4. Zabbix Server 에 등록

    1. Configuration > Hosts > Create host

    2. Host 항목 입력
   - Host name : <Your name>
   - Groups : 소유 그룹 선택
   - Agent interfaces
        * 고정 IP 인 경우 IP 입력
        * Active 모드의 경우 0.0.0.0 입력

    3. Templates 항목 입력
   - 'Select' 버튼
   - 'Template OS Windows Active' 선택

    4. 'Add' 버튼 클릭

    5. Monitoring > Graphs 에서 신규 등록된 Host 선택 후 데이터 수신 여부 확인

## 5. 추가

    1. 설치없이 zabbix agent 실행하는 경우

   ```
   cd c:\zabbix_agents_3.4.6.win\bin\win64
   zabbix_agentd.exe -f --config c:\zabbix_agents_3.0.0.win\conf\zabbix_agentd.win.conf
   ```

    2. Template 선택시 참고 사항

   - Template OS Windows : Zabbix Server 에서 Host 로 연결이 가능한 경우 (Public IP) 선택, Server 에서 Host 제어 가능함
   - Template OS Windows Active : private address 로 연결되어 Server 에서 연결이 어려운 경우 선택

[참조](http://www.zabbix.com/download.php)