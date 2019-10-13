
# Gateway system for TinyOS 
- This is for TinyOS basestation which supports multi-hop gateway with RaspberryPi2
- TinyOS root mote connected to RaspberryPi2 using USB interface
- collecting Tos Packets and forwarding to Cloud service

# Requrements
- RaspBerryPi 2/3/4
- TinyOS mote
  - Teglos rev.B family
  - Kmote is best for this system
  
# crontab 디버깅 방법
  - */45 * * * * sh /home/pi/devel/BerePi/apps/tinyosGW/this_run_public_ip.sh > /home/pi/logs/crontab_debug.log 2>&1
  - 위의 예처럼 실행을 시키면, 로그파일로 저장이 되어, crontab 실행이 정상적으로 진행되고 있는지 확인할 수 있음 (45분마다)
  
  
# Mac OSX issue
- name is Darwin
    - name = platform.system()
- brew는 sshpass 를 제공하지 않아서, github에서 다운로드 받아서 설치해야 함
    - https://ole.michelsen.dk/blog/schedule-jobs-with-crontab-on-mac-osx.html
    
      
# 실행 플랫폼 확인

<pre>
os_type = platform.system()
os_machine = platform.machine()
os_ver = os.uname()

#출력
Linux
armv6l
('Linux', 'mins-gate', '4.1.19+', '#858 Tue Mar 15 15:52:03 GMT 2016', 'armv6l')
</pre>

