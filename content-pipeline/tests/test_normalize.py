from src.scoring.normalize import normalize


def test_spec_example_pair_matches():
    a = normalize("Nifty Hits All-Time High!")
    b = normalize("nifty hits all time highs")
    assert a == b
    assert a != ""


def test_idempotent():
    once = normalize("Virat Kohli's Century — INSANE stats!! 🔥🔥")
    assert normalize(once.replace("_", " ")) == once


def test_deterministic():
    assert normalize("Modi announces new scheme") == normalize("Modi announces new scheme")


def test_emoji_stripped():
    assert normalize("🔥🔥🔥") == ""
