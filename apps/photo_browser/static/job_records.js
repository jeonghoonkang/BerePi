/* Job timestamps and explicit server-side TXT archiving. */
(() => {
  const active = status => ['queued', 'running', 'stopping'].includes(status);
  function formatTime(value) {
    const date = Date.parse(value);
    return Number.isFinite(date) ? new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul', dateStyle: 'medium', timeStyle: 'medium',
    }).format(new Date(date)) + ' (KST)' : '기록 없음';
  }
  function timingText(status, currentTime) {
    const p = status.result || status.progress || {};
    const started = status.started_at || p.started_at;
    const finishedLabel = status.status === 'completed' ? '완료 시각' : '종료 시각';
    const parts = [`시작 시각: ${status.status === 'queued' ? '대기 중' : formatTime(started)}`,
      `${finishedLabel}: ${active(status.status) ? '대기 중 / 진행 중' : formatTime(status.finished_at)}`];
    const firstMerge = p.merge_started_at || status.merge_started_at;
    if (status.kind === 'merge') parts.push(`최초 병합 시작: ${status.status === 'queued' ? '대기 중' : formatTime(firstMerge || started)}`);
    const start = Date.parse(status.kind === 'merge' ? firstMerge || started : started);
    const end = active(status.status) ? currentTime : Date.parse(status.finished_at);
    if (status.status !== 'queued' && Number.isFinite(start) && Number.isFinite(end)) {
      let seconds = Math.max(0, Math.floor((end - start) / 1000));
      const days = Math.floor(seconds / 86400); seconds %= 86400;
      const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds % 3600 / 60);
      parts.push(`경과 시간: ${days ? days + '일 ' : ''}${String(hours).padStart(2, '0')}시간 ${String(minutes).padStart(2, '0')}분 ${String(seconds % 60).padStart(2, '0')}초`);
    }
    return parts.join(' · ');
  }
  function createArchiveControls(request) {
    const root = document.createElement('section'), button = document.createElement('button');
    const message = document.createElement('p');
    button.type = 'button'; button.textContent = '보관 (TXT)';
    message.setAttribute('role', 'status'); message.setAttribute('aria-live', 'polite');
    message.style.overflowWrap = 'anywhere';
    root.append(button, message);
    let job, busy = false, savedPath = '';
    const showPath = () => { message.textContent = savedPath ? `TXT 보관 경로 (서버): ${savedPath}` : ''; };
    button.onclick = async () => {
      if (!job || busy || active(job.status)) return;
      busy = true; button.disabled = true; message.textContent = '작업 기록을 TXT 파일로 보관하고 있습니다…';
      try {
        const result = await request(`api/jobs/${encodeURIComponent(job.job_id)}/archive`, 'POST', {});
        savedPath = result.path;
        showPath();
      } catch (error) {
        message.textContent = `보관 실패: ${error.message}` + (savedPath ? ` · 기존 TXT 경로: ${savedPath}` : '');
      } finally { busy = false; button.disabled = active(job.status); }
    };
    return {root, update(status) {
      job = status; savedPath = status.archive?.path || savedPath;
      button.disabled = busy || active(job.status);
      if (!busy) {
        showPath();
        if (!savedPath && active(job.status)) message.textContent = '작업 종료 후 TXT로 보관할 수 있습니다.';
      }
    }};
  }
  function mergeEstimateText(progress) {
    if (progress?.merge_elapsed_seconds == null) return '';
    const duration = value => {
      const seconds = Math.max(0, Math.round(Number(value)));
      return `${Math.floor(seconds / 60).toLocaleString()}분 ${seconds % 60}초 (${(seconds / 60).toFixed(2)}분)`;
    };
    const parts = [`이번 실행 소요: ${duration(progress.merge_elapsed_seconds)}`];
    const kind = progress.eta_sample_kind === 'fast_skip' ? '빠른 건너뛰기' : '복사·검증';
    if (progress.eta_sample_target == null) {
      parts.push('예상 시간: 파일 처리 표본 수집 전');
    } else if (!progress.eta_ready) {
      parts.push(`예상 시간 계산 중: ${kind} ${progress.eta_sample_files || 0}/${progress.eta_sample_target}개 측정`);
    } else {
      parts.push(`최근 ${progress.eta_sample_files}개 ${kind}: ${duration(progress.eta_sample_seconds)}`);
      if (progress.estimated_remaining_seconds === 0) {
        parts.push('파일 처리 완료 · DB·보고서 마무리 시간은 별도');
      } else {
        parts.push(`예상 남은 시간: ${duration(progress.estimated_remaining_seconds)}`);
        parts.push(`예상 총소요: ${duration(progress.estimated_total_seconds)}`);
        parts.push(`파일 처리 종료 예상: ${formatTime(progress.estimated_finish_at)}`);
      }
    }
    return parts.join(' · ');
  }
  window.photoBrowserJobRecords = {formatTime, timingText, createArchiveControls, mergeEstimateText};
})();
