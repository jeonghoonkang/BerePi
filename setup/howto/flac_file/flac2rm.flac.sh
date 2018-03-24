
echo " Beware, it will delete all files of FLAC, which in the lower lever directory"

echo " Please input yes or no : "
echo " you inputed, if yes will proceed to delete"
read keystroke 
#echo $keystroke

if [ "$keystroke" = "no" ] 
then 
    exit 0
fi

echo " Please make sure you entered yes, which will proceed to delete, or Ctrl+C "
read keystroke 
find ./ -name "*.flac" -print0 | xargs -0 -i -t rm {}


