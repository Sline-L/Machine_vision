# Scratch V5 运行说明

Model2 是只判断齿轮 ROI 是否存在划痕的三模型融合包。业务界面继续使用“缺陷”和
“不合格”名称，但该版本不覆盖缺齿等其他缺陷。

## 判定流程

两个 384 输入分类器分别输出划痕概率并执行温度校准，YOLO26-P2 以 960 输入检测划痕，
取最高框置信度执行温度校准。最终计算：

```text
classifier_probability = (efficientnet_probability + resnet_probability) / 2
defect_score = 0.25 * classifier_probability + 0.75 * detector_probability
REJECT when defect_score >= 0.300273610279458
```

最高原始检测置信度达到 0.05 时显示一个辅助框。框仅供人工复核，最终结果始终由融合
概率决定。配置及三个权重位于 `model/model2/`；加载时会解析相对路径、校验 SHA256，并读取同目录 `manifest.json`（[Model Artifact Contract](model-bundle.md)）。validation 与 locked_test 必须分开记录。

## 数据集回放（Stage C）

不接摄像头时，可用同一套 locator + Scratch V5 从磁盘出 cycle：

```bash
python -m gp --replay /path/to/non_locked_frames
```

图像经 `ReplayCamera` 进入 `LatestFrame`，工人路径与实时相机相同。不要用锁定的 `test_scratch` 做 smoke 后再拿去调阈值。Dataset 仓不要 merge 进 Runtime 仓。

## 已知指标与边界

验证集 Recall 为 0.9767、FPR 为 0.0841，但验证集参与过模型和阈值选择。锁定的 150 张
独立测试集结果为 Recall 0.8065、Precision 0.5556、FPR 0.1681（TP/FP/TN/FN =
25/20/99/6），因此当前交付是可运行基线，不是生产最终模型。

训练环境为 PyTorch 2.14.0、torchvision 0.29.0、Ultralytics 8.4.142。当前开发环境使用
较低版本时，两张迁移基准图仍保持相同 PASS/REJECT，但概率存在约 `2.3e-5` 和
`4.1e-4` 的差异。Jetson NX 上线前必须重新记录三路概率、融合概率、延迟和显存；不得
根据锁定测试集重新选择阈值。
