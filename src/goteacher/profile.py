from __future__ import annotations

VALID_RANKS = [f"rank_{r}" for r in ["20k","19k","18k","17k","16k","15k","14k","13k","12k","11k","10k","9k","8k","7k","6k","5k","4k","3k","2k","1k","1d","2d","3d","4d","5d","6d","7d","8d","9d"]]
VALID_PREAZ = [f"preaz_{r}" for r in ["20k","19k","18k","17k","16k","15k","14k","13k","12k","11k","10k","9k","8k","7k","6k","5k","4k","3k","2k","1k","1d","2d","3d","4d","5d","6d","7d","8d","9d"]]
VALID_PROYEAR = [f"proyear_{y}" for y in range(1800, 2024)]
VALID_PREFIXES = ["rank_", "preaz_", "proyear_"]

SHORT_RANK_MAP: dict[str, str] = {}
for profile in VALID_RANKS:
    rank = profile.removeprefix("rank_")
    SHORT_RANK_MAP[rank] = profile
for profile in VALID_PREAZ:
    rank = profile.removeprefix("preaz_")
    SHORT_RANK_MAP[f"preaz_{rank}"] = profile
    SHORT_RANK_MAP[f"az_{rank}"] = profile


def normalize_profile(raw: str | None) -> str | None:
    if raw is None:
        return None
    raw = raw.strip().lower()
    if raw in VALID_RANKS or raw in VALID_PREAZ or raw.startswith("proyear_") or raw.startswith("rank_"):
        return raw
    mapped = SHORT_RANK_MAP.get(raw)
    if mapped:
        return mapped
    return raw


def validate_profile(raw: str | None) -> tuple[str | None, str | None]:
    profile = normalize_profile(raw)
    if profile is None:
        return None, None
    if profile in VALID_RANKS or profile in VALID_PREAZ:
        return profile, None
    if profile.startswith("proyear_"):
        try:
            year = int(profile.removeprefix("proyear_"))
            if 1800 <= year <= 2023:
                return profile, None
        except ValueError:
            pass
    if profile.startswith("rank_") and "_" in profile.removeprefix("rank_"):
        return profile, None
    examples = ", ".join(VALID_RANKS[:5] + ["..."] + VALID_PREAZ[:2] + ["proyear_1800"])
    return None, f"invalid profile '{raw}'. valid formats: {examples}"