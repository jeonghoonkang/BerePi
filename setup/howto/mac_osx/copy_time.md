### copy finish file size loop

- while true; do;echo""; du -hs ./; echo " / 105G"; sleep 10; clear ; done;

### print time

<pre> tot_size=105; start=`date +%s.%N`; while true; do; ontheway=`date +%s.%N`; echo""; du -hs ./; echo " / 105G"; diff=$( echo "$ontheway - $start" | bc -l ); echo 'run time: ' $diff; sleep 10; clear ; done; </pre>


### Reference
- https://codechacha.com/ko/shell-script-measure-wall-time/
