// VieEdge dashboard — vanilla JS, no CDN (works on the device's private hotspot).
(() => {
  const $ = (id) => document.getElementById(id);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  let ws, answer = "", sparkData = [];

  // Stages of the waterfall: [label, from, to, colour var]
  const STAGES = [
    ["Chờ endpoint (VAD)", "speech_end", "endpoint", "--s-wait"],
    ["STT xong", "speech_end", "stt_final", "--s-stt"],
    ["LLM token đầu (TTFT)", "llm_request", "llm_first_token", "--s-llm"],
    ["Câu đầu tiên", "llm_first_token", "first_chunk", "--s-llm"],
    ["TTS câu đầu", "first_chunk", "tts_first_done", "--s-tts"],
    ["Âm thanh đầu tiên", "speech_end", "first_audio", "--s-audio"],
    ["LLM xong", "llm_request", "llm_done", "--s-llm"],
    ["Đọc xong", "first_audio", "audio_done", "--s-tts"],
  ];

  function connect() {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ws.onmessage = (m) => handle(JSON.parse(m.data));
    ws.onclose = () => setTimeout(connect, 1500);
  }

  function setState(s) {
    const b = $("b-state");
    b.textContent = { idle: "Sẵn sàng", listening: "Đang nghe", thinking: "Đang nghĩ", speaking: "Đang nói", booting: "Khởi động" }[s] || s;
    b.className = "badge state " + s;
  }

  function handle(ev) {
    switch (ev.type) {
      case "hello":
        $("b-os").textContent = "OS: " + ev.os_cfg;
        $("b-stt").textContent = "STT: " + ev.stt;
        setState(ev.state);
        setRag(!!ev.rag);
        fillSelect(ev.stt_available, ev.stt);
        { const turns = (ev.history || []).filter((h) => h.type === "turn");
          turns.forEach(addHistory);
          if (turns.length) { const t = turns[turns.length - 1]; drawWaterfall(t);
            $("question").textContent = t.question || "—"; $("answer").textContent = t.answer || "—"; } }
        break;
      case "state": setState(ev.state); break;
      case "config": if (ev.stt) $("b-stt").textContent = "STT: " + ev.stt; if (ev.rag !== undefined) setRag(ev.rag); break;
      case "partial": $("partial").textContent = ev.text; break;
      case "final":
        $("question").textContent = ev.text || "(không nghe rõ)";
        $("partial").textContent = "—"; answer = ""; $("answer").textContent = "…";
        break;
      case "token": answer += ev.text; $("answer").textContent = answer; break;
      case "answer_done": $("answer").textContent = ev.text; break;
      case "turn": drawWaterfall(ev); addHistory(ev); break;
      case "sys": drawSys(ev); break;
      case "stress": { const b = $("stress"); b.classList.toggle("on", ev.on); b.textContent = "Tải nặng: " + (ev.on ? "bật" : "tắt"); break; }
    }
  }

  function setRag(on) { const b = $("rag"); b.classList.toggle("on", on); b.textContent = "Tra cứu: " + (on ? "bật" : "tắt"); }

  function fillSelect(list, cur) {
    const s = $("stt-select");
    s.innerHTML = "";
    const names = { ct2: "STT thuần CPU", hybrid: "STT NPU-nghe / CPU-giải mã" };
    (list || []).forEach((n) => { const o = document.createElement("option"); o.value = n; o.textContent = names[n] || n; o.selected = n === cur; s.appendChild(o); });
    s.onchange = () => ws.send(JSON.stringify({ cmd: "set_stt", backend: s.value }));
  }

  function fitCanvas(c) {
    const r = window.devicePixelRatio || 1, w = c.clientWidth, h = c.getAttribute("height");
    c.width = w * r; c.height = h * r; const g = c.getContext("2d"); g.setTransform(r, 0, 0, r, 0, 0); return [g, w, +h];
  }

  function drawWaterfall(turn) {
    const c = $("waterfall"), [g, W, H] = fitCanvas(c), t = turn.t_abs || {}, t0 = t.speech_end;
    g.clearRect(0, 0, W, H);
    if (t0 === undefined) return;
    const rows = STAGES.filter(([, a, b]) => t[a] !== undefined && t[b] !== undefined)
      .map(([l, a, b, col]) => [l, (t[a] - t0) * 1000, (t[b] - t0) * 1000, col]);
    const maxMs = Math.max(500, ...rows.map((r) => r[2]));
    const left = Math.min(150, W * 0.38), rowH = Math.min(24, (H - 24) / Math.max(rows.length, 1));
    g.font = "12px system-ui"; g.textBaseline = "middle";
    rows.forEach(([l, a, b, col], i) => {
      const y = 6 + i * rowH, x0 = left + (Math.max(a, 0) / maxMs) * (W - left - 50), x1 = left + (b / maxMs) * (W - left - 50);
      g.fillStyle = css("--muted"); g.fillText(l, 0, y + rowH / 2);
      g.fillStyle = css(col); g.fillRect(x0, y + 3, Math.max(2, x1 - x0), rowH - 6);
      g.fillStyle = css("--ink"); g.fillText(`${Math.round(b)} ms`, x1 + 4, y + rowH / 2);
    });
    g.strokeStyle = css("--line"); g.beginPath(); g.moveTo(left, H - 14); g.lineTo(W - 50, H - 14); g.stroke();
    g.fillStyle = css("--muted"); g.fillText("0 = người dùng ngừng nói", left, H - 5);
    const m = turn.metrics || {}, meta = turn.meta || {};
    $("turn-metrics").innerHTML = [
      ["Âm thanh đầu", m.first_audio_ms, "ms"], ["STT sau khi ngừng nói", m.stt_after_speech_ms, "ms"], ["TTFT", m.ttft_ms, "ms"],
      ["tokens/s", meta.llm_tok_s, ""], ["KV cache tái dùng", meta.llm_cached_n, "tok"], ["Speculative STT", meta.stt_speculative_hit ? "trúng" : "không", ""],
    ].filter((x) => x[1] !== undefined && x[1] !== null).map(([k, v, u]) => `<span>${k}: <b>${v}${u ? " " + u : ""}</b></span>`).join("");
  }

  function addHistory(turn) {
    const tb = document.querySelector("#history tbody"), tr = document.createElement("tr"), m = turn.metrics || {}, meta = turn.meta || {};
    tr.innerHTML = `<td class="num">${turn.turn_id}</td><td></td><td></td><td>${meta.stt || ""}</td><td class="num">${m.first_audio_ms ?? "–"} ms</td>`;
    tr.children[1].textContent = turn.question || ""; tr.children[2].textContent = turn.answer || "";
    tb.prepend(tr);
    while (tb.children.length > 30) tb.lastChild.remove();
  }

  function drawSys(s) {
    const cores = $("cores");
    if (cores.children.length !== (s.cpu_cores || []).length) {
      cores.innerHTML = (s.cpu_cores || []).map((_, i) => `<div class="core"><span>Lõi ${i}</span><div class="bar"><div class="fill ${i === 3 ? "iso" : ""}"></div></div><b>0%</b></div>`).join("");
    }
    (s.cpu_cores || []).forEach((v, i) => { const row = cores.children[i]; row.querySelector(".fill").style.width = v + "%"; row.querySelector("b").textContent = Math.round(v) + "%"; });
    const fq = s.freq_mhz || [];  // one value per core: show the range, the full list stays in the tooltip
    $("freq").textContent = fq.length ? (Math.min(...fq) === Math.max(...fq) ? `${fq[0]} MHz` : `${Math.min(...fq)}–${Math.max(...fq)} MHz`) : "–";
    $("freq").title = fq.join(" / ") + " MHz";
    $("load").textContent = (s.load1 ?? 0).toFixed(2);
    $("temp").textContent = s.temp_c != null ? s.temp_c + " °C" : "–";
    $("thr").textContent = s.throttled == null ? "–" : (s.throttled ? "0x" + s.throttled.toString(16) : "không");
    $("ram").textContent = `${s.ram_used_mb} / ${s.ram_total_mb} MB`;
    $("power").textContent = s.power_w != null ? `${s.power_w} W (${s.power_src})` : "–";
    $("npu").textContent = s.npu_calls != null
      ? `${s.enc_where === "npu" ? "" : "(ONNX/CPU) "}${s.npu_calls} lần, bận ${s.npu_busy_s}s` : "không dùng (STT thuần CPU)";
    $("npu-temp").textContent = s.npu_temp_c != null ? s.npu_temp_c.toFixed(1) + " °C" : "–";
    $("xrun").textContent = s.xruns ? `${s.xruns.capture} / ${s.xruns.playback}` : "–";
    if (s.os_cfg) $("b-os").textContent = "OS: " + s.os_cfg;
    sparkData.push(s.cpu_total || 0); if (sparkData.length > 120) sparkData.shift();
    const c = $("spark"), [g, W, H] = fitCanvas(c);
    g.clearRect(0, 0, W, H); g.strokeStyle = css("--accent"); g.lineWidth = 1.5; g.beginPath();
    sparkData.forEach((v, i) => { const x = (i / 119) * W, y = H - (v / 100) * (H - 4) - 2; i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.stroke(); g.fillStyle = css("--muted"); g.font = "11px system-ui"; g.fillText("CPU tổng (2 phút)", 4, 12);
  }

  // hold-to-talk (touch + mouse)
  const ptt = $("ptt");
  const down = (e) => { e.preventDefault(); ptt.classList.add("down"); ws && ws.send(JSON.stringify({ cmd: "ptt", down: true })); };
  const up = (e) => { e.preventDefault(); if (!ptt.classList.contains("down")) return; ptt.classList.remove("down"); ws && ws.send(JSON.stringify({ cmd: "ptt", down: false })); };
  ptt.addEventListener("pointerdown", down); ptt.addEventListener("pointerup", up); ptt.addEventListener("pointerleave", up);

  $("rag").onclick = () => ws && ws.send(JSON.stringify({ cmd: "set_rag", on: !$("rag").classList.contains("on") }));
  $("stress").onclick = () => ws && ws.send(JSON.stringify({ cmd: "stress", on: !$("stress").classList.contains("on") }));

  connect();
})();
