
- sudo docker cp compose_script_app_1:/var/www/html/config/config.php ./
- sudo docker cp config.php compose_script_app_1:/var/www/html/config/config.php 
- sudo docker exec -it compose_script_app_1 cat /var/www/html/config/config.php
- sudo docker exec -it nextcloud_app_1 cat /var/www/html/config/config.php


<pre>

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
  'instanceid' => '',
  'passwordsalt' => '',
  'secret' => '',
  'trusted_domains' => 
  array (
    0 => 'tinyos.mooo.com:xxxx',
  ),
  'datadirectory' => '/var/www/html/data',
  'dbtype' => 'mysql',
  'version' => '21.0.1.1',
  'overwrite.cli.url' => 'https://tinyos.mooo.com:xxxx',
  'overwriteprotocol' => 'https',
  'dbname' => 'xx',
  'dbhost' => 'xx',
  'dbport' => '',
  'dbtableprefix' => 'oc_',
  'mysql.utf8mb4' => true,
  'dbuser' => 'xx',
  'dbpassword' => 'xx',
  'installed' => true,
);

</pre>
