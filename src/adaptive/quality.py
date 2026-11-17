"""NumPy-only quality measurement; no OpenCV image operations."""
import numpy as np
from src.io.video import validate_frame


def convolve3(image, kernel):
    """3x3 convolution with reflect padding, vectorized over image pixels."""
    padded = np.pad(image, 1, mode='reflect')
    out = np.zeros_like(image, dtype=np.float64)
    h, w = image.shape
    for y in range(3):
        for x in range(3):
            out += kernel[2-y, 2-x] * padded[y:y+h, x:x+w]
    return out


def measure_quality(frame):
    validate_frame(frame)
    f = frame.astype(np.float64)
    y = 0.114*f[..., 0] + 0.587*f[..., 1] + 0.299*f[..., 2]
    lap = convolve3(y, np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]]))
    # Robust Laplacian-based estimate: MAD / Gaussian MAD / kernel L2 norm.
    # Interior only when available, avoiding reflected border artifacts.
    interior = lap[1:-1, 1:-1] if min(y.shape) >= 3 else lap
    mad = np.median(np.abs(interior - np.median(interior)))
    return {'brightness': float(y.mean()), 'contrast': float(y.std()),
            'noise': float(mad / (0.6744897501960817 * np.sqrt(20))),
            'sharpness': float(interior.var())}
