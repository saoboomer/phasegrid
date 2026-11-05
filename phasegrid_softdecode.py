"""Soft-decision classifier for PhaseGrid's 26-dimensional codebook."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class SoftDecode:
    index: int
    distances: np.ndarray
    probabilities: np.ndarray
    confidence: float

def estimate_sigma_from_pilots(expected: np.ndarray, observed: np.ndarray) -> float:
    """Estimate scalar Gaussian noise after fitting global gain and offset."""
    x = np.asarray(expected, dtype=np.float64)
    y = np.asarray(observed, dtype=np.float64)
    if x.shape != y.shape or x.ndim != 2 or x.shape[0] < 2:
        raise ValueError("expected and observed need matching (n_pilots, features) arrays")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("pilot arrays must be finite")
    design = np.column_stack((x.reshape(-1), np.ones(x.size)))
    gain, offset = np.linalg.lstsq(design, y.reshape(-1), rcond=None)[0]
    if abs(gain) < 1e-12:
        raise ValueError("calibration gain is too close to zero")
    residual = y.reshape(-1) - (gain * x.reshape(-1) + offset)
    sigma = float(np.sqrt(np.mean(residual * residual)))
    if not np.isfinite(sigma) or sigma <= 1e-12:
        raise ValueError("estimated sigma is zero or invalid")
    return sigma

def soft_decode(observation: np.ndarray, codebook: np.ndarray, sigma: float,
                prior: np.ndarray | None = None) -> SoftDecode:
    """Return nearest codeword and Gaussian soft-decision probabilities."""
    y = np.asarray(observation, dtype=np.float64)
    c = np.asarray(codebook, dtype=np.float64)
    if c.ndim != 2 or y.ndim != 1 or c.shape[1] != y.size or c.shape[0] < 2:
        raise ValueError("codebook must be (n_symbols, n_features), observation 1-D")
    if not np.all(np.isfinite(c)) or not np.all(np.isfinite(y)):
        raise ValueError("codebook and observation must be finite")
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("sigma must be finite and positive")
    distances = np.linalg.norm(c - y[None, :], axis=1)
    logits = -0.5 * (distances / float(sigma)) ** 2
    if prior is not None:
        p = np.asarray(prior, dtype=np.float64)
        if p.shape != (c.shape[0],) or not np.all(np.isfinite(p)) or np.any(p < 0):
            raise ValueError("prior must be a finite nonnegative vector matching the codebook")
        total = float(p.sum())
        if total <= 0:
            raise ValueError("prior must have positive mass")
        with np.errstate(divide="ignore"):
            logits += np.log(p / total)
    weights = np.exp(logits - np.max(logits))
    probabilities = weights / weights.sum()
    index = int(np.argmax(probabilities))
    return SoftDecode(index, distances, probabilities, float(probabilities[index]))
