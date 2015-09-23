### 개발 목표
  1. 1차 목표
     - 라즈베리 파이 기반 메쉬 네트워크
     - 라즈베리 파이를 이용하여 메쉬 노드 디바이스를 구현하고 이를 이용하여 구성한 로컬 메쉬 네트워크와 외부 네트워크를 연결  
  1. 2차 목표
     - 메쉬 네트워크 기반 IoT 애플리케이션
     - 센서 등의 IoT 디바이스를 연동해서 메쉬 네트워크의 실제적인 효용성을 검증 


### 현재 진행 상황(2015년 9월 23일)
  1. 세부 목표 별 진행 상황
    - 와이파이 네크워크 구성
      + 라즈베리 파이에 와이파이 동글을 장착하여 ad-hoc 네트워크 구성
      + 테스트된 동글
        * RTL8188CUS(8192CU) 칩셋
          - Whezzy, Archlinux 모두 nl80211 미지원으로 메쉬 네트워크 구현 불가
          - nl80211 지원 가능하도록 커널 드라이버 수정해도 정상 동작하지 않음
          - 라즈베리 파이 외 다른 플랫폼에서는 드라이버 수정 후 nl80211 지원하지만 iw, wpa_supplicant 등의 툴도 전용으로 customize 해야 하기 때문에 reject
        * BCM43143 칩셋(http://www.adafruit.com/product/2638)
          - Whezzy, Archlinux 모두 nl80211 지원하고 일부 제약사항 있지만 메쉬 네트워크 구현 가능
      + 테스트된 네트워크 매니징 툴
        * iwconfig
          - 가장 simple하지만 부가 관리 기능이 없어서 유용하지 않음
          - Broken link 처리하려면 재시작 해야함
          - Whezzy, Archlinux 모두 정상 동작하지 않음
        * wpa_supplicant
          - 안드로이드도 쓰고 있는 client 용으로는 최상이지만 메쉬 네트워크용으로는 부적절
          - nl80211을 쓰는 것이 좋고 Whezzy, Archlinux 모두 정상 동작
        * iw
          - WPA를 지원하지 않아서 client 용으로는 적합하지 않지만 메쉬 네트워크용으로는 최선
          - nl80211만 지원하므로 BCM43143 칩셋 같은 호환 동글을 사용해야함
          - Wheezy는 iw 4.x 버전을 manual build 해야 ad-hoc 동작
          - Archlinux는 정상 동작
          - 칩셋 및 드라이버에 따라 지원하는 기능이 다름, 가령 ad-hoc 보다 유리한 mesh point 연결을 사용할 수도 있음
        * hostapd
          - iw 연동 VLAN 테스트를 위해 적용
          - nl80211로 정상 동작하지만 ad-hoc과는 exclusive 
    - 메쉬 네트워크 구성
      + Babeld
        * Whezzy 및 Archilinux 패키지 없음
        * 테스트 용으로 초기 검토 후 reject
      + BATMAN(http://www.open-mesh.org)
        * batman-adv는 커널에 포함되어 있음
        * Archlinux는 batman-adv, batctl 설치 시 packer 패치가 필요함
        * Alfred를 설치해야 batadv-vis 등의 추가 기능을 사용할 수 있고 Wheezy는 빌드 패치해야 함
        * 3 hop 구성으로 정상 동작
        * Wheezy, Archlinux 조합으로 hop 연결도 문제 없음
        * Alfred의 경우 Wheezy에서는 IPV6 활성화해야 하고 master, slave 모두 오동작하는 경우가 있음
        * 향후 alfred 아키텍쳐 참고해서 batman-adv 만으로 simple manipulation 기능 구현 필요
      + OpenWRT
         * 배트맨이 내장되어 있으나 패키지 형태가 아니기 때문에 향후 customize 등에 결정적인 제약이 생김
         * Arduino YUN 테스트 중 홀드
      + OSLR
         * MANET를 위한 메쉬 솔루션의 standard이자 끝판왕이지만 Too much
    - 외부 네트워크 연결
      + 마스터 노드에 이더넷을 이용해서 packet forwarding 및 NAT 설정
      + 슬레이브 노드에 route 설정 및 DNS 설정
      + IP allocation은 DHCP 혹은 Avahi 모두 정상 동작
      + Wheezy의 경우 avahi-browse 등을 추가 설정해야 함
      + Avahi 사용 시 mDNS/DNS-SD 기능을 fully 적용할 수 있으나 Archlinux에서는 설정에 문제 있음
      + 메쉬 네트워크(ad-hoc 기반)의 특성 상 bandwidth 문제가 있음
  1. 문제점
    - 하드웨어 디펜던시(와이파이 디바이스 선택)
      + 현재 BCM43143으로 최소한의 구현이 가능하지만 여전히 제약 사항이 있음
      + nl80211 지원하는 칩셋, 드라이버셋을 써야 함
      + ad-hoc이나 mesh point를 제대로 지원해야 함
      + iw의 link detection 과 호환이 되지 않으면 broken link를 확인하는 방법이 지저분해짐
      + minor 하지만 WDS 지원 여부
      + Multiple SSIDs 혹은 VLAN tagging 지원 여부가 상당히 중요함
      + BCM43143의 nl80211 capability 정보에는 지원한다고 enumeration 되어 있지만 실제 동작하지 않음
      + 최악의 경우 virtual interface가 아닌 phy를 추가해서 AP 기능을 제공할 수 밖에 없음
      + Open-Mesh의 경우 관련 기능들을 모두 제공하는 칩셋(Atheros)을 사용하고 있음
      + 즉, station 급이 아닌 AP 급의 고가 디바이스가 필요할 수 있음
    - 전체 네크워크 스킴에 대한 선택
      + 메쉬 네트워크 위에 얹을 네트워크 스킴, 가령 Zero configuration을 적용할 것인 지 NAT traversal을 적용할 것인 지 등의 고민과 실질적인 검증이 필요함
  1. 검증 안된 사항
    - 4 hop 이상의 구성 및 range for stable link 테스트
    - BATMAN gateway
    - 자동 로밍
    - 멀티 링크
    - RF interference 혹은 broken link 관리 등


### 향후 계획
  1. 세부 목표(10월말까지)
    - 슬레이브 노드 패키지 개발
    - 마스터 노드 패키지 개발
      + 옵션 1 : DHCP로 로컬네트워크 구성 가능한 AP 포함
      + 옵션 2 : Zero configuration 및 NAT traveral 적용
      + 옵션 3 : Wheezy 뿐만 아니라 Archlinux 용 패키지
  1. 추가 검토 사항
    - Zero configuration 및 NAT traversal 검증
    - 에디슨 등의 타 H/W 플랫폼 검증
    - 핸디캡이 최소화된 cost efficient한 디바이스 수배
