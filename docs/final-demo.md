# Final demo (fixed script)

Do not improvise extra faults, prompt tweaks, or live V3-1 recovery. Three scenes only.

**Board:** GearPro replay + `GEARPRO_RESEARCH_INJECT=1`, Control `:8787`, llama-server `:8080`, overlay `edgemedic-live`.

**Operator line (once, at start):**

> 小模型不可靠。系统靠 L0/L1、经验库、白名单 Control 和 Verify 把它关在边界里。V3-1 只是 shadow 观察，不是恢复权限。

Then run:

```bash
cd /home/jetson/Projects/edgemedic-live
/home/jetson/Projects/Machine_vision/.venv/bin/python3 tools/nx_final_demo.py
```

## Demo A — INSPECTION_PAUSED

Show: pause → inspection detects `INSPECTION_PAUSED` → `resume_inspection` → mission verify RECOVERED.

Say: 这不是唯一特例；下一条是另一类运行时故障。

## Demo B — CAMERA_STALE (replay pipeline)

Show: freeze file → `frame_age_ms` grows on normal telemetry → `restart_camera` → frames resume → verify.

Say: 这是 replay capture pipeline 的 stale，不是拔掉 `/dev/video*`。

## Demo C — memory ON vs OFF (CAMERA_STALE)

Uses the **frozen** RQ2 episode file. Does not farm new successes to inflate n.

Show: memory ON skips L2; memory OFF spends ~2.4 s in L2; both recovered in the recorded pair.

Say: 机制是“已知故障可绕过小模型”，不是“成功率显著提高”。

## Do not demo

Third live family, physical unplug, V3 driving recovery, RQ1 live execute, Health Graph, prompt A/B.
