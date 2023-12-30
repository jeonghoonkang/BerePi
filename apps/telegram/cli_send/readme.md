### Sending file via Telegram on Command line console
- https://steemit.com/utopian-io/@yuxid/how-to-send-text-and-files-to-other-devices-in-linux-command-line-via-telegram
- installation
  - pip3 install telegram-send
  - 에러발생시 다시 버전 정확히 설치 (2023.9.25)

### How to use
- telegram-send -f FILENAME
- cat {file} | telegram-send --stdin

#### Installation issue

- pip3 install --force-reinstall -v "python-telegram-bot==13.5"
  - to solve this error
<pre> ImportError: cannot import name 'MAX_MESSAGE_LENGTH' from 'telegram.constants' (/home/user/.local/lib/python3.10/site-packages/telegram/constants.py) </pre>

#### Python 3.8 Problem
<pre>
sudo apt-get remove python3.8
sudo apt-get remove --auto-remove python3.8
sudo apt-get purge python3.8
sudo apt-get purge --auto-remove python3.8
</pre>
