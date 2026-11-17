"""Ordered operation runner shared by fixed and adaptive enhancement.

Only apply_ops is implemented here; fixed_enhance/FIXED_PARAMS follow separately.
"""

from . import ops
from .color import validate_frame


# Integration defaults, not values calibrated on evaluation footage.
DEFAULT_KSIZE = 3
DEFAULT_GAUSSIAN_SIGMA = 1.0
DEFAULT_UNSHARP_SIGMA = 1.0
DEFAULT_UNSHARP_THRESHOLD = 5.0

_KNOWN_KEYS = frozenset({
    "denoise", "ksize", "sigma", "gamma", "hist_eq", "unsharp",
    "unsharp_sigma", "unsharp_threshold", "rules",
})


def _validated_params(params):
    """Validate even inactive options before starting any image processing."""
    if not isinstance(params, dict):
        raise ValueError("params must be a dict")
    unknown = params.keys() - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"unknown params keys: {', '.join(sorted(map(repr, unknown)))}")
    config = {
        "denoise": "none", "ksize": DEFAULT_KSIZE,
        "sigma": DEFAULT_GAUSSIAN_SIGMA, "gamma": 1.0, "hist_eq": False,
        "unsharp": 0.0, "unsharp_sigma": DEFAULT_UNSHARP_SIGMA,
        "unsharp_threshold": DEFAULT_UNSHARP_THRESHOLD,
    }
    # rules is metadata owned by B; its value is neither inspected nor modified.
    config.update({key: value for key, value in params.items() if key != "rules"})
    if not isinstance(config["denoise"], str) or config["denoise"] not in ("none", "gaussian", "median"):
        raise ValueError("denoise must be 'none', 'gaussian' or 'median'")
    allowed_sizes = (3, 5) if config["denoise"] == "median" else (3, 5, 7, 9)
    ops._validate_ksize(config["ksize"], allowed_sizes)
    ops._validate_real(config["sigma"], "sigma", strictly_positive=True)
    ops._validate_real(config["gamma"], "gamma")
    if not 0.3 <= config["gamma"] <= 3.0:
        raise ValueError("gamma must be in [0.3, 3.0]")
    if type(config["hist_eq"]) is not bool:
        raise ValueError("hist_eq must be a bool")
    ops._validate_real(config["unsharp"], "unsharp")
    ops._validate_real(config["unsharp_sigma"], "unsharp_sigma", strictly_positive=True)
    ops._validate_real(config["unsharp_threshold"], "unsharp_threshold")
    return config


def apply_ops(img, params):
    """Return uint8 BGR after denoise -> gamma -> hist_eq -> unsharp.

    Missing operation keys skip that operation; rules is ignored. Optional
    ksize/sigma/unsharp_sigma/unsharp_threshold configure operations, never enable
    them. See docs/dip_parameters.ko.md for defaults and validation decisions.
    Inputs and params are preserved, and even an identity returns a fresh array.
    """
    validate_frame(img)
    config = _validated_params(params)
    out = img.copy()
    if config["denoise"] == "gaussian":
        out = ops.gaussian(out, config["ksize"], config["sigma"])
    elif config["denoise"] == "median":
        out = ops.median(out, config["ksize"])
    if config["gamma"] != 1.0:
        out = ops.gamma(out, config["gamma"])
    if config["hist_eq"]:
        out = ops.hist_eq(out)
    if config["unsharp"] != 0.0:
        out = ops.unsharp(out, config["unsharp"], config["unsharp_sigma"], config["unsharp_threshold"])
    return out
