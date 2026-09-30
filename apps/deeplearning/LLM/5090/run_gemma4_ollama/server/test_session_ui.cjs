// Run with Node; uses Python only to decode the server's embedded HTML literal.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const html = execFileSync(process.env.PYTHON || 'python', ['-c',
  "import ast, pathlib, sys; t=ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')); s=next(ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='INDEX_HTML' for x in n.targets)); sys.stdout.buffer.write(s.encode('utf-8'))",
  __dirname+'/server.py'], {encoding:'utf8'});
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
for (const script of scripts) new vm.Script(script);
const script = scripts.find(s=>s.includes('function setSessionState'));
const code = script.slice(script.indexOf('    let sessionWasActive'), script.indexOf('    async function loginSession'));
const element = ()=>({style:{},textContent:'',disabled:false,setAttribute(){}});
const fields = Array.from({length:6},element), notice=element();
let response = {logged_in:false}, status=200, offline=false;
const sandbox = {authFields:{userId:fields.slice(0,3),password:fields.slice(3)},
  saveUserButton:element(),logoutSessionButton:element(),loginSessionButton:element(),sessionStatus:element(),
  document:{getElementById:()=>notice},AbortController,setTimeout,clearTimeout,
  fetch:async()=>{if(offline)throw Error('network offline');return {status,ok:status===200,json:async()=>response};}};
vm.createContext(sandbox);vm.runInContext(code,sandbox);
(async()=>{
  await vm.runInContext('refreshSessionStatus()',sandbox);
  assert.match(notice.textContent,/로그인 세션이 없습니다/);
  response={logged_in:true,user_id:'admin'};
  await vm.runInContext('refreshSessionStatus()',sandbox);
  assert(fields.every(f=>f.style.backgroundColor==='#e0efff'));
  offline=true;await vm.runInContext('refreshSessionStatus()',sandbox);
  assert.match(notice.textContent,/확인 불가/);
  assert(fields.every(f=>f.style.backgroundColor==='#e0efff'));
  offline=false;response={logged_in:false};
  await vm.runInContext('refreshSessionStatus()',sandbox);
  assert.match(notice.textContent,/만료/);
  assert(fields.every(f=>f.style.backgroundColor==='#e5e7eb'));
  vm.runInContext("setSessionState({logged_in:true,user_id:'admin'})",sandbox);
  assert.match(notice.textContent,/인증 완료/);
  status=401;await vm.runInContext("authFetch('/api/generate')",sandbox);
  assert.match(notice.textContent,/거부/);
  assert(fields.every(f=>f.style.backgroundColor==='#e5e7eb'));
  console.log('Session UI: login, expiry, re-login, 401, network outage, all credential fields: PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
