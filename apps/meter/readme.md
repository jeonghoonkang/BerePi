
  - 911 meter 적용 방법
    - 라즈베리파이 CGI 인터페이스로 데이터 처리, 표현
    - 누진단계에 따른 측정 -> 비용계산 루틴 추가 완료
    - RESTful API, MySQL API 지원 

  - 전력측정 방법
    - JSON 인터페이스
    - 시스템 통합
    - CT 센서
    
  - 전력미터기 API
    - http://IP:4242/api/query?start=2015/06/26-00:00:00&m=sum:gyu_RC1_etype.t_current{nodeid=911}
    - http://IP:4242/#start=24h-ago&m=sum:gyu_RC1_thl.temperature{nodeid=924}&o=axis%20x1y2&m=sum:gyu_RC1_thl.batt{nodeid=923}&o=&m=sum:gyu_RC1_thl.temperature{nodeid=916}&o=axis%20x1y2&yrange=[2000:3100]&key=out%20bottom%20center&wxh=400x300&autoreload=15


    - http://IP:4242/api/query?start=1m-ago&m=sum:gyu_RC1_etype.t_current{nodeid=911}
    

