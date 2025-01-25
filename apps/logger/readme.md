# Logging 라이브러리
## berelogger import 방법 
<pre>
import sys
sys.path.append("/home/***/devel/BerePi/apps/logger")
import berepi_logger
</pre>
## 파일 사이즈 limit 지원
### rotateHandler
- logger

# BASH logger
<code> while true; do tail 파일; echo "---------- split line ----------"; echo " "; sleep 30; done;  
  </code>
