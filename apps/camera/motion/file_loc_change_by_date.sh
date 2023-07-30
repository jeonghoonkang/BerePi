
mkdir /volume1/video/$(date +%Y-%m-%d\(%a\))


for f in /volume1/video/*; do
  # skip over directories
  [ -f "$f" ] || continue
  # grep the date in YYMMDD format
  date=$(printf '%s' "$f" | grep -Eo '[0-9]{6}')
  # set target path using date to convert YYMMDD to YYYY-MM-DD(%a)
  target="/volume1/video/daily/$(date -d "$date" +%Y-%m-%d\(%a\))/"
  # mv the file
  echo mv "$f" "$target"
done




#!/bin/bash

SOURCE_FOLDER="video/"
TARGET_FOLDER="video/daily" # Not used as it is under the source folder.

doMove() {
    # Year loop assuming AFTER 2000 up to 2022
    cd "$SOURCE_FOLDER"
    for i in 20{19..20} ; do
        #echo -e "/nWorking on 20$1"
        # Month Loop
        for j in 0{1..9} {10..12} ; do
            # Day Loop
            for k in 0{1..9} {10..31} ; do
                # Find files matching YYMMDD
                file=$(find . -maxdepth 1 -type f -print | grep $i$j$k)
                # For each found file:
                for sf in $file ; do
                    # Find the folder with a different format
                    folder=$(find * -type d -print | grep $i-$j-$k)
                    echo -e "\nFile: $sf"
                    echo -e "Folder: $folder"
                    mv "$sf" "$folder/" # 2> /dev/null
                    echo -e "Moved $sf to $folder"
                done
            done
        done
    done
    cd .. # Change to your needs.
}
doMove
