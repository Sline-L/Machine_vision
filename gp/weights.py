"""Inspect GearPro classifier checkpoints without importing OpenCV."""


def classifier_family(checkpoint, state_dict):
    family = checkpoint.get("family") if isinstance(checkpoint, dict) else None
    if family:
        return str(family)
    if "fc.weight" in state_dict:
        return "resnet18"
    if "classifier.1.weight" in state_dict:
        return "efficientnet_b0"
    raise ValueError("无法识别分类器结构，checkpoint 缺少 family 且权重键不匹配")


def classifier_outputs(state_dict):
    if "fc.weight" in state_dict:
        return int(state_dict["fc.weight"].shape[0])
    if "classifier.1.weight" in state_dict:
        return int(state_dict["classifier.1.weight"].shape[0])
    raise ValueError("无法从分类器权重推断输出维度")
