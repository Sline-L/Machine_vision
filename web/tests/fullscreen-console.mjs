// Run after npm run build. Uses a locally installed Chromium; no browser package is required.
import assert from 'node:assert/strict'
import http from 'node:http'
import path from 'node:path'
import { readFile, writeFile, mkdtemp } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'
import { spawn } from 'node:child_process'

const root = fileURLToPath(new URL('../../gp/static/', import.meta.url))
const artifacts = await mkdtemp(path.join(tmpdir(), 'gearpro-fullscreen-'))
const fixture = {
  version: 'api.v2', status: '检测运行中', error: null,
  source: { type: 'camera', video_name: null },
  inspection: { active: true, model_loaded: true },
  control: { is_owner: true, owner_label: '生产终端' },
  health: { camera: { opened: true }, serial: { connected: true } },
  settings: { mode: '自由模式', inference_profile: 'FULL', target_quantity: 100, duration_minutes: 10,
    camera_index: 0, scratch_threshold: .53, missing_hole_threshold: .61, locator_confidence: .5,
    inference_interval: .1, serial_port: '/dev/ttyUSB0', serial_baudrate: 9600, stream_fps: 15, stream_quality: 80,
    model_default_thresholds: { scratch: .53, missing_hole: .61 } },
  stats: { total: 1280, good: 1257, defective: 23, good_rate: 1257 / 1280, scratch: 15, missing_hole: 6, combined: 2 },
  result: { has_gear: true, verdict: '不合格', is_defective: true, reject_reasons: ['scratch'],
    model_versions: { scratch: 'Scratch V5', missing_hole: 'Missing Hole V1' }, elapsed_ms: 84.1,
    observations: [{ specialists: { scratch: { probability: .87 }, missing_hole: { probability: .12 } } }],
    timings: { locator_ms: 12.1, scratch: { total_ms: 36 }, missing_hole: { total_ms: 36 } } },
}
const sampleFrame = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="640" height="480" fill="#a4abb0"/><circle cx="320" cy="240" r="158" fill="#727b82" stroke="#c5cbd0" stroke-width="28" stroke-dasharray="20 12"/><circle cx="320" cy="240" r="104" fill="#b4bbc0" stroke="#505a61" stroke-width="9"/><circle cx="320" cy="240" r="46" fill="#737e85"/><path d="M378 155l24 31m-29-27 26 31" stroke="#373f44" stroke-width="3"/><rect x="362" y="146" width="50" height="56" fill="none" stroke="#c93636" stroke-width="3"/></svg>`
const server = http.createServer(async (req, res) => {
  try {
    if (req.url.startsWith('/api/v2/stream')) { res.setHeader('Content-Type', 'image/svg+xml'); res.end(sampleFrame); return }
    const relative = req.url === '/' ? 'index.html' : req.url.split('?')[0].slice(1)
    const file = path.resolve(root, relative)
    if (!file.startsWith(path.resolve(root) + path.sep)) throw Error('Invalid path')
    const content = await readFile(file)
    res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html')
    res.end(content)
  } catch { res.writeHead(404); res.end() }
})
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) })
const browser = spawn(process.env.CHROMIUM_PATH || '/usr/bin/chromium', [
  '--headless', '--no-sandbox', '--disable-gpu', '--remote-debugging-port=0',
  `--user-data-dir=${path.join(artifacts, 'browser')}`, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'] })
let stderr = '', socket
try {
  const endpoint = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(Error(stderr || 'Chromium startup timed out')), 15000)
    browser.once('error', error => { clearTimeout(timeout); reject(error) })
    browser.once('exit', () => { clearTimeout(timeout); reject(Error(stderr)) })
    browser.stderr.on('data', data => {
      stderr += data
      const match = stderr.match(/DevTools listening on (ws:\/\/\S+)/)
      if (match) { clearTimeout(timeout); resolve(match[1]) }
    })
  })
  const targets = await (await fetch(`http://127.0.0.1:${new URL(endpoint).port}/json/list`)).json()
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }))
  let sequence = 0
  const pending = new Map(), exceptions = []
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data)
    if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails)
    if (message.id) {
      const callback = pending.get(message.id)
      pending.delete(message.id)
      message.error ? callback.reject(Error(JSON.stringify(message.error))) : callback.resolve(message.result)
    }
  })
  const command = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence
    const timeout = setTimeout(() => { pending.delete(id); reject(Error(`CDP timeout: ${method}`)) }, 10000)
    pending.set(id, { resolve: value => { clearTimeout(timeout); resolve(value) }, reject: error => { clearTimeout(timeout); reject(error) } })
    socket.send(JSON.stringify({ id, method, params }))
  })
  const evaluate = async expression => {
    const response = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (response.exceptionDetails) throw Error(JSON.stringify(response.exceptionDetails))
    return response.result.value
  }
  const settle = () => new Promise(resolve => setTimeout(resolve, 120))
  const click = async text => {
    assert.equal(await evaluate(`(() => { const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim().replace(/^[▶■▣▥▷⚙]\\s*/, '')===${JSON.stringify(text)});if(!b||b.disabled)return false;b.focus();b.click();return true })()`), true, `Cannot click ${text}`)
    await settle()
  }
  const emit = async expression => { await evaluate(`${expression};window.emitState()`); await settle() }
  const snapshot = async name => {
    const shot = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
    await writeFile(path.join(artifacts, `${name}.png`), Buffer.from(shot.data, 'base64'))
  }
  await command('Runtime.enable')
  await command('Page.enable')
  await command('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.mockState=${JSON.stringify(fixture)};
    window.requests=[];window.mockFailure=null;window.pause=false;window.clockOffset=0;
    const actualNow=Date.now;Date.now=()=>actualNow()+window.clockOffset;
    window.WebSocket=class{static OPEN=1;constructor(){this.readyState=1;window.mockSocket=this;setTimeout(()=>window.emitState(),20)}send(){}close(){this.readyState=3;this.onclose?.({code:1000})}};
    window.emitState=()=>window.mockSocket?.onmessage?.({data:JSON.stringify(window.mockState)});
    setInterval(()=>{if(!window.pause&&window.mockSocket?.readyState===1)window.emitState()},500);
    window.fetch=async(url,options={})=>{
      window.requests.push({url,method:options.method||'GET',body:options.body instanceof FormData?'video':options.body});
      if(url.endsWith('/session'))return{ok:true,json:async()=>({authenticated:true,password_required:false})};
      if(window.mockFailure)return{ok:false,json:async()=>({detail:window.mockFailure})};
      if(url.endsWith('/inspection/stop'))window.mockState.inspection.active=false;
      if(url.endsWith('/inspection/start'))window.mockState.inspection.active=true;
      if(url.endsWith('/control/acquire'))window.mockState.control.is_owner=true;
      if(url.endsWith('/control/release'))window.mockState.control.is_owner=false;
      if(url.endsWith('/source/camera')){window.mockState.source.type='camera';window.mockState.inspection.active=false}
      if(url.endsWith('/source/video')){window.mockState.source={type:'video',video_name:'测试.mp4'};window.mockState.inspection.active=true}
      if(url.endsWith('/stats/reset')){window.mockState.stats={total:0,good:0,defective:0,good_rate:0};window.mockState.result=null}
      if(url.endsWith('/settings'))Object.assign(window.mockState.settings,JSON.parse(options.body));
      return{ok:true,json:async()=>window.mockState};
    };` })
  await command('Page.navigate', { url: `http://127.0.0.1:${server.address().port}/` })
  await new Promise(resolve => setTimeout(resolve, 800))
  for (const [width, height] of [[800,500],[1024,640],[1280,800],[1920,1200]]) {
    await command('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
    await settle()
    await snapshot(`detection-${width}`)
    const layout = await evaluate(`(() => {const rail=document.querySelector('.function-rail'),page=document.querySelector('.detection-page');return{overflow:document.documentElement.scrollWidth>innerWidth,railOverflow:rail.scrollHeight>rail.clientHeight+1,pageOverflow:page.scrollHeight>page.clientHeight+1,font:parseFloat(getComputedStyle(document.querySelector('dt')).fontSize),buttons:[...document.querySelectorAll('.rail-button')].every(b=>b.getBoundingClientRect().height>=44)}})()`)
    assert.equal(layout.overflow, false, `Horizontal overflow at ${width}`)
    assert.equal(layout.railOverflow, false, `Rail overflow at ${width}; ${artifacts}`)
    assert.equal(layout.pageOverflow, false, `Detection page overflow at ${width}`)
    assert(layout.font >= 16 && layout.buttons, `Small text or buttons at ${width}`)
    await snapshot(`detection-${width}`)
  }
  await command('Emulation.setDeviceMetricsOverride', { width:1024,height:640,deviceScaleFactor:1,mobile:false })
  const before = await evaluate('window.requests.length')
  await click('统计')
  assert.equal(await evaluate('document.querySelectorAll(".ring-progress").length'),3)
  assert.equal(await evaluate('document.querySelector(".ring-reading > strong").textContent'),'65.2%')
  assert.equal(await evaluate('window.requests.length'), before, 'Navigation must not mutate runtime')
  assert(await evaluate('window.mockState.inspection.active'))
  await snapshot('statistics-1024')
  await click('停止检测')
  assert.equal(await evaluate('window.mockState.inspection.active'), false)
  await click('检测')
  assert(await evaluate('document.body.textContent.includes("上次检测结果")'))
  await click('开始检测')
  assert(await evaluate('document.querySelector(".verdict-value").textContent.includes("等待结果")'))
  await emit('window.mockState.result.elapsed_ms++')
  assert(await evaluate('document.querySelector(".verdict-panel").classList.contains("bad")'))
  await click('放大画面')
  assert.equal(await evaluate('document.querySelectorAll(".camera-stage img").length'),1)
  await snapshot('expanded-1024')
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27})
  await settle()
  assert.equal(await evaluate('!!document.querySelector("[role=dialog]")'),false)
  assert.equal(await evaluate('document.activeElement.textContent.trim()'),'放大画面')
  await click('设置')
  assert.equal(await evaluate('document.body.textContent.includes("目标数量")'),false)
  await evaluate(`(() => {const s=document.querySelector('.form-grid select');s.value='定量模式';s.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  await settle()
  assert(await evaluate('document.body.textContent.includes("目标数量")'))
  await snapshot('settings-1024')
  await click('检测')
  assert(await evaluate('document.body.textContent.includes("放弃未保存修改？")'))
  await click('取消')
  assert(await evaluate('!!document.querySelector(".settings-page")'))
  await click('统计');await click('放弃并离开')
  await click('设置')
  await evaluate(`(() => {const i=document.querySelector('input[type=number]');i.value='.2';i.dispatchEvent(new Event('input',{bubbles:true}))})()`);await settle()
  await evaluate('window.mockFailure="设置保存失败"')
  await click('保存设置')
  assert(await evaluate('document.body.textContent.includes("设置保存失败")'))
  await evaluate('window.mockFailure=null')
  await click('保存设置')
  assert(await evaluate('document.body.textContent.includes("设置已保存")'))
  await evaluate(`(() => {const s=document.querySelectorAll('.form-grid select')[1];s.value='SPARSE';s.dispatchEvent(new Event('change',{bubbles:true}))})()`);await settle()
  await click('放弃修改')
  assert.equal(await evaluate('document.querySelector("input[type=number]").valueAsNumber'),0.2,'Discard must preserve the saved inference interval')
  await click('统计')
  await click('清空统计');await click('取消')
  assert.equal(await evaluate('document.activeElement.textContent.trim()'),'清空统计','Restore dialog trigger focus')
  assert.equal(await evaluate('window.requests.filter(r=>r.url.endsWith("/stats/reset")).length'),0)
  await click('清空统计');await click('确认清空')
  assert.equal(await evaluate('window.mockState.stats.total'),0)
  assert(await evaluate('[...document.querySelectorAll(".ring-reading > strong")].every(e=>e.textContent==="—")'))
  await click('视频测试')
  await snapshot('video-1024')
  const chooseVideo = async () => { await evaluate(`(() => {const dt=new DataTransfer();dt.items.add(new File(['test'],'测试.mp4',{type:'video/mp4'}));const i=document.querySelector('input[type=file]');i.files=dt.files;i.dispatchEvent(new Event('change',{bubbles:true}))})()`);await settle() }
  await chooseVideo()
  assert.equal(await evaluate('window.requests.filter(r=>r.url.endsWith("/source/video")).length'),0)
  await evaluate('window.mockFailure="视频上传失败"')
  await click('切换并开始检测')
  assert(await evaluate('document.querySelector("[role=dialog]").textContent.includes("视频上传失败")'))
  await evaluate('window.mockFailure=null')
  await click('切换并开始检测')
  assert(await evaluate('!!document.querySelector(".detection-page")'))
  assert(await evaluate('document.querySelector(".device-strip").textContent.includes("相机：未使用")'))
  await click('视频测试');await click('返回实时相机')
  assert(await evaluate('document.querySelector(".source-line").textContent.includes("实时相机")'))
  await emit('window.mockState.settings.inference_profile="SAFE_STOP"')
  assert(await evaluate('document.querySelector(".start-button").disabled'))
  await emit('window.mockState.settings.inference_profile="FULL";window.mockState.health.camera.opened=false')
  assert(await evaluate('document.querySelector(".start-button").disabled'))
  await emit('window.mockState.health.camera.opened=true;window.mockState.control.is_owner=false')
  assert(await evaluate('document.querySelector(".start-button").disabled && document.querySelector(".stop-button").disabled'))
  await click('接管控制')
  await emit(`window.mockState=${JSON.stringify(fixture)}`)
  await emit('window.mockState.result.is_defective=false;window.mockState.result.verdict="合格"')
  assert(await evaluate('document.querySelector(".verdict-panel").classList.contains("good")'))
  await emit('window.mockState.result.has_gear=false;window.mockState.result.verdict="未检测到齿轮"')
  assert(await evaluate('document.querySelector(".verdict-panel").classList.contains("idle")'))
  await emit('window.mockState.inspection.active=false;window.mockState.status="当前任务已完成"')
  assert(await evaluate('document.querySelector(".runtime-reading").textContent.includes("任务已完成")'))
  for (const [width,height] of [[800,500],[1024,640],[1280,800],[1920,1200]]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false})
    for (const [label,name] of [['统计','statistics'],['视频测试','video'],['设置','settings']]) {
      await click(label)
      assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),`Page overflow: ${name} at ${width}`)
      assert(await evaluate('document.querySelector(".stop-button").getBoundingClientRect().bottom<=innerHeight'),`Stop button inaccessible at ${width}`)
      await snapshot(`${name}-${width}`)
    }
    await click('检测')
  }
  for (const [width,height] of [[600,375],[390,600]]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false})
    await settle()
    assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),`Small-window overflow at ${width}`)
    await snapshot(`small-window-${width}`)
  }
  await command('Emulation.setDeviceMetricsOverride',{width:1024,height:640,deviceScaleFactor:1,mobile:false})
  await evaluate('window.pause=true;window.clockOffset=6000')
  await new Promise(resolve=>setTimeout(resolve,650))
  assert(await evaluate('document.body.textContent.includes("状态更新超时")'))
  assert(await evaluate('document.querySelector(".stop-button").disabled'))
  await evaluate('window.pause=false;window.emitState()');await settle()
  await evaluate('window.pause=true;window.mockSocket.close()');await settle()
  assert(await evaluate('document.body.textContent.includes("正在重新连接")'))
  await snapshot('disconnected-1024')
  await evaluate('window.pause=false;window.emitState()');await settle()
  assert.equal(exceptions.length,0,JSON.stringify(exceptions))
  console.log(`PASS: responsive 16:10 layouts, navigation, cross-page stop, stale results, settings drafts/save failure, video switch/upload failure, reset confirmation, permissions, SAFE_STOP, timeout and disconnect. Screenshots: ${artifacts}`)
} finally {
  socket?.close()
  browser.kill()
  server.close()
}
