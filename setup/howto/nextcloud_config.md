
sudo docker cp compose_script_app_1:/var/www/html/config/config.php ./
sudo docker cp config.php compose_script_app_1:/var/www/html/config/config.php 
sudo docker exec -it compose_script_app_1 cat /var/www/html/config/config.php

>> sudo docker exec -it nextcloud_app_1 cat /var/www/html/config/config.php

<?php
$CONFIG = array (
  'htaccess.RewriteBase' => '/',
  'memcache.local' => '\\OC\\Memcache\\APCu',
  'apps_paths' => 
  array (
    0 => 
    array (
      'path' => '/var/www/html/apps',
      'url' => '/apps',
      'writable' => false,
    ),
    1 => 
    array (
      'path' => '/var/www/html/custom_apps',
      'url' => '/custom_apps',
      'writable' => true,
    ),
  ),
  'instanceid' => 'ocy9174t8mqe',
  'passwordsalt' => '4yiY39c7Po5cYFMI6wdIY+Y6KESTAl',
  'secret' => 'gHih7cu6U5vNFaMZIcOgsvPpt5jLPG3oi/JlB9c3YHJRKVs+',
  'trusted_domains' => 
  array (
    0 => 'tinyos.mooo.com:8881',
  ),
  'datadirectory' => '/var/www/html/data',
  'dbtype' => 'mysql',
  'version' => '21.0.1.1',
  'overwrite.cli.url' => 'https://tinyos.mooo.com:8881',
  'overwriteprotocol' => 'https',
  'dbname' => 'nextcloud',
  'dbhost' => 'db',
  'dbport' => '',
  'dbtableprefix' => 'oc_',
  'mysql.utf8mb4' => true,
  'dbuser' => 'nextcloud',
  'dbpassword' => '1234',
  'installed' => true,
);
