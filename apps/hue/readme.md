## Hue 게이트웨이 버튼 클릭, 아이디 입력, send message, key return


<pre>

Button Press 

curl -d '{"devicetype":"[{아이디-plain-text}]"}' -H "Content-Type: application/json" -X POST 'http://{주소}/api'
  회신 : [{"success":{"username":"{아이디-key}"}}]

curl 'http://{주소}/api/{아이디}/lights'

curl -X PUT -H 'Content-Type: application/json' -d '{"on":true}' 'http://{주소}/api/{아이디-key}/lights/{light번호}/state'

</pre>
 
