# V3 两阶段缺陷识别结果

## 结论

V3 已完成无泄漏拆分、分类判定器、异常检测、独立/联合定位器、P2、CLAHE、灰度增强、hard-case 重采样和阈值搜索。总训练耗时约 3.28 小时，使用 RTX 4060、CUDA、AMP、RAM cache 和 4 个数据加载进程。

严格锁定测试集上的目标未达到，因此当前模型适合继续复核和辅助标注，不应直接按目标指标上线自动剔除。

| 指标 | 结果 | 目标 |
| --- | ---: | ---: |
| 划痕图像级 Recall | 0.364 | >= 0.90 |
| 缺齿图像级 Recall | 0.789 | >= 0.90 |
| 正常误剔除率 | 0.150 | <= 0.10 |
| 划痕框级 P / R | 0.000 / 0.000 | P >= 0.50, R >= 0.70 |
| 缺齿框级 P / R | 0.781 / 0.481 | P >= 0.50, R >= 0.70 |

缺齿在侧视测试子集的框级 Recall 为 0.722、Precision 为 0.867；主要短板是斜视缺齿和所有视角的划痕泛化。划痕的 P2、CLAHE、灰度增强均未稳定改善，说明瓶颈主要是有效独立样本和标注一致性，而不是继续增加 epoch。

## 数据完整性

- 343 张原始图按近重复组重新拆分为 train 243、val 50、test 50。
- 159 个近重复组，dHash 距离 <= 2 的跨集合泄漏为 0。
- 新测试集在模型选择和阈值搜索完成后只评估一次。
- 50 张训练/验证难例已写入 `review_queue.csv` 和 `review_queue/`，不包含 V3 测试图片。

## 交付文件

- `final/gate_yolo26n_cls.pt`：当前选中的三分类剔除判定器。
- `final/gate_resnet18.pt`：ResNet18 备选判定器。
- `final/anomaly_reference.pt`：正常样本特征距离参考。
- `final/scratch_localizer.pt`：划痕解释定位器。
- `final/missing_tooth_localizer.pt`：缺齿解释定位器。
- `inference_config.json`：阈值、权重、输入尺寸和融合配置。
- `final_report.json`：测试集完整指标和分视角结果。
- `leaderboard.csv`：所有快速候选及长训结果。

## 推理

```powershell
& "F:\Work\VSCode\Projects\DATASET\.venv\Scripts\python.exe" `
  "F:\Work\VSCode\Projects\DATASET\infer_defects_v3.py" `
  "图片或文件夹路径" `
  --output "F:\Work\VSCode\Projects\DATASET\outputs\defect_search_v3\predictions"
```

## 下一轮建议

1. 先复核 `review_queue/` 的 50 张难例，统一连续划痕区域与独立缺齿齿位的框法。
2. 新增真正独立的划痕齿轮与正常强反光样本，优先覆盖正视、侧视和低对比划痕；不要只抽取同一段视频的相邻帧。
3. 复核后重新生成 V4 拆分；保留本次 test 锁定结果作为历史记录，不再对其调阈值。
4. 缺齿可先作为人工复核辅助，划痕定位器当前不可作为生产判定依据。
