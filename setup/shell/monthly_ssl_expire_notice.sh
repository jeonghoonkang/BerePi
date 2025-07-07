#!/bin/bash
# Author: https://github.com/jeonghoonkang
# openssl 을 이용하여 HTTPS 인증서 만료일을 확인하고 telegram-send 로 전송
# Usage: $0 <domain> [port]
# Example crontab (매달 1일 오전 9시):
# 0 9 1 * * bash /home/tinyos/devel/BerePi/setup/shell/monthly_ssl_expire_notice.sh example.com

DOMAIN="$1"
PORT="${2:-443}"
if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain> [port]" >&2
    exit 1
fi

end_date=$(openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:$PORT" 2>/dev/null \
    | openssl x509 -noout -enddate | cut -d= -f2)

if [ -z "$end_date" ]; then
    echo "Failed to retrieve certificate for $DOMAIN" >&2
    exit 2
fi

message="SSL certificate for $DOMAIN expires on $end_date"
echo "$message" | telegram-send --stdin

