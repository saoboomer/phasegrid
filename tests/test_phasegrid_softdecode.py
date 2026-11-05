import numpy as np
import pytest
from phasegrid_softdecode import estimate_sigma_from_pilots, soft_decode

def test_soft_decode_selects_nearest_codeword():
    codebook = 3.0 * np.eye(4)
    observed = codebook[2] + np.array([0.01, -0.02, 0.03, 0.0])
    result = soft_decode(observed, codebook, sigma=0.1)
    assert result.index == 2
    assert result.confidence > 0.99
    assert result.probabilities.sum() == pytest.approx(1.0)

def test_uncertain_midpoint_has_low_confidence():
    codebook = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 4.0]])
    result = soft_decode(np.array([1.0, 0.0]), codebook, sigma=0.5)
    assert result.index in (0, 1)
    assert result.confidence < 0.51

def test_prior_affects_posterior():
    codebook = np.array([[0.0], [1.0]])
    observation = np.array([0.6])
    assert soft_decode(observation, codebook, 0.2).index == 1
    assert soft_decode(observation, codebook, 0.2, np.array([0.99, 0.01])).index == 0

def test_sigma_estimation_removes_gain_and_offset():
    rng = np.random.default_rng(7)
    expected = rng.normal(size=(80, 26))
    observed = 1.7 * expected + 0.4 + rng.normal(scale=0.03, size=expected.shape)
    assert estimate_sigma_from_pilots(expected, observed) == pytest.approx(0.03, abs=0.003)

def test_invalid_sigma_rejected():
    with pytest.raises(ValueError):
        soft_decode(np.array([0.0]), np.array([[0.0], [1.0]]), 0.0)
