URL="****.com"; FURL=$URL":8881"; openssl s_client -connect $FURL -servername $URL 2>/dev/null | openssl x509 -noout -dates
