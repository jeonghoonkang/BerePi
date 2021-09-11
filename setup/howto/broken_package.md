apt install 문제발생
install 불가 

Open the /var/log/dist-upgrade/apt.log log file in a text editor.

Locate any "broken" packages and remove them with sudo apt-get remove <package>.
  
Note: in newer versions, the log is located in /var/log/apt/term.log instead.
