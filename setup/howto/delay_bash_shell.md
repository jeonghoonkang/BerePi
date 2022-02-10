## deay and start scp

<pre>
secs=$((5 * 60))
while [ $secs -gt 0 ]; do
   echo -ne "$secs\033[0K\r"
   sleep 1
   : $((secs--))
done

sshpass -p{PW} scp -v -r -o StrictHostKeyChecking=no admin@192.168.0.1:rtx/* ./{path}/  

rsync -avrh --rsh="sshpass -p {PW} ssh -p {PORT} -l daehan" {DEST}.com:/home/daehan/data /home/backup/

</pre>
