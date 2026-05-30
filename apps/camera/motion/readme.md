# Motion detection S/W installation (Project : Motion)

## 설치 command 
- sudo apt-get installl motion

## requirements
```
Debian/Ubuntu/Raspbian
Required
sudo apt-get install autoconf automake build-essential pkgconf libtool git libzip-dev libjpeg-dev gettext libmicrohttpd-dev
```
## configuration 
- /etc/modules
  - bcm2835-v4l2
- /etc/motion/motion.conf
  - event_gap 단위는 초
- 파일 저장 경로 /var/lib/motion
   
 <pre>   
############################################################
       # Picture output configuration parameters
############################################################
    # Output pictures when motion is detected         
    picture_output on    

    movie_filename %Y%m%d%H%M%S-%qA
    # %출력설명, https://motion-project.github.io/4.1/motion_guide.html#conversion_specifiers
       
 </pre> 

- ls /var/lib/motion/ | wc -l | telegram-send --stdin 

## 최근 5분 사람 감지 후 Telegram 전송

`detection_5min.py` 는 `/var/lib/motion` 에 저장된 최근 5분 이미지 파일을 원격 Gemma4 31B 모델에 보내 사람 존재 여부와 인원수를 확인합니다. 사람이 감지되면 해당 사진, 인원수, 사람이 찍힌 시각을 Telegram 으로 전송하고 `person_detected_events.jsonl` 에도 저장합니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/camera/motion
python3 detection_5min.py
python3 detection_5min.py --dry-run
python3 detection_5min.py --dir /var/lib/motion --minutes 5
```

모델 접속 주소, prompt, Telegram bot token/chat id, 감지 이벤트 로그 경로는 `conf_connect_model.conf` 에서 설정합니다.

## run / start / stop / daemon
- sudo systemctl status ( start / stop ) motion
  - /var/lib/motion
  - /var/log/motion/motion.log 
- hostname
- crontab for maintanance
  - 9 2 * * * /var/www/html/cam/motion/cleanup_file.sh > /home/pi/devel/BerePi/apps/debug/debug_motion.log 2>&1
  - 30 */4 * * * /var/www/html/cam/motion/del_sort.sh > /home/pi/devel/BerePi/apps/debug/debug_motion.log 2>&1

## Performance, run fact-info
- 30 Min (DESK shot)
  - generation 69MB JPG files
  - 4351 pics
- One day in office 
  - light change effect : less 5 time or slightly more
- 70 days office : 3/1 ~ 5/10
  - 123 GB, 1 day about 2 GB  
- 160 days : 2/20 ~ 7/30
  - 190 GB, 1 day about 1.2 GB

# Resource
## Source code
- Motion Project Homepage 
  - https://motion-project.github.io/index.html
  - Repo : https://github.com/Motion-Project/motion

## Links (howto)
- https://www.bouvet.no/bouvet-deler/utbrudd/building-a-motion-activated-security-camera-with-the-raspberry-pi-zero
  - https://learn.adafruit.com/cloud-cam-connected-raspberry-pi-security-camera?view=all
  - https://www.instructables.com/id/Raspberry-Pi-Motion-Detection-Security-Camera/#step5

# Copying camera capture files to SERVER
- scp -P 22 -pr /var/lib/motion tinyos@IP:webdav/gw/cam

# check file by telegram-send
<pre>  
  # 0 : device num
  # event
  # time
  telegram-send -f /var/lib/motion/0-*-20240730_0203*.mkv  
  # jpg file name :  20240719_074929-11.jpg
  # date "+%Y%m%d"
</pre>

### addition
- sudo command without asking password
  - https://www.baeldung.com/linux/sudo-non-interactive-mode
- find mtime
  - https://inpa.tistory.com/entry/LINUX-%F0%9F%93%9A-find-%EB%AA%85%EB%A0%B9-mtime-ctime-atime-%EC%98%B5%EC%85%98-n-n-%EA%B0%9C%EB%85%90-%EC%A0%95%EB%A6%AC#find_-mtime_n_%EA%B0%9C%EB%85%90_%EC%9D%B5%ED%9E%88%EA%B8%B0 
