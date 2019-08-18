- rsync 전송 속도 설정 방법
[root@ns1 ~/job]# time rsync --bwlimit=5120 --partial  -v ns2::R`pwd`/tmpfs1G .

- 참고 : http://coffeenix.net/board_view.php?bd_code=1418
