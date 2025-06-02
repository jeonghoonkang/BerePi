# Author : https://github.com/jeonghoonkang
# DNS URL expire check
# 도메인 기간 SSL 

# URL="****.com"; echo $URL; FURL=$URL":8881"; openssl s_client -connect $FURL -servername $URL 2>/dev/null | openssl x509 -noout -dates


#!/bin/bash
# Check if SSL certificate expires within 2 weeks
URL="$1"
PORT="${2:-443}"
THRESHOLD_DAYS=14

if [ -z "$URL" ]; then
    echo "Usage: $0 <domain> [port]" >&2
    exit 1
fi

end_date=$(openssl s_client -servername "$URL" -connect "$URL:$PORT" 2>/dev/null \
    | openssl x509 -noout -enddate | cut -d= -f2)

if [ -z "$end_date" ]; then
    echo "Failed to retrieve certificate for $URL" >&2
    exit 2
fi

end_ts=$(date -d "$end_date" +%s)
current_ts=$(date +%s)
diff_days=$(( (end_ts - current_ts) / 86400 ))

if [ "$diff_days" -le "$THRESHOLD_DAYS" ]; then
    echo "SSL certificate for $URL expires in $diff_days days (within 2 weeks)"
else
    echo "SSL certificate for $URL expires in $diff_days days" | telegram-send --stdin # should check telegram-send is working or not
fi
