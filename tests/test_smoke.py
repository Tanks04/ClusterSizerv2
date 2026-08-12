"""Bare-minimum test that pytest can collect and import the package at all."""

from src.calculations.thresholds import Thresholds


def test_thresholds_construct():
    assert Thresholds() is not None
