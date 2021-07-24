- crontab -l 출력
<pre>
  49 1,4,22,23 * * * /home/pi/devel/BerePi/apps/log_check/run_cron.sh
  50 1,4,22,23 * * * /home/pi/devel/BerePi/apps/log_check/run_cron_git.sh
</pre>

- 동작 확인
  - tail -f ~/devel/BerePi/apps/log_check/error.log 
