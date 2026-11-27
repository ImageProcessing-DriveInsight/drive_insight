"""Initial, uncalibrated rules. Tune on labeled training clips, not test clips."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class Thresholds:
    dark: float = 60
    dim: float = 100
    bright: float = 190
    low_contrast: float = 35
    noise: float = 8
    high_noise: float = 18
    low_sharpness: float = 100

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in asdict(self).values()):
            raise ValueError('Thresholds must be finite and positive')
        if not self.dark < self.dim < self.bright or not self.noise < self.high_noise:
            raise ValueError('Threshold ranges must be ordered')

    def scaled(self, scale):
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError('scale must be finite and positive')
        return Thresholds(**{k: v * scale for k, v in asdict(self).items()})


def select_params(quality, *, thresholds=None):
    t = thresholds or Thresholds()
    q = {k: float(quality[k]) for k in ('brightness', 'contrast', 'noise', 'sharpness')}
    if any(not math.isfinite(v) or v < 0 for v in q.values()) or q['brightness'] > 255:
        raise ValueError('Invalid quality metrics')
    p = {'gamma': 1.0, 'hist_eq': False, 'denoise': 'none', 'ksize': 3,
         'unsharp': 0.0, 'rules': []}
    if q['brightness'] < t.dark:
        p['gamma'] = 0.5
        p['rules'].append('BR_DARK')
    elif q['brightness'] < t.dim:
        p['gamma'] = 0.75
        p['rules'].append('BR_DIM')
    elif q['brightness'] > t.bright:
        p['gamma'] = 1.3
        p['rules'].append('BR_BRIGHT')
    if q['contrast'] < t.low_contrast and q['noise'] < t.noise:
        p['hist_eq'] = True
        p['rules'].append('CT_LOW')
    if q['noise'] >= t.high_noise:
        p.update(denoise='median', ksize=5)
        p['rules'].append('NS_HIGH')
    elif q['noise'] >= t.noise:
        p.update(denoise='gaussian', ksize=3)
        p['rules'].append('NS_MEDIUM')
    if q['sharpness'] < t.low_sharpness and q['noise'] < t.noise:
        p['unsharp'] = 0.8
        p['rules'].append('SH_LOW')
    return p
