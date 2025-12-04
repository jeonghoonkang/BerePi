#!/bin/bash
# Author : github.com/jeonghoonkang
# Check if SSL certificate expires within 2 weeks


usage() { echo "Usage: $0 [-p port] <domain>" >&2; exit 1; }

PORT=443
while getopts ":p:" opt; do
    case "$opt" in
        p) PORT="$OPTARG" ;;
        *) usage ;;
    esac
done
shift $((OPTIND-1))

URL="$1"
THRESHOLD_DAYS=14

if [ -z "$URL" ]; then
    usage
fi

echo "### starting openssl ###'
echo "### It takes time ###'

end_date=$(openssl s_client -servername "$URL" -connect "$URL:$PORT" 2>/dev/null \
    | openssl x509 -noout -enddate | cut -d= -f2)

if [ -z "$end_date" ]; then
    echo "Failed to retrieve certificate for $URL" >&2
    exit 2
fi

end_ts=$(date -d "$end_date" +%s)
current_ts=$(date +%s)
diff_days=$(( (end_ts - current_ts) / 86400 ))

formatted_end_date=$(date -d "$end_date" '+%m월 %d일 %A')

if [ "$diff_days" -le "$THRESHOLD_DAYS" ]; then
    echo "SSL certificate for $URL:$PORT expires on $formatted_end_date (within 2 weeks)"
else
    echo "SSL certificate for $URL:$PORT expires on $formatted_end_date"
fi


