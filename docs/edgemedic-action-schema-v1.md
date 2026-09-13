# Action Schema v1

人工按钮与 EdgeMedic 调用**同一套**动作。Executor 只接受白名单；Guardian 校验 level、precondition、retry、timeout；完成后跑 `verify`，失败则 rollback 或记 FAILURE。

禁止：任意 shell、`reboot`、改系统网络、改固件、删文件。OpenClaw 若暴露自然语言，也必须翻译成下列 `name`，不能直通 bash。

## 级别

| level | 含义 | 自动执行 |
| --- | --- | --- |
| 1 | 只读 | 是 |
| 2 | 可恢复 | 是，须 rollback/verify |
| 3 | 危险 | **否**（v1 不实现这些 name） |

## 白名单

| name | level | risk | 现状 | precondition（摘要） | timeout_s | retry | rollback | verify |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `get_state` | 1 | none | Control API `GET /api/state` | 无 | 1 | 0 | 无 | 返回合法 Snapshot |
| `restart_camera` | 2 | low | 已实现 | camera 打开失败或 STALE | 8 | 2 | 再 start 原 index | `frame_seq` 增加且 `frame_age_ms < 500` |
| `restart_worker` | 2 | low | 已实现 | worker 异常或连续 inspect 失败 | 30 | 1 | stop | worker running 且一次 inspect 无 exception |
| `reconnect_serial` | 2 | low | 已实现 | `consecutive_failures >= 1` 或未连接 | 3 | 3 | close | `send` 探针成功或端口可打开 |
| `set_inference_profile` | 2 | medium | `FULL`/`SPARSE`/`SAFE_STOP`/`TRT_FAST`（缺 engine 则拒绝） | 目标档位已实现；TRT_FAST 须 engine 文件存在 | 90 | 0 | 上一档位 | snapshot.profile 匹配；TRT_FAST 后 backend=engine |
| `set_locator_profile` | 2 | medium | 停 worker → 丢 inspector → 换权重 → warmup | `pt_safe` 或 `trt_fast` 且对应权重存在 | 90 | 0 | 原 locator 路径 | locator.backend 匹配且已加载（若当时在跑检测） |
| `pause_inspection` | 2 | low | 已实现 | inspection_active | 5 | 0 | `resume_inspection` | inspection_active=false |
| `resume_inspection` | 2 | low | 已实现 | 相机可用 | 30 | 0 | pause | inspection_active=true |
| `reload_config` | 2 | medium | 重读 `var/settings.json` 并必要时重建 inspector | JSON/模型路径合法 | 90 | 0 | `rollback_config` | validate_models 通过且档位匹配 |
| `rollback_config` | 2 | medium | 恢复内存快照，否则 `var/settings.last_known_good.json` | 存在快照或 last-known-good | 90 | 0 | 无 | 档位与 locator 回到快照 |
| `apply_settings` | 2 | medium | **仅 human**：校验并写入 UI 设置 | 字段合法 | 90 | 0 | 配置快照 | 设置已生效 |
| `use_camera` | 2 | low | **仅 human**：切回实时相机 | 无 | 30 | 0 | 无 | 退出视频模式 |
| `use_video` | 2 | low | **仅 human**：切到指定视频文件 | `params.path` | 30 | 0 | 无 | `video_mode` |
| `reset_stats` | 1 | none | **仅 human**：清空本次统计 | 无 | 5 | 0 | 无 | 统计清零 |

`set_locator_profile` 的 `pt_safe` = `model/model1.pt`；`trt_fast` = `.cache/exports/model1.engine`。不要做成改 YOLO 对象内部字段。Web 仪表盘的 start/stop/settings/camera/video/reset 走同一套 `ControlService`（`source=human`），不绕过 Guardian。

## 请求 / 响应

请求：

```json
{
  "name": "set_inference_profile",
  "params": { "profile": "SPARSE" },
  "source": "human",
  "request_id": "uuid"
}
```

`source` 由服务器绑定：HTTP 上最多是 `reflex`/`memory`/`reasoner`。客户端写 `"source":"human"` 不能升级权限。Guardian 不靠客户端标签放行 human-only 动作。

响应：

```json
{
  "request_id": "uuid",
  "accepted": true,
  "executed": true,
  "verified": true,
  "error": null,
  "snapshot_before": {},
  "snapshot_after": {},
  "duration_ms": 412
}
```

`accepted=false`：precondition 或未实现档位。`verify_level` 为 `none`/`config`/`function`/`mission`。`verified` 与 `recovery_success` 仅在 function/mission 为 true。仅 `config` 时不 rollback，但也 **不得**写入 Repair Memory 成功病例。

GearPro 默认在本机 `127.0.0.1:8787` 提供接口（可用 `--no-control` 或 `GEARPRO_CONTROL_PORT=0` 关闭）：

- `GET /api/state` → SystemSnapshot
- `POST /api/action` → 上面的请求/响应信封

JSON Schema：[edgemedic/action.schema.json](edgemedic/action.schema.json)。
