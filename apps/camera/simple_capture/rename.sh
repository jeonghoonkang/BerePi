#!/bin/bash
for f in *.png; do 
        echo $f
        mv -- "$f" "`hostname``date +_%F_%R_`${f}"
        #mv -- "$f" "`date`${f}"
done
#$(date +%F_%R)
#rename -v 's/00000//' *.png
#mv 00000001.png capture.$(date +%F_%R).jpg                                 
