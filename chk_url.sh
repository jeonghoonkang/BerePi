# Author : https://github.com/jeonghoonkang
# DNS URL expire check
# 도메인 기간 SSL 
URL="****.com"; echo $URL; FURL=$URL":8881"; openssl s_client -connect $FURL -servername $URL 2>/dev/null | openssl x509 -noout -dates
