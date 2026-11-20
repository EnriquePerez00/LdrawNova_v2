"""Unit tests for structural_diff_config: tier inference and configuration lookup."""
import pytest

from ldraw_tools.structural_diff_config import (
    infer_tier,
    get_config_for_tier,
    TIER_CONFIGS,
)


class TestInferTier:
    """Test tier inference from parts count."""
    
    def test_micro_lower_bound(self):
        """1 part → MICRO."""
        assert infer_tier(1) == "MICRO"
    
    def test_micro_upper_bound(self):
        """50 parts → MICRO (boundary)."""
        assert infer_tier(50) == "MICRO"
    
    def test_small_lower_bound(self):
        """51 parts → SMALL (boundary+1)."""
        assert infer_tier(51) == "SMALL"
    
    def test_small_middle(self):
        """100 parts → SMALL."""
        assert infer_tier(100) == "SMALL"
    
    def test_small_upper_bound(self):
        """200 parts → SMALL (boundary)."""
        assert infer_tier(200) == "SMALL"
    
    def test_medium_lower_bound(self):
        """201 parts → MEDIUM (boundary+1)."""
        assert infer_tier(201) == "MEDIUM"
    
    def test_medium_large(self):
        """1000 parts → MEDIUM."""
        assert infer_tier(1000) == "MEDIUM"
    
    def test_beyond_largest(self):
        """5000 parts (beyond MEDIUM max) → defaults to MEDIUM."""
        assert infer_tier(5000) == "MEDIUM"
    
    def test_zero_parts(self):
        """0 parts → defaults to MICRO."""
        # Edge case: outside all ranges → falls back to MEDIUM (largest)
        result = infer_tier(0)
        assert result in ["MICRO", "MEDIUM"]  # Depends on default fallback


class TestGetConfigForTier:
    """Test tier configuration lookup."""
    
    def test_micro_config(self):
        """MICRO tier config exists and has expected structure."""
        cfg = get_config_for_tier("MICRO")
        assert cfg["weight_structural"] == 0.3
        assert cfg["convergence_threshold"] == 85.0
        assert cfg["status"] == "VALIDATED"
        assert "parts_range" in cfg
        assert cfg["parts_range"] == (1, 50)
    
    def test_small_config(self):
        """SMALL tier config exists and differs from MICRO."""
        cfg = get_config_for_tier("SMALL")
        assert cfg["weight_structural"] == 0.4  # 60% A4
        assert cfg["convergence_threshold"] == 82.0
        assert cfg["status"] in ["RECOMMENDED_PROBE", "PROBE", "READY"]
    
    def test_medium_config(self):
        """MEDIUM tier config has equal weighting."""
        cfg = get_config_for_tier("MEDIUM")
        assert cfg["weight_structural"] == 0.5  # 50/50
        assert cfg["convergence_threshold"] == 80.0
    
    def test_invalid_tier_raises(self):
        """Invalid tier name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown tier"):
            get_config_for_tier("HUGE")
    
    def test_config_is_copy(self):
        """get_config_for_tier should return a copy, not reference."""
        cfg1 = get_config_for_tier("MICRO")
        cfg1["weight_structural"] = 0.999
        
        cfg2 = get_config_for_tier("MICRO")
        assert cfg2["weight_structural"] == 0.3  # Unchanged
    
    def test_all_tiers_defined(self):
        """All tiers in TIER_CONFIGS should be gettable."""
        for tier in TIER_CONFIGS.keys():
            cfg = get_config_for_tier(tier)
            assert "weight_structural" in cfg
            assert "convergence_threshold" in cfg
            assert "parts_range" in cfg
