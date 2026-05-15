from __future__ import annotations

from goteacher.profile import normalize_profile, validate_profile


def test_normalize_short_rank():
    assert normalize_profile("1d") == "rank_1d"
    assert normalize_profile("5k") == "rank_5k"
    assert normalize_profile("20k") == "rank_20k"
    assert normalize_profile("9d") == "rank_9d"


def test_normalize_full_form():
    assert normalize_profile("rank_1d") == "rank_1d"
    assert normalize_profile("preaz_5k") == "preaz_5k"
    assert normalize_profile("proyear_2020") == "proyear_2020"


def test_normalize_az_prefix():
    assert normalize_profile("az_1d") == "preaz_1d"


def test_normalize_none():
    assert normalize_profile(None) is None


def test_validate_valid():
    profile, err = validate_profile("5k")
    assert profile == "rank_5k"
    assert err is None


def test_validate_invalid():
    profile, err = validate_profile("rank_abc")
    assert profile is None
    assert "invalid profile" in err


def test_validate_proyear():
    profile, err = validate_profile("proyear_2020")
    assert profile == "proyear_2020"
    assert err is None


def test_validate_proyear_out_of_range():
    profile, err = validate_profile("proyear_1799")
    assert profile is None
    assert "invalid profile" in err


def test_validate_none():
    profile, err = validate_profile(None)
    assert profile is None
    assert err is None
