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
| `get_state` | 1 | none | 待做 Snapshot | 无 | 1 | 0 | 无 | 返回合法 Snapshot |
| `restart_camera` | 2 | low | 有 `CameraView.stop/start`，须从 Qt 拆出才能给 Agent 调 | camera 打开失败或 STALE | 8 | 2 | 再 start 原 index | `frame_seq` 增加且 `frame_age_ms < 500` |
| `restart_worker` | 2 | low | 有 start/stop inspection | worker 异常或连续 inspect 失败 | 30 | 1 | stop | worker running 且一次 inspect 无 exception |
| `reconnect_serial` | 2 | low | 有 `SerialOutput.reconfigure/close` | `consecutive_failures >= 1` 或未连接 | 3 | 3 | close | `send` 探针成功或端口可打开 |
| `set_inference_profile` | 2 | medium | **仅 `FULL`/`SPARSE`/`SAFE_STOP` 可先做**；其余见 Profile 文档 | 目标档位已实现；TRT_FAST 须 engine 文件存在 | 60 | 0 | 上一档位 | snapshot.profile 匹配；若非 SAFE_STOP 则一次成功 inspect |
| `set_locator_profile` | 2 | medium | 须重建 inspector | `pt_safe` 或 `trt_fast` 且对应权重存在 | 90 | 0 | 原 locator 路径 | locator.loaded 且 warmup 无异常 |
| `pause_inspection` | 2 | low | stop worker，相机可继续 | inspection_active | 5 | 0 | `resume_inspection` | inspection_active=false |
| `resume_inspection` | 2 | low | start worker | 相机可用 | 30 | 0 | pause | inspection_active=true |
| `reload_config` | 2 | medium | 部分设置已在 UI apply | JSON/模型路径合法 | 90 | 0 | `rollback_config` | validate_models 通过 |
| `rollback_config` | 2 | medium | 需保存上一份 AppConfig 快照 | 存在快照 | 90 | 0 | 无 | 配置哈希回到快照 |

`set_locator_profile` 的 `pt_safe` = `model/model1.pt`；`trt_fast` = `.cache/exports/model1.engine`。不要做成改 YOLO 对象内部字段。

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

`source` 为 `human` | `reflex` | `reasoner`。Guardian 不区分执行路径，只区分 level。

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

`accepted=false`：precondition 或未实现档位。`executed=true` 且 `verified=false`：必须 rollback 或标 FAILURE，**不得**写入 Repair Memory 成功病例。

JSON Schema：[edgemedic/action.schema.json](edgemedic/action.schema.json)。
