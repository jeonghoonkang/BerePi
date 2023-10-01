- put Nextcloud in maintenance mode: edit config/config.php and change this line:
'maintenance' => true,
- Empty table oc_file_locks: Use tools such as phpmyadmin or connect directly to your database and run (the default table prefix is oc_, this prefix can be different or even empty):
DELETE FROM oc_file_locks WHERE 1
- disable maintenance mode (undo first step).
- Make sure your cron-jobs run properly (you admin page tells you when cron ran the last time):
