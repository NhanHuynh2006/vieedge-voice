// The phone is the microphone and the speaker of the Pi: mic -> 16 kHz int16 -> /audio (binary WebSocket); speech <- /audio.
// getUserMedia is only allowed on https (or localhost), so this page is served on the https port with a self-signed certificate.
(() => {
  const $ = (id) => document.getElementById(id);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const MIC_RATE = 16000, FRAME = 320;            // 20 ms frames, like the sound-card period on the Pi
  let ctl, aws, mic, play, nextT = 0, outRate = 22050, on = false, stream, node, lastRx = 0;
  let state = "idle", micLevel = 0, outLevel = 0, shownLevel = 0, liveMe = null, liveBot = null, turnHasUser = false;

  const NAMES = { idle: "Sẵn sàng", listening: "Đang nghe", thinking: "Đang nghĩ", speaking: "Đang nói", booting: "Khởi động" };
  const WORKLET = `
  class P extends AudioWorkletProcessor {
    constructor() { super(); this.r = sampleRate / ${MIC_RATE}; this.t = 0; this.o = new Int16Array(${FRAME}); this.n = 0; this.last = 0; this.pk = 0; }
    process(inp) {
      const x = inp[0] && inp[0][0]; if (!x) return true;
      for (; this.t < x.length; this.t += this.r) {
        const i = Math.floor(this.t), f = this.t - i, a = i < 0 ? this.last : x[i], b = x[Math.min(i + 1, x.length - 1)];
        const v = Math.max(-1, Math.min(1, a + (b - a) * f)); this.pk = Math.max(this.pk, Math.abs(v));
        this.o[this.n++] = v < 0 ? v * 32768 : v * 32767;
        if (this.n === ${FRAME}) { this.port.postMessage({ pcm: this.o.buffer.slice(0), pk: this.pk }, []); this.n = 0; this.pk = 0; }
      }
      this.t -= x.length; this.last = x[x.length - 1]; return true;
    }
  }
  registerProcessor('pcm16k', P);`;

  // ------------------------------------------------------------------ voice orb
  const orb = $("orb"), g = orb.getContext("2d");
  const colour = () => ({ idle: css("--faint"), listening: css("--listen"), thinking: css("--think"), speaking: css("--speak"), booting: css("--faint") }[state] || css("--accent"));
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  function drawOrb(ts) {
    const W = orb.width, H = orb.height, cx = W / 2, cy = H / 2, R = W * 0.22, t = ts / 1000;
    g.clearRect(0, 0, W, H);
    const live = state === "listening" ? micLevel : state === "speaking" ? outLevel : 0;
    shownLevel += (live - shownLevel) * 0.18;
    const lvl = Math.min(1, shownLevel * 2.2), c = colour();
    const breathe = reduce ? 0 : Math.sin(t * 1.4) * 0.025;
    // soft halo
    const halo = g.createRadialGradient(cx, cy, R * 0.6, cx, cy, W * 0.5);
    halo.addColorStop(0, c + "55"); halo.addColorStop(1, c + "00");
    g.fillStyle = halo; g.beginPath(); g.arc(cx, cy, W * 0.5, 0, 7); g.fill();
    // ripples (speaking) or level rings (listening)
    g.lineWidth = 3;
    if (state === "speaking" || state === "listening") {
      for (let i = 0; i < 3; i++) {
        const ph = reduce ? i / 3 : ((t * 0.55 + i / 3) % 1);
        g.strokeStyle = c + Math.round((1 - ph) * 110 + 20).toString(16).padStart(2, "0");
        g.beginPath(); g.arc(cx, cy, R * (1.15 + ph * (0.9 + lvl * 0.7)), 0, 7); g.stroke();
      }
    }
    // thinking: orbiting arcs
    if (state === "thinking") {
      for (let i = 0; i < 3; i++) {
        const a0 = (reduce ? 0 : t * (1.6 + i * 0.5)) + i * 2.1;
        g.strokeStyle = c + (i === 0 ? "ff" : "99"); g.lineWidth = 5 - i;
        g.beginPath(); g.arc(cx, cy, R * (1.3 + i * 0.18), a0, a0 + 1.5); g.stroke();
      }
    }
    // core disc
    const r = R * (1 + breathe + lvl * 0.28);
    const core = g.createRadialGradient(cx - r * 0.3, cy - r * 0.35, r * 0.1, cx, cy, r);
    core.addColorStop(0, c); core.addColorStop(1, c + "aa");
    g.fillStyle = core; g.beginPath(); g.arc(cx, cy, r, 0, 7); g.fill();
    g.fillStyle = css("--bg") + "d9";                       // microphone glyph
    const mw = r * 0.26, mh = r * 0.5;
    g.beginPath(); g.roundRect(cx - mw, cy - mh * 0.9, mw * 2, mh * 1.3, mw); g.fill();
    g.lineWidth = r * 0.07; g.strokeStyle = css("--bg") + "d9"; g.beginPath(); g.arc(cx, cy - mh * 0.05, mw * 1.7, 0.15 * Math.PI, 0.85 * Math.PI); g.stroke();
    g.beginPath(); g.moveTo(cx, cy + mh * 0.62); g.lineTo(cx, cy + mh * 0.95); g.stroke();
    micLevel *= 0.92; outLevel *= 0.9;
    requestAnimationFrame(drawOrb);
  }
  requestAnimationFrame(drawOrb);

  // ------------------------------------------------------------------ chat
  function bubble(cls, text) {
    const b = document.createElement("div"); b.className = "bubble " + cls; b.textContent = text;
    $("chat").appendChild(b); $("hint").hidden = true; b.scrollIntoView({ block: "end", behavior: reduce ? "auto" : "smooth" }); return b;
  }
  function setState(s) {
    state = s; const b = $("b-state"); b.textContent = NAMES[s] || s; b.className = "badge state " + s;
    $("stage-label").textContent = on ? (NAMES[s] || s) : "Chạm để bắt đầu";
  }
  function setRag(on) { const b = $("b-rag"); b.dataset.on = on ? "1" : "0"; b.textContent = "Tra cứu: " + (on ? "bật" : "tắt"); b.style.color = on ? "var(--ink)" : "var(--muted)"; }
  function chip(k, v) { const c = document.createElement("span"); c.className = "chip"; c.innerHTML = `${k} <b>${v}</b>`; return c; }

  function connectCtl() {
    ctl = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ctl.onmessage = (m) => {
      const ev = JSON.parse(m.data);
      if (ev.type === "hello" || ev.type === "state") setState(ev.state);
      if ((ev.type === "hello" || ev.type === "config") && ev.rag !== undefined) setRag(ev.rag);
      else if (ev.type === "partial") { if (!liveMe) liveMe = bubble("me live", ""); liveMe.textContent = ev.text; }
      else if (ev.type === "final") {
        if (!liveMe && ev.text) liveMe = bubble("me", "");
        if (liveMe) { liveMe.classList.remove("live"); liveMe.textContent = ev.text || "(không nghe rõ)"; }
        liveMe = null; liveBot = bubble("bot live", "…"); $("chips").innerHTML = "";
      } else if (ev.type === "token") { if (!liveBot) liveBot = bubble("bot live", ""); liveBot.textContent = (liveBot.textContent === "…" ? "" : liveBot.textContent) + ev.text; }
      else if (ev.type === "answer_done") { if (liveBot) { liveBot.textContent = ev.text; liveBot.classList.remove("live"); } liveBot = null; }
      else if (ev.type === "reflex") { if (!liveBot) liveBot = bubble("bot", ""); liveBot.classList.remove("live"); liveBot.textContent = ev.text; liveBot = null; }
      else if (ev.type === "turn") {
        const m = ev.metrics || {}, c = $("chips"); c.innerHTML = "";
        if (m.first_audio_ms != null) c.appendChild(chip("tiếng đầu", (m.first_audio_ms / 1000).toFixed(2) + " s"));
        if (m.stt_after_speech_ms != null) c.appendChild(chip("nghe", Math.round(m.stt_after_speech_ms) + " ms"));
        if (ev.meta && ev.meta.llm_tok_s) c.appendChild(chip("tốc độ", ev.meta.llm_tok_s + " tok/s"));
        if (ev.meta && ev.meta.fast) c.appendChild(chip("đường", "nhanh"));
      }
    };
    ctl.onopen = () => { $("b-link").textContent = "Pi · " + location.hostname; };
    ctl.onclose = () => { $("b-link").textContent = "Mất kết nối"; setTimeout(connectCtl, 1500); };
  }

  // ------------------------------------------------------------------ speech from the Pi
  function playChunk(buf) {
    const i16 = new Int16Array(buf), n = i16.length;
    if (!n || !play) return;
    const now = play.currentTime;
    let silent = true, pk = 0;
    for (let k = 0; k < n; k += 8) { const a = Math.abs(i16[k]); if (a > pk) pk = a; }
    if (pk > 40) silent = false;
    if (!silent) outLevel = Math.max(outLevel, pk / 14000);
    if (silent && nextT - now > 0.2) return;       // drop idle silence if we are ahead (keeps the delay low)
    const f = new Float32Array(n);
    for (let k = 0; k < n; k++) f[k] = i16[k] / 32768;
    const ab = play.createBuffer(1, n, outRate);
    ab.copyToChannel(f, 0);
    const src = play.createBufferSource();
    src.buffer = ab; src.connect(play.destination);
    const t = Math.max(now + 0.06, nextT);          // 60 ms jitter buffer
    src.start(t); nextT = t + n / outRate;
  }

  function connectAudio() {
    aws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/audio`);
    aws.binaryType = "arraybuffer";
    aws.onmessage = (m) => {
      lastRx = performance.now();
      if (typeof m.data === "string") {
        const h = JSON.parse(m.data);
        if (h.type === "hello") { outRate = h.rate; $("stage-sub").textContent = "Đã kết nối. Hãy nói tiếng Việt."; setState(state); }
        else if (h.type === "error") { $("stage-sub").textContent = h.message; on = false; }
      } else playChunk(m.data);
    };
    aws.onclose = () => { if (on) { $("stage-sub").textContent = "Mất kết nối, đang nối lại…"; setTimeout(connectAudio, 1500); } };
  }

  function send(buf, pk) {
    if (aws && aws.readyState === 1) aws.send(buf);
    micLevel = Math.max(micLevel, pk);
  }

  async function start() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      $("stage-sub").textContent = "Trình duyệt chỉ cho dùng micro trên https. Mở https://" + location.hostname + ":8443/phone rồi chấp nhận cảnh báo chứng chỉ.";
      return;
    }
    mic = new (window.AudioContext || window.webkitAudioContext)();
    play = new (window.AudioContext || window.webkitAudioContext)();
    await Promise.all([mic.resume(), play.resume()]);
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: false, channelCount: 1 } });
    } catch (e) { $("stage-sub").textContent = "Không mở được micro: " + e.name; return; }
    const src = mic.createMediaStreamSource(stream);
    if (mic.audioWorklet) {
      const url = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));
      await mic.audioWorklet.addModule(url);
      node = new AudioWorkletNode(mic, "pcm16k");
      node.port.onmessage = (e) => send(e.data.pcm, e.data.pk);
      src.connect(node); node.connect(mic.destination);
    } else {                                                // old browsers: main-thread fallback
      const sp = mic.createScriptProcessor(2048, 1, 1), r = mic.sampleRate / MIC_RATE;
      let t = 0, o = new Int16Array(FRAME), n = 0, pk = 0;
      sp.onaudioprocess = (e) => {
        const x = e.inputBuffer.getChannelData(0);
        for (; t < x.length; t += r) {
          const v = Math.max(-1, Math.min(1, x[Math.floor(t)])); pk = Math.max(pk, Math.abs(v));
          o[n++] = v < 0 ? v * 32768 : v * 32767;
          if (n === FRAME) { send(o.buffer.slice(0), pk); n = 0; pk = 0; }
        }
        t -= x.length;
      };
      src.connect(sp); sp.connect(mic.destination);
    }
    on = true; connectAudio();
    $("go").textContent = "Tắt micro và loa"; $("go").classList.add("on"); setState(state);
  }

  function stop() {
    on = false;
    try { aws && aws.close(); } catch (e) { /* closing */ }
    if (stream) stream.getTracks().forEach((t) => t.stop());
    if (mic) mic.close(); if (play) play.close();
    mic = play = null; nextT = 0;
    $("go").textContent = "Bật micro và loa"; $("go").classList.remove("on");
    $("stage-sub").textContent = "Đã tắt."; setState("idle");
  }

  $("go").onclick = () => (on ? stop() : start());
  $("orb").onclick = () => (on ? null : start());
  const cmd = (o) => ctl && ctl.readyState === 1 && ctl.send(JSON.stringify(o));
  const ptt = $("ptt");
  ["pointerdown"].forEach((e) => ptt.addEventListener(e, (ev) => { ev.preventDefault(); ptt.classList.add("down"); cmd({ cmd: "ptt", down: true }); }));
  ["pointerup", "pointerleave", "pointercancel"].forEach((e) => ptt.addEventListener(e, () => { if (ptt.classList.contains("down")) { ptt.classList.remove("down"); cmd({ cmd: "ptt", down: false }); } }));
  $("barge").onclick = () => cmd({ cmd: "barge_in" });
  $("b-rag").onclick = () => cmd({ cmd: "set_rag", on: $("b-rag").dataset.on !== "1" });
  setInterval(() => { $("net").textContent = on && lastRx ? "tín hiệu từ Pi: " + Math.round(performance.now() - lastRx) + " ms trước" : ""; }, 1000);
  setState("idle"); connectCtl();
})();
