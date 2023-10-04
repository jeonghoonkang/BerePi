
### 동작확인 
- 'maintenance' => true,                                                                                                             
-'filelocking.enabled' => false,  

### 단순참고

- DELETE FROM oc_file_locks WHERE oc_file_locks.lock != 0
- put Nextcloud in maintenance mode: edit config/config.php and change this line:
  - 'maintenance' => true,
- Empty table oc_file_locks: Use tools such as phpmyadmin or connect directly to your database and run (the default table prefix is oc_, this prefix can be different or even empty):
  - DELETE FROM oc_file_locks WHERE 1
- disable maintenance mode (undo first step).
- Make sure your cron-jobs run properly (you admin page tells you when cron ran the last time):
