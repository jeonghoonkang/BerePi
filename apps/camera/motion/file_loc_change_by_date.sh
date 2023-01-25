
mkdir /volume1/video/$(date +%Y-%m-%d\(%a\))


for f in /volume1/video/*; do
  # skip over directories
  [ -f "$f" ] || continue
  # grep the date in YYMMDD format
  date=$(printf '%s' "$f" | grep -Eo '[0-9]{6}')
  # set target path using date to convert YYMMDD to YYYY-MM-DD(%a)
  target="/volume1/video/daily/$(date -d "$date" +%Y-%m-%d\(%a\))/"
  # mv the file
  echo mv "$f" "$target"
done

