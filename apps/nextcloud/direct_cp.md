# Copy file to nextcloud server
First create a .netrc file containing your credentials. For help about that please see https://linux.die.net/man/5/netrc 39
My location for “.netrc” file is the homedirecty of the user running the script.

<pre>
BACKUP_PATH="/backup/nextcloud"
LOGDATE=`date +%Y-%m-%d-%H-%M`
LOGFILENAME=/backup/mylog-$LOGDATE.log
curl --netrc -s -S -T /$BACKUP_PATH/db/$LOGDATE-db.sql.gz "https://your.cloud/remote.php/dav/files/<path-on-your-server>/" >> $LOGFILENAME && rm /$BACKUP_PATH/db/$LOGDATE-db.sql.gz
</pre>
You need to adapt your pathes.

For curl options see the docs at https://linux.die.net/man/1/curl
