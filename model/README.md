# Runtime weights

These files are tracked because the NX and PC need the same `.pt` baselines.

| File | Role |
| --- | --- |
| `model1.pt` | YOLO gear locator |
| `model2.pt` | Current EfficientNet-B0 classifier (`family=efficientnet_b0`, 384) |
| `model_old.pt` | Previous ResNet18 classifier (`family=resnet18`, 512), A/B only |

Do not commit TensorRT `.engine` files; they are board-specific build products.
See `docs/model-formats.md`.
