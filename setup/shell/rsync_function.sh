function pushpi()
{ 
  local URL=mycloud.no-ip.org
  local PORT=2234
  local USER=pi
  local FOLDER=/media/USBdrive/ncdata/admin/files/
  local OPTS=( -aui --progress --stats --inplace --partial )
  rsync ${OPTS[@]} -e "ssh -p $PORT" $@ $USER@$URL:$FOLDER
}

# pushpi this_file_or_folder file2 file3
