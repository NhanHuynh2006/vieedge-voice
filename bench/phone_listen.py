import subprocess,sys,time,json
def sh(c): return subprocess.run(c,shell=True,capture_output=True,text=True).stdout
extra=sys.argv[2] if len(sys.argv)>2 else ""
secs=int(sys.argv[1])
sh("adb logcat -c; adb shell am force-stop vn.vieedge.voice; adb shell 'run-as vn.vieedge.voice rm -f files/segments.jsonl files/turns.jsonl'")
time.sleep(2)
sh(f"adb shell am start -n vn.vieedge.voice/.MainActivity --es model qwen3.5-2b-vi-voice-Q4_0.gguf --es device HTP0 --ez ack true --ez rag true --ei listen {secs} --es wavs x {extra}")
t=time.time()
while time.time()-t<secs+90:
    if "TEST done" in sh("adb logcat -d -s VieEdge:I"): break
    time.sleep(3)
seg=[json.loads(l) for l in sh("adb shell 'run-as vn.vieedge.voice cat files/segments.jsonl'").splitlines() if l.strip()]
turns=[json.loads(l) for l in sh("adb shell 'run-as vn.vieedge.voice cat files/turns.jsonl'").splitlines() if l.strip()]
print(f"{secs}s of room audio: {len(seg)} segments reached the recogniser, {len(turns)} turns answered")
for s in seg: print("  seg dur=%.1fs rms=%.4f ignored=%s text=%r"%(s['dur'],s['rms'],s['ignored'],s['text']))
