# SystemSnapshot v2

SystemSnapshot v2 将原来的单一 `scratch_v5` 节点扩展为 `specialists.scratch_v5` 和
`specialists.missing_hole_v1`，并增加整体 `inference` 健康状态。相机、定位、串口和
mission 字段延续 v1 语义。

新 API `/api/v2` 返回 v2 快照；兼容期内 `/api/v1` 继续返回 v1 形状。两个专项都是最终
判定的必要依赖，任一专项故障时 `inference.health` 为 0，检测 worker 停止且
`mission.output_valid` 为 false。

JSON 形状见 [edgemedic/system-snapshot-v2.schema.json](edgemedic/system-snapshot-v2.schema.json)
及 [示例](edgemedic/examples/system-snapshot-v2.json)。
