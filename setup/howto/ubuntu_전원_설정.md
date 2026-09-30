
### 일정시간동안 움직임 없으면, sleep 하는 기능 방지
- ubuntu release 업그레이드하면, 기본적으로 입력없을때 sleep 전환하는 것으로 확인함 (2026/10)
 <code> sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target </code>
 <code> 1995  systemctl is-enabled sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target</code>
