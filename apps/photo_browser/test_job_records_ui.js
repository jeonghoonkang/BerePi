const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function main() {
  const scope = {window: {}, document: {createElement(tag) {
    return {tag, children: [], style: {}, textContent: '', append(...nodes) { this.children.push(...nodes); }, setAttribute() {}};
  }}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/job_records.js'), 'utf8'), scope);
  const {formatTime, timingText, createArchiveControls} = scope.window.photoBrowserJobRecords;
  const job = {job_id: 'scanjob', kind: 'scan', status: 'completed',
    started_at: '2026-11-02T00:00:00Z', finished_at: '2026-11-02T01:02:03Z'};
  const text = timingText(job, Date.now());
  assert.ok(text.includes(`시작 시각: ${formatTime(job.started_at)}`));
  assert.ok(text.includes(`완료 시각: ${formatTime(job.finished_at)}`));
  assert.match(text, /01시간 02분 03초/);
  assert.match(formatTime(job.finished_at), /KST/);
  assert.equal(formatTime(undefined), '기록 없음');
  assert.match(timingText({...job, status: 'running'}, Date.parse('2026-11-02T00:10:00Z')), /00시간 10분 00초/);
  assert.match(timingText({...job, status: 'queued', started_at: undefined}, Date.now()), /시작 시각: 대기 중/);
  assert.doesNotMatch(timingText({...job, kind: 'merge', status: 'queued', merge_started_at: job.started_at}, Date.now()), /경과 시간/);
  assert.match(timingText({status: 'failed'}, Date.now()), /종료 시각: 기록 없음/);
  const resumed = timingText({...job, kind: 'merge', merge_started_at: '2026-11-01T00:00:00Z'}, Date.now());
  assert.match(resumed, /최초 병합 시작/);
  assert.match(resumed, /1일 01시간 02분 03초/);

  let calls = 0, resolveSave;
  const archive = createArchiveControls(async (url, method) => {
    calls++;
    assert.equal(url, 'api/jobs/scanjob/archive');
    assert.equal(method, 'POST');
    return new Promise(resolve => { resolveSave = resolve; });
  });
  archive.update(job);
  const [button, message] = archive.root.children;
  const saving = button.onclick();
  assert.equal(button.disabled, true);
  await button.onclick();
  assert.equal(calls, 1);
  resolveSave({path: '/data/db/job-archives/scanjob.txt'});
  await saving;
  assert.equal(button.disabled, false);
  assert.match(message.textContent, /TXT 보관 경로 \(서버\):/);
  assert.ok(message.textContent.includes('/data/db/job-archives/scanjob.txt'));
  archive.update({...job, status: 'running'});
  assert.equal(button.disabled, true);
  await button.onclick();
  assert.equal(calls, 1);

  const restored = createArchiveControls(async () => { throw new Error('disk full'); });
  restored.update({...job, archive: {path: '/data/db/job-archives/scanjob.txt'}});
  const [retry, saved] = restored.root.children;
  assert.ok(saved.textContent.includes('/data/db/job-archives/scanjob.txt'));
  await retry.onclick();
  assert.match(saved.textContent, /보관 실패: disk full/);
  assert.ok(saved.textContent.includes('/data/db/job-archives/scanjob.txt'));
  assert.equal(retry.disabled, false);
  console.log('Job records UI: KST timestamps, durations, TXT paths, retries and active-job protection passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
