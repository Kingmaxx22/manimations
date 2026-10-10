"""Tests for free asset acquisition (Freesound SFX, Jamendo music).

No network: the HTTP layer is injected, so these pin the request the code builds
and the response it accepts, including the constraints that actually matter —
Jamendo's ``audiodownload_allowed`` gate and Freesound's licence filter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from manimations.pipeline import assets


# --------------------------------------------------------------------------
# request construction + response parsing (injected transport)
# --------------------------------------------------------------------------
class _Recorder:
    """Stands in for http_json: records the request, returns a canned response."""

    def __init__(self, response: dict):
        self.response = response
        self.url = None
        self.params = None

    def __call__(self, url, params, **kwargs):
        self.url = url
        self.params = params
        return self.response


class _Downloader:
    def __init__(self, payload: bytes = b"ID3fakeaudio"):
        self.payload = payload
        self.calls: list[tuple[str, Path]] = []

    def __call__(self, url, dst, **kwargs):
        self.calls.append((url, Path(dst)))
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(self.payload)
        return dst


FREESOUND_RESPONSE = {
    "count": 2,
    "results": [
        {
            "id": 111, "name": "Cinematic Whoosh Soft.wav",
            "username": "soundguy", "license": "Creative Commons 0",
            "duration": 1.4, "url": "https://freesound.org/s/111/",
            "previews": {"preview-hq-mp3": "https://cdn.freesound.org/prev/111_hq.mp3"},
        },
        {
            "id": 222, "name": "UI Click", "username": "ui", "license": "Attribution",
            "duration": 0.2, "url": "https://freesound.org/s/222/",
            "previews": {"preview-lq-mp3": "https://cdn.freesound.org/prev/222_lq.mp3"},
        },
        {"id": 333, "name": "No preview", "previews": {}},  # must be skipped
    ],
}

JAMENDO_RESPONSE = {
    "headers": {"status": "success"},
    "results": [
        {
            "id": "189201", "name": "Tech Future Beat", "artist_name": "SynthWave Beats",
            "duration": 120, "audiodownload_allowed": True,
            "audiodownload": "https://prod-1.storage.jamendo.com/download/track/189201/mp32/",
            "shareurl": "https://www.jamendo.com/track/189201",
            "license_ccurl": "http://creativecommons.org/licenses/by-nc-nd/3.0/",
        },
        {   # the critical case: downloads forbidden -> must never be returned
            "id": "999", "name": "All Rights Reserved", "artist_name": "Locked",
            "audiodownload_allowed": False,
            "audiodownload": "", "shareurl": "https://www.jamendo.com/track/999",
        },
        {   # allowed but empty url -> also unusable
            "id": "888", "name": "Empty URL", "audiodownload_allowed": True,
            "audiodownload": "",
        },
    ],
}


def test_freesound_search_uses_current_endpoint_and_cc0_filter():
    rec = _Recorder(FREESOUND_RESPONSE)
    client = assets.FreesoundClient("KEY", json_get=rec)
    client.search("whoosh", count=5)

    # /apiv2/search/ is current; /search/text/ was deprecated in Nov 2025
    assert rec.url == "https://freesound.org/apiv2/search/"
    assert "search/text" not in rec.url
    assert rec.params["token"] == "KEY"
    assert rec.params["query"] == "whoosh"
    assert 'license:"Creative Commons 0"' in rec.params["filter"]
    assert rec.params["page_size"] == 5


def test_freesound_search_parses_previews_and_skips_empty():
    rec = _Recorder(FREESOUND_RESPONSE)
    client = assets.FreesoundClient("KEY", json_get=rec)
    results = client.search("whoosh")
    assert len(results) == 2  # the preview-less entry is dropped
    assert results[0].id == "111"
    assert results[0].audio_url.endswith("111_hq.mp3")
    assert results[0].duration == pytest.approx(1.4)
    # falls back to the low-quality preview when hq is absent
    assert results[1].audio_url.endswith("222_lq.mp3")


def test_freesound_max_duration_becomes_a_filter():
    rec = _Recorder(FREESOUND_RESPONSE)
    assets.FreesoundClient("KEY", json_get=rec).search("click", max_duration=2)
    assert "duration:[0 TO 2]" in rec.params["filter"]


def test_freesound_any_license_drops_the_cc0_filter():
    rec = _Recorder(FREESOUND_RESPONSE)
    assets.FreesoundClient("KEY", json_get=rec).search("whoosh", license=None)
    assert "filter" not in rec.params


def test_freesound_rejects_unknown_license():
    client = assets.FreesoundClient("KEY", json_get=_Recorder({}))
    with pytest.raises(assets.AssetError, match="unknown Freesound licence"):
        client.search("x", license="WTFPL")


def test_freesound_without_key_is_unavailable():
    client = assets.FreesoundClient("", json_get=_Recorder({}))
    ok, detail = client.available()
    assert ok is False
    assert assets.FREESOUND_ENV in detail
    with pytest.raises(assets.AssetError):
        client.search("whoosh")


def test_jamendo_search_skips_tracks_that_forbid_download():
    """audiodownload_allowed=false must never yield a usable asset."""
    rec = _Recorder(JAMENDO_RESPONSE)
    client = assets.JamendoClient("CID", json_get=rec)
    results = client.search(tags="electronic upbeat", count=5)

    ids = [a.id for a in results]
    assert ids == ["189201"]
    assert "999" not in ids
    assert "888" not in ids


def test_jamendo_request_defaults_to_instrumental_and_download_format():
    rec = _Recorder(JAMENDO_RESPONSE)
    assets.JamendoClient("CID", json_get=rec).search(tags="lofi")
    assert rec.params["client_id"] == "CID"
    assert rec.params["format"] == "json"
    assert rec.params["vocalinstrumental"] == "instrumental"
    assert rec.params["audioformat"] == "mp32"
    assert rec.params["audiodlformat"] == "mp32"
    assert rec.params["tags"] == "lofi"
    # over-fetches because forbidden tracks are dropped
    assert rec.params["limit"] >= 3


def test_jamendo_duration_window():
    rec = _Recorder(JAMENDO_RESPONSE)
    assets.JamendoClient("CID", json_get=rec).search(
        tags="tech", min_duration=60, max_duration=180
    )
    assert rec.params["durationbetween"] == "60_180"


def test_jamendo_rejects_unknown_format():
    client = assets.JamendoClient("CID", json_get=_Recorder({}))
    with pytest.raises(assets.AssetError, match="unknown Jamendo audioformat"):
        client.search(tags="x", audioformat="wav")


def test_jamendo_surfaces_api_failure():
    rec = _Recorder({"headers": {"status": "failed",
                                 "error_message": "Invalid Client Id"}, "results": []})
    client = assets.JamendoClient("BAD", json_get=rec)
    with pytest.raises(assets.AssetError, match="Invalid Client Id"):
        client.search(tags="x")


def test_jamendo_retries_empty_but_successful_response():
    """The live API intermittently returns 0 rows with status=success.

    An identical query was observed returning 0 and 10 rows alternately, so an
    empty-but-successful body is retried rather than reported as "no results".
    """
    calls = {"n": 0}

    def flaky(url, params, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"headers": {"status": "success"}, "results": []}
        return JAMENDO_RESPONSE

    client = assets.JamendoClient("CID", json_get=flaky)
    results = client.search(tags="electronic", count=5, attempts=3)
    assert calls["n"] == 2
    assert [a.id for a in results] == ["189201"]


def test_jamendo_gives_up_after_attempts():
    calls = {"n": 0}

    def always_empty(url, params, **kwargs):
        calls["n"] += 1
        return {"headers": {"status": "success"}, "results": []}

    client = assets.JamendoClient("CID", json_get=always_empty)
    assert client.search(tags="x", attempts=2) == []
    assert calls["n"] == 2


def test_jamendo_without_client_id_is_unavailable():
    client = assets.JamendoClient("", json_get=_Recorder({}))
    ok, detail = client.available()
    assert ok is False
    assert assets.JAMENDO_ENV in detail


# --------------------------------------------------------------------------
# download + provenance
# --------------------------------------------------------------------------
def test_freesound_fetch_writes_file_with_usable_name(tmp_path):
    dl = _Downloader()
    client = assets.FreesoundClient("KEY", json_get=_Recorder(FREESOUND_RESPONSE),
                                    download=dl)
    asset = client.search("whoosh")[0]
    client.fetch(asset, tmp_path)
    assert asset.path is not None and asset.path.exists()
    assert asset.path.name == "cinematic_whoosh_soft.wav.mp3" or asset.path.suffix == ".mp3"
    assert asset.path.parent == tmp_path


def test_jamendo_fetch_names_file_after_artist(tmp_path):
    dl = _Downloader()
    client = assets.JamendoClient("CID", json_get=_Recorder(JAMENDO_RESPONSE),
                                  download=dl)
    asset = client.search(tags="electronic")[0]
    client.fetch(asset, tmp_path)
    assert asset.path is not None
    assert "synthwave_beats" in asset.path.name


def test_write_credits_records_licence_and_files(tmp_path):
    rec = _Recorder(JAMENDO_RESPONSE)
    client = assets.JamendoClient("CID", json_get=rec, download=_Downloader())
    asset = client.search(tags="electronic")[0]
    client.fetch(asset, tmp_path)

    path = assets.write_credits([asset], tmp_path / "credits.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["assets"][0]["author"] == "SynthWave Beats"
    assert "creativecommons.org" in payload["assets"][0]["license"]

    txt = path.with_suffix(".txt").read_text(encoding="utf-8")
    assert "Tech Future Beat" in txt
    assert "SynthWave Beats" in txt


def test_needs_attribution_flags_non_cc0():
    cc0 = assets.Asset("freesound", "1", "a", "x", "Creative Commons 0", "", "")
    by = assets.Asset("freesound", "2", "b", "y", "Attribution", "", "")
    nc = assets.Asset("jamendo", "3", "c", "z", "http://creativecommons.org/licenses/by-nc/3.0/", "", "")
    flagged = assets.needs_attribution([cc0, by, nc])
    assert [a.id for a in flagged] == ["2", "3"]


def test_cc0_recognised_as_url_not_just_display_name():
    """The API returns CC0 as a URL; that must not be read as 'credit owed'.

    Caught by a live Freesound call: three genuinely CC0 files were reported as
    requiring attribution because the licence came back as
    http://creativecommons.org/publicdomain/zero/1.0/.
    """
    url_form = assets.Asset(
        "freesound", "1", "whoosh", "DJT4NN3R",
        "http://creativecommons.org/publicdomain/zero/1.0/", "", "",
    )
    assert assets.is_cc0(url_form.license)
    assert assets.needs_attribution([url_form]) == []

    assert assets.is_cc0("Creative Commons 0")
    assert assets.is_cc0("CC0")
    assert not assets.is_cc0("http://creativecommons.org/licenses/by/3.0/")
    assert not assets.is_cc0("Attribution NonCommercial")


def test_asset_credit_line_is_readable():
    a = assets.Asset("jamendo", "1", "Tech Future Beat", "SynthWave Beats",
                     "Creative Commons BY-NC", "https://j/track/1", "https://a")
    credit = a.credit()
    assert "Tech Future Beat" in credit
    assert "SynthWave Beats" in credit
    assert "https://j/track/1" in credit


def test_set_project_music_edits_brief_in_place(project_dir):
    music = project_dir / "assets" / "bed.mp3"
    music.parent.mkdir(parents=True, exist_ok=True)
    music.write_bytes(b"x")

    assert assets.set_project_music(project_dir, music)
    text = (project_dir / "project.yaml").read_text(encoding="utf-8")
    assert "music:" in text
    # the brief stays loadable and the existing scenes survive
    from manimations.config import ProjectConfig

    proj = ProjectConfig.load(project_dir)
    assert proj.music is not None and "bed.mp3" in proj.music
    assert len(proj.scenes) == 2


def test_set_project_music_replaces_existing_key(project_dir):
    yaml_path = project_dir / "project.yaml"
    yaml_path.write_text("music: old.mp3\n" + yaml_path.read_text(encoding="utf-8"),
                         encoding="utf-8")
    new = project_dir / "new.mp3"
    new.write_bytes(b"x")
    assets.set_project_music(project_dir, new)
    text = yaml_path.read_text(encoding="utf-8")
    assert "old.mp3" not in text
    assert text.count("music:") == 1


def test_write_credits_merges_across_batches(tmp_path):
    """A second download must not erase the first batch's attribution.

    Regression: write_credits overwrote the file, so fetching whooshes and then
    key clacks left only the clacks credited.
    """
    first = [assets.Asset("freesound", "1", "Whoosh #1", "alice",
                          "http://creativecommons.org/publicdomain/zero/1.0/",
                          "https://freesound.org/s/1", "https://cdn/1.mp3")]
    second = [assets.Asset("freesound", "2", "wKey", "bob",
                           "http://creativecommons.org/publicdomain/zero/1.0/",
                           "https://freesound.org/s/2", "https://cdn/2.mp3")]

    path = tmp_path / "credits.json"
    assets.write_credits(first, path)
    assets.write_credits(second, path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    ids = sorted(a["id"] for a in payload["assets"])
    assert ids == ["1", "2"]
    txt = path.with_suffix(".txt").read_text(encoding="utf-8")
    assert "Whoosh #1" in txt and "wKey" in txt


def test_write_credits_merge_is_idempotent(tmp_path):
    """Re-recording the same asset must not duplicate it."""
    a = [assets.Asset("freesound", "1", "Whoosh", "alice", "Creative Commons 0", "", "")]
    path = tmp_path / "credits.json"
    assets.write_credits(a, path)
    assets.write_credits(a, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["count"] == 1


def test_write_credits_survives_a_corrupt_file(tmp_path):
    path = tmp_path / "credits.json"
    path.write_text("{not json", encoding="utf-8")
    a = [assets.Asset("freesound", "1", "W", "x", "Creative Commons 0", "", "")]
    assets.write_credits(a, path)  # must not raise
    assert json.loads(path.read_text(encoding="utf-8"))["count"] == 1
