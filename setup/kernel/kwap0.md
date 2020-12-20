kswapd0 프로세서가 CPU 사용율 100% 사용 하여, 지속적으로 실행되는 경우 
/etc/sysctl.conf 파일에 추가한 내용 

(ubuntu에서 동작안함)

vm.swappiness=60
vm.vfs_cache_pressure=30
vm.dirty_background_ratio=10
vm.dirty_ratio=30
