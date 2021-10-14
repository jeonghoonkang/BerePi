
CSV 파일 사용 법

https://gist.github.com/pax/322e642662f56334317767ee68ba611f

head -1 file1.txt > all.txt && tail -n +2 -q file*.txt >> all.txt


cat $(ls -t) > outputfile
ls -tQ | xargs cat


