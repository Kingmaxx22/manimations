"""Free asset acquisition: sound effects (Freesound) and music (Jamendo).

Two key-based, free REST APIs are wrapped here so a workflow can pull SFX and a
background bed programmatically instead of hunting for files by hand:

* **Freesound** (``https://freesound.org/apiv2``) for sound effects.  Results are
  filtered to **CC0** by default, so the default path carries no attribution
  obligation.
* **Jamendo** (``https://api.jamendo.com/v3.0``) for full-length music beds.
  Jamendo has no CC0 catalogue, so every track is Creative Commons; the
  attribution is *recorded* rather than assumed away.

Keys are read from the environment (``FREESOUND_API_KEY``, ``JAMENDO_CLIENT_ID``)
and are never written to disk or echoed to the terminal.

Three documented constraints shape the implementation, and none of them are
optional if the output is to be usable:

* Freesound's key-only path serves **preview MP3s** (transcoded, ~128 kbps), not
  the original upload — the original needs OAuth2.  That is fine for UI clicks
  and transition whooshes, and is the only key-free option.
* Jamendo tracks may set ``audiodownload_allowed = false``; ``audiodownload`` is
  then an empty string and the track **must be skipped**.  The API docs are
  explicit that applications have to honour this, so tracks are filtered on it
  rather than silently falling back to the streaming URL.
* Freesound's ``/apiv2/search/text/`` endpoint was deprecated in November 2025 in
  favour of ``/apiv2/search/``.  The current endpoint is used.

Every download is appended to a credits file next to the audio, because "free to
use" is not the same as "no record needed".
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

#: Environment variables holding the credentials (never stored in the repo).
#: Several spellings are accepted because these names get typed by hand and the
#: provider portals do not agree on a convention.
FREESOUND_ENV = "FREESOUND_API_KEY"
JAMENDO_ENV = "JAMENDO_CLIENT_ID"
_FREESOUND_KEYS = ("FREESOUND_API_KEY", "FREESOUND_KEY", "FREESOUND_CLIENT_ID")
_JAMENDO_KEYS = ("JAMENDO_CLIENT_ID", "JAMENDO_CLIENTID", "JAMENDO_ID",
                 "JAMENDO_CLIENT_KEY")


def env_lookup(names: tuple[str, ...]) -> str:
    """First non-empty value among ``names``, matched case-insensitively.

    Falls back to a case-insensitive scan of the environment so a hand-written
    ``Jamendo_Clientid`` still works without renaming anyone's dotfile.
    """
    for n in names:
        v = os.environ.get(n)
        if v and v.strip():
            return v.strip()
    lowered = {k.lower(): v for k, v in os.environ.items()}
    for n in names:
        v = lowered.get(n.lower())
        if v and v.strip():
            return v.strip()
    return ""

#: The only three licence values Freesound's ``license`` field can take.  These
#: are what the *filter* accepts; the field itself comes back as a URL
#: (e.g. ``http://creativecommons.org/publicdomain/zero/1.0/``), so both forms
#: have to be recognised when deciding whether credit is owed.
FREESOUND_CC0 = "Creative Commons 0"
FREESOUND_LICENSES = (FREESOUND_CC0, "Attribution", "Attribution NonCommercial")

#: Markers that mean "this is CC0, no attribution required".
_CC0_MARKERS = (
    "creative commons 0",
    "publicdomain/zero",
    "cc0",
)


def is_cc0(license_text: str) -> bool:
    """Whether a licence string (display name *or* URL) is CC0 / public domain."""
    low = (license_text or "").lower()
    return any(m in low for m in _CC0_MARKERS)

#: Jamendo audio formats, by the name the API uses.
JAMENDO_FORMATS = ("mp31", "mp32", "ogg", "flac")
#: Audio format -> file extension for the downloaded file.
_EXT = {"mp31": ".mp3", "mp32": ".mp3", "ogg": ".ogg", "flac": ".flac"}

_USER_AGENT = "manimations/0.1 (+https://github.com/Kingmaxx22/manimations)"


class AssetError(RuntimeError):
    """Raised when an asset cannot be searched for or downloaded."""


@dataclass
class Asset:
    """One downloadable sound, with the provenance needed to credit it."""

    source: str          # "freesound" | "jamendo"
    id: str
    title: str
    author: str
    license: str
    page_url: str
    audio_url: str
    duration: float = 0.0
    path: Path | None = None
    extra: dict = field(default_factory=dict)

    def credit(self) -> str:
        """A one-line attribution suitable for a video description."""
        bits = [f'"{self.title}"']
        if self.author:
            bits.append(f"by {self.author}")
        bits.append(f"({self.license})")
        if self.page_url:
            bits.append(f"— {self.page_url}")
        return " ".join(bits)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["path"] = str(self.path) if self.path else None
        return d


# --------------------------------------------------------------------------
# HTTP helpers (stdlib only — the project has no requests dependency)
# --------------------------------------------------------------------------
def http_json(url: str, params: dict, *, timeout: int = 30,
              headers: dict | None = None) -> dict:
    """GET ``url`` with ``params`` and parse the JSON body."""
    query = urllib.parse.urlencode(params, doseq=True)
    full = f"{url}?{query}"
    req = urllib.request.Request(full, headers={"User-Agent": _USER_AGENT,
                                               **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:200]
        except Exception:  # pragma: no cover - best effort
            pass
        raise AssetError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise AssetError(f"could not reach {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise AssetError(f"{url} did not return JSON: {exc}") from exc


def http_download(url: str, dst: Path, *, timeout: int = 120) -> Path:
    """Stream ``url`` to ``dst``; returns the path on success."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    tmp = dst.with_suffix(dst.suffix + ".part")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as fh:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        raise AssetError(f"download failed for {url}: {exc}") from exc
    if not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise AssetError(f"download produced no data for {url}")
    tmp.replace(dst)
    return dst


def _slug(text: str, *, limit: int = 48) -> str:
    import re

    out = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return (out[:limit] or "asset").rstrip("_")


# --------------------------------------------------------------------------
# Freesound — sound effects
# --------------------------------------------------------------------------
class FreesoundClient:
    """Search and download sound effects from Freesound.

    Defaults to the CC0 licence filter, which is the whole point of using this
    API for automated workflows: the result needs no attribution.
    """

    #: Current search resource; ``/search/text/`` is deprecated (Nov 2025).
    BASE = "https://freesound.org/apiv2/search/"
    #: ``fields`` is strongly recommended by the docs so one request suffices.
    FIELDS = "id,name,previews,license,username,duration,url"

    def __init__(self, api_key: str | None = None, *, json_get=http_json,
                 download=http_download):
        self.api_key = (
            api_key if api_key is not None else env_lookup(_FREESOUND_KEYS)
        )
        self._json = json_get
        self._download = download

    def available(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, (
                f"no Freesound API key: set {FREESOUND_ENV} "
                f"(create one at https://freesound.org/apiv2/apply)"
            )
        return True, "freesound key present"

    def search(self, query: str, *, count: int = 5,
               license: str | None = FREESOUND_CC0,
               max_duration: float | None = None) -> list[Asset]:
        """Search Freesound; ``license=None`` disables the licence filter.

        Raising the licence filter above CC0 means the returned assets carry an
        attribution obligation — :func:`write_credits` records it either way.
        """
        ok, detail = self.available()
        if not ok:
            raise AssetError(detail)
        if license is not None and license not in FREESOUND_LICENSES:
            raise AssetError(
                f"unknown Freesound licence {license!r}; "
                f"expected one of {FREESOUND_LICENSES}"
            )

        filters: list[str] = []
        if license:
            filters.append(f'license:"{license}"')
        if max_duration is not None:
            filters.append(f"duration:[0 TO {float(max_duration):g}]")

        params: dict = {
            "query": query,
            "fields": self.FIELDS,
            "page_size": max(1, min(int(count), 150)),  # API maximum is 150
            "token": self.api_key,
        }
        if filters:
            params["filter"] = " ".join(filters)

        data = self._json(self.BASE, params)
        results = data.get("results", []) if isinstance(data, dict) else []
        assets: list[Asset] = []
        for r in results:
            previews = r.get("previews") or {}
            audio = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
            if not audio:
                continue
            assets.append(Asset(
                source="freesound",
                id=str(r.get("id", "")),
                title=str(r.get("name", "untitled")),
                author=str(r.get("username", "")),
                license=str(r.get("license", "")),
                page_url=str(r.get("url", "")),
                audio_url=str(audio),
                duration=float(r.get("duration", 0.0) or 0.0),
            ))
        return assets

    def fetch(self, asset: Asset, out_dir: Path) -> Asset:
        """Download ``asset`` into ``out_dir`` and record its local path."""
        ext = Path(urllib.parse.urlparse(asset.audio_url).path).suffix or ".mp3"
        name = f"{_slug(asset.title)}{ext}"
        asset.path = self._download(asset.audio_url, Path(out_dir) / name)
        return asset


# --------------------------------------------------------------------------
# Jamendo — background music
# --------------------------------------------------------------------------
class JamendoClient:
    """Search and download music beds from Jamendo.

    Jamendo's catalogue is Creative Commons rather than CC0, and a track may
    forbid downloads outright, so :meth:`search` only ever returns tracks whose
    ``audiodownload_allowed`` is true.
    """

    BASE = "https://api.jamendo.com/v3.0/tracks/"

    def __init__(self, client_id: str | None = None, *, json_get=http_json,
                 download=http_download):
        self.client_id = (
            client_id if client_id is not None else env_lookup(_JAMENDO_KEYS)
        )
        self._json = json_get
        self._download = download

    def available(self) -> tuple[bool, str]:
        if not self.client_id:
            return False, (
                f"no Jamendo client id: set {JAMENDO_ENV} "
                f"(create one at https://devportal.jamendo.com/)"
            )
        return True, "jamendo client id present"

    def search(self, *, tags: str | None = None, search: str | None = None,
               count: int = 3, instrumental: bool = True,
               audioformat: str = "mp32",
               max_duration: float | None = None,
               min_duration: float | None = None,
               attempts: int = 3) -> list[Asset]:
        """Search Jamendo for downloadable tracks.

        ``instrumental`` defaults to true: a music bed sits under narration, so
        vocals are usually unwanted.

        ``attempts`` guards against a real quirk of this API: the same query
        intermittently returns zero results while still reporting
        ``status: success`` (observed returning 0 and 10 rows alternately for an
        identical request).  An empty-but-successful response is therefore
        retried rather than reported as "no results".
        """
        ok, detail = self.available()
        if not ok:
            raise AssetError(detail)
        if audioformat not in JAMENDO_FORMATS:
            raise AssetError(
                f"unknown Jamendo audioformat {audioformat!r}; "
                f"expected one of {JAMENDO_FORMATS}"
            )

        # Over-fetch, because tracks that forbid download are dropped below.
        want = max(1, min(int(count), 200))  # API maximum is 200
        params: dict = {
            "client_id": self.client_id,
            "format": "json",
            "limit": min(200, want * 3),
            "include": "licenses",
            "audioformat": audioformat,
            "audiodlformat": audioformat,
        }
        if tags:
            params["tags"] = tags
        if search:
            params["search"] = search
        if instrumental:
            params["vocalinstrumental"] = "instrumental"
        if max_duration is not None or min_duration is not None:
            lo = int(min_duration) if min_duration is not None else 0
            hi = int(max_duration) if max_duration is not None else 3600
            params["durationbetween"] = f"{lo}_{hi}"

        results: list[dict] = []
        for attempt in range(max(1, attempts)):
            data = self._json(self.BASE, params)
            if isinstance(data, dict) and data.get("headers", {}).get("status") == "failed":
                raise AssetError(
                    "Jamendo rejected the request: "
                    f"{data['headers'].get('error_message', 'unknown error')}"
                )
            results = data.get("results", []) if isinstance(data, dict) else []
            if results:
                break
            if attempt + 1 < attempts:
                import time

                time.sleep(0.5 * (attempt + 1))

        assets: list[Asset] = []
        for r in results:
            # The API docs are explicit: honour this, do not fall back to the
            # streaming URL.
            if not r.get("audiodownload_allowed"):
                continue
            audio = r.get("audiodownload") or ""
            if not audio:
                continue
            assets.append(Asset(
                source="jamendo",
                id=str(r.get("id", "")),
                title=str(r.get("name", "untitled")),
                author=str(r.get("artist_name", "")),
                license=str(r.get("license_ccurl") or "Creative Commons"),
                page_url=str(r.get("shareurl", "")),
                audio_url=str(audio),
                duration=float(r.get("duration", 0.0) or 0.0),
            ))
            if len(assets) >= want:
                break
        return assets

    def fetch(self, asset: Asset, out_dir: Path) -> Asset:
        ext = Path(urllib.parse.urlparse(asset.audio_url).path).suffix or ".mp3"
        name = f"{_slug(asset.author)}_{_slug(asset.title)}{ext}".lstrip("_")
        asset.path = self._download(asset.audio_url, Path(out_dir) / name)
        return asset


# --------------------------------------------------------------------------
# provenance
# --------------------------------------------------------------------------
def write_credits(assets: list[Asset], path: Path) -> Path:
    """Write attribution for ``assets`` as JSON plus a human-readable list.

    CC0 assets need no credit, but recording everything is cheap and makes the
    licence status of a finished video auditable after the fact.  Each line is
    tagged so it is obvious what is *required* rather than merely recorded.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(assets),
        "needs_attribution": len(needs_attribution(assets)),
        "assets": [a.to_dict() for a in assets],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    required = [a for a in assets if not is_cc0(a.license)]
    lines = ["# Asset credits", ""]
    if required:
        lines.append(
            f"{len(required)} of {len(assets)} asset(s) REQUIRE attribution "
            f"(non-CC0). Include these lines in the video description:"
        )
        lines.append("")
    for a in assets:
        flag = "REQUIRED" if not is_cc0(a.license) else "no credit needed (CC0)"
        lines.append(f"- [{flag}] [{a.source}] {a.credit()}")
        if a.path:
            lines.append(f"  - file: {a.path.name}")
    txt = path.with_suffix(".txt")
    txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def needs_attribution(assets: list[Asset]) -> list[Asset]:
    """The subset of ``assets`` that is not CC0 and therefore must be credited.

    Handles both licence spellings: Freesound's filter uses the display name
    ``"Creative Commons 0"``, but the API returns a URL such as
    ``http://creativecommons.org/publicdomain/zero/1.0/``.  Treating the URL as
    non-CC0 would demand credit that is not owed.
    """
    return [a for a in assets if not is_cc0(a.license)]


def set_project_music(project_root: Path, music: Path) -> bool:
    """Point a project's ``music:`` brief entry at ``music``.

    A targeted line edit (like the duration fitting) so the hand-authored brief
    keeps its comments and ordering.  Adds the key when it is absent.
    """
    import re

    yaml_path = Path(project_root) / "project.yaml"
    if not yaml_path.exists():
        return False
    rel = music.as_posix()
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    replaced = False
    for line in lines:
        if re.match(r"^\s*music:\s*", line):
            out.append(f"music: {rel}\n")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        # insert after subtitle_lang / before the scenes block, or at the end
        inserted = False
        for i, line in enumerate(out):
            if re.match(r"^\s*scenes:\s*$", line):
                out.insert(i, f"music: {rel}\n")
                inserted = True
                break
        if not inserted:
            out.append(f"music: {rel}\n")
    yaml_path.write_text("".join(out), encoding="utf-8")
    return True
