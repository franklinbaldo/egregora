"""Tests for reader agent ELO rating calculations."""

import pytest

from egregora.agents.reader.elo import (
    DEFAULT_ELO,
    K_FACTOR,
    calculate_elo_update,
    calculate_expected_score,
)


class TestExpectedScore:
    """Test ELO expected score calculation."""

    def test_equal_ratings(self):
        """Equal ratings should give 0.5 expected score."""
        expected = calculate_expected_score(1500.0, 1500.0)
        assert abs(expected - 0.5) < 0.001

    def test_higher_rating_expected_to_win(self):
        """Higher rated player should have >0.5 expected score."""
        expected = calculate_expected_score(1600.0, 1500.0)
        assert expected > 0.5
        assert expected < 1.0

    def test_lower_rating_expected_to_lose(self):
        """Lower rated player should have <0.5 expected score."""
        expected = calculate_expected_score(1400.0, 1500.0)
        assert expected < 0.5
        assert expected > 0.0

    def test_symmetric(self):
        """Expected scores for A vs B and B vs A should sum to 1."""
        expected_a = calculate_expected_score(1600.0, 1400.0)
        expected_b = calculate_expected_score(1400.0, 1600.0)
        assert abs((expected_a + expected_b) - 1.0) < 0.001

    def test_400_point_difference(self):
        """400 point difference should give ~0.91 expected score."""
        expected = calculate_expected_score(1900.0, 1500.0)
        assert abs(expected - 0.909) < 0.001


class TestEloUpdate:
    """Test ELO rating updates."""

    def test_equal_ratings_winner_a(self):
        """When equal ratings, winner gains K/2 points."""
        new_a, new_b = calculate_elo_update(1500.0, 1500.0, "a")
        assert abs(new_a - 1516.0) < 0.1  # Gained K/2 = 16
        assert abs(new_b - 1484.0) < 0.1  # Lost K/2 = 16

    def test_equal_ratings_winner_b(self):
        """When equal ratings, winner gains K/2 points."""
        new_a, new_b = calculate_elo_update(1500.0, 1500.0, "b")
        assert abs(new_a - 1484.0) < 0.1  # Lost K/2 = 16
        assert abs(new_b - 1516.0) < 0.1  # Gained K/2 = 16

    def test_equal_ratings_tie(self):
        """Tie between equal ratings should not change them."""
        new_a, new_b = calculate_elo_update(1500.0, 1500.0, "tie")
        assert abs(new_a - 1500.0) < 0.1
        assert abs(new_b - 1500.0) < 0.1

    def test_upset_victory(self):
        """Lower rated player wins = big rating change."""
        # 1400 player beats 1600 player
        new_a, new_b = calculate_elo_update(1400.0, 1600.0, "a")
        # A should gain more than K/2
        assert new_a > 1400.0 + K_FACTOR / 2
        # B should lose more than K/2
        assert new_b < 1600.0 - K_FACTOR / 2

    def test_expected_victory(self):
        """Higher rated player wins = small rating change."""
        # 1600 player beats 1400 player
        new_a, new_b = calculate_elo_update(1600.0, 1400.0, "a")
        # A should gain less than K/2
        assert new_a < 1600.0 + K_FACTOR / 2
        assert new_a > 1600.0  # But still gains
        # B should lose less than K/2
        assert new_b > 1400.0 - K_FACTOR / 2
        assert new_b < 1400.0  # But still loses

    def test_rating_conservation(self):
        """Total rating points should be conserved."""
        initial_sum = 1600.0 + 1400.0
        new_a, new_b = calculate_elo_update(1600.0, 1400.0, "a")
        final_sum = new_a + new_b
        assert abs(initial_sum - final_sum) < 0.001

    def test_custom_k_factor(self):
        """Custom K factor should scale changes."""
        new_a_k16, new_b_k16 = calculate_elo_update(1500.0, 1500.0, "a", k_factor=16)
        new_a_k32, new_b_k32 = calculate_elo_update(1500.0, 1500.0, "a", k_factor=32)

        # K=32 should produce double the change of K=16
        change_k16 = new_a_k16 - 1500.0
        change_k32 = new_a_k32 - 1500.0
        assert abs(change_k32 - 2 * change_k16) < 0.001

    def test_tie_between_unequal_ratings(self):
        """Tie favors lower rated player slightly."""
        new_a, new_b = calculate_elo_update(1600.0, 1400.0, "tie")
        # Higher rated player should lose a bit
        assert new_a < 1600.0
        # Lower rated player should gain a bit
        assert new_b > 1400.0
        # But changes should be moderate (less than K/2)
        assert abs(new_a - 1600.0) < K_FACTOR / 2
        assert abs(new_b - 1400.0) < K_FACTOR / 2


class TestDefaultConstants:
    """Test default ELO constants."""

    def test_default_elo(self):
        """Default ELO should be 1500."""
        assert DEFAULT_ELO == 1500.0

    def test_k_factor(self):
        """Default K factor should be 32."""
        assert K_FACTOR == 32
