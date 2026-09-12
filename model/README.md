# Runtime weights

These files are tracked because the NX and PC need the same `.pt` baselines.

| File | Role |
| --- | --- |
| `model1.pt` | YOLO gear locator |
| `model2/inference_config.json` | Scratch V5 bundle configuration and relative weight paths |
| `model2/classifier_1.pt` | EfficientNet-B0 scratch classifier, 384 input |
| `model2/classifier_2.pt` | ResNet18 scratch classifier, 384 input |
| `model2/detector.pt` | YOLO26-P2 auxiliary scratch detector, 960 input |
| `model_old.pt` | Previous ResNet18 classifier (`family=resnet18`, 512), A/B only |

Do not commit TensorRT `.engine` files; they are board-specific build products.
See `docs/model-formats.md`.
