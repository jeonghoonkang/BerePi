/* Address lookup runs on the server, never against the browser's public IP. */
(() => {
  const internal = document.getElementById('server-internal-ip');
  const external = document.getElementById('server-external-ip');
  async function update() {
    let delay = 60000;
    try {
      const response = await fetch('api/server-network', {cache: 'no-store'});
      if (!response.ok) throw new Error('Address lookup failed');
      const data = await response.json();
      internal.textContent = data.internal_ips.length ? data.internal_ips.join(', ') : (data.refreshing ? '조회 중…' : '감지되지 않음');
      external.textContent = data.external_ip || (data.refreshing ? '조회 중…' : '조회 불가');
      external.title = data.external_ip ? '서버의 외부 통신에 사용되는 공인 IP (NAT·VPN·프록시 환경에 따라 달라질 수 있음)' : '인터넷 연결 또는 공인 IP 조회 서비스 접근을 확인하세요.';
      if (data.refreshing) delay = 1000;
    } catch (_) {
      internal.textContent = '조회 불가';
      external.textContent = '조회 불가';
    } finally {
      setTimeout(update, delay);
    }
  }
  update();
})();
