### Sending file via Telegram on Command line console
- https://steemit.com/utopian-io/@yuxid/how-to-send-text-and-files-to-other-devices-in-linux-command-line-via-telegram
- pip3 install telegram-send


#### installation issue

- pip3 install --force-reinstall -v "python-telegram-bot==13.5"
  - to solve this error
<pre> ImportError: cannot import name 'MAX_MESSAGE_LENGTH' from 'telegram.constants' (/home/user/.local/lib/python3.10/site-packages/telegram/constants.py) </pre>
