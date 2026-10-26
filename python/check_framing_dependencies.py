"""Verify the packaged detector and import its pinned runtime, without editor access."""
import hashlib
import json
from pathlib import Path

def check():
    import cv2
    root = Path(__file__).resolve().parents[1] / 'assets/models/yunet'
    receipt = json.loads((root / 'source.json').read_text())
    model = root / 'yunet.onnx'
    if hashlib.sha256(model.read_bytes()).hexdigest() != receipt['sha256']:
        raise ValueError('Packaged framing model hash mismatch')
    cv2.FaceDetectorYN_create(str(model), '', (320, 320), .3, .3, 5000)
    return {'ready': True, 'opencv': cv2.__version__, 'modelSha256': receipt['sha256']}

if __name__ == '__main__':
    print(json.dumps(check()))
