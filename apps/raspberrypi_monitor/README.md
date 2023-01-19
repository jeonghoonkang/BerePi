# Raspberry Pi Monitor

## INSTALL

  매 5분마다 라즈베리파이의 CPU/GPU 온도를 측정하여 로그로 저장한다.
  
  ```bash
  wget https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/apps/raspberrypi_monitor/temp_for_crontab.sh
 
  sudo chmod +x ./temp_for_crontab.sh
  ./temp_for_crontab.sh
  ```


## 온도 히스토리

1. 현재 CPU 온도 보기

    `rpi_cpu_temp`
    
1. 현재 GPU 온도 보기

    `rpi_gpu_temp`

1. crontab 로그파일 보기

    CPU 온도 로그파일 보기<br />
    `sudo cat /var/log/cpu_temp`

    CPU 온도 로그파일 보기<br />
    `sudo cat /var/log/cpu_temp`

1. 결과

    ```bash
    pi@tinyos:~ $ rpi_cpu_temp
    2021-07-23 14:42:58 40.894

    pi@tinyos:~ $ rpi_gpu_temp
    2021-07-23 14:43:01 42.355
    ```

    ```bash
    pi@tinyos:~ $ sudo tail -f /var/log/cpu_temp
    2021-07-23 15:45:01 42.842
    2021-07-23 15:50:01 43.816
    2021-07-23 15:55:01 42.355
    2021-07-23 16:00:01 43.329
    2021-07-23 16:05:01 43.329
    2021-07-23 16:10:01 43.816
    2021-07-23 16:15:01 43.816
    ```
