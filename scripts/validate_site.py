"""Validate and assemble the public presentation site; never package original replays."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit, unquote


ROOT = Path(__file__).resolve().parents[1]
BLOCKED = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".csv", ".pkl", ".npy", ".npz", ".zip", ".xosc", ".xml", ".log"}
REMOVED_FIGURES = {"flow_anatomy", "flow_bottleneck"}
REMOVED_PREVIEWS = {
    "local-concerns-gpt.gif", "local-concerns-qwen7b.gif", "local-concerns-deepseek.gif",
    "everyday-hazards-gpt.gif", "cl-kc2-sim-ads.gif", "cl-kc2-behavior.gif",
    "wx-clear.gif", "wx-rain.gif", "wx-fog.gif", "wx-night.gif",
}
WEATHER_PREVIEWS = {
    "wx-bus-clear.webp", "wx-turnback-rain.webp", "wx-motorcycle-fog.webp",
    "wx-occludedped-night.webp",
}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()
        self.images = 0
        self.image_sources, self.resource_buttons = [], []
        self._resource = None
        self._publication_depth = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set(a.get("class", "").split())
        assert not {"clip", "missing"}.issubset(classes), "Missing clip placeholder in page"
        if tag == "div":
            if self._publication_depth:
                self._publication_depth += 1
            elif "publication-links" in classes:
                self._publication_depth = 1
        if self._publication_depth and tag in {"a", "button"}:
            assert self._resource is None, "Nested resource controls"
            self._resource = {"tag": tag, "attrs": a, "text": []}
        if "id" in a:
            assert a["id"] not in self.ids, f"Duplicate element ID: {a['id']}"
            self.ids.add(a["id"])
        for key in ("src", "href"):
            if a.get(key):
                self.links.append(a[key])
        if tag == "img":
            assert "alt" in a, "Image is missing alternative text"
            self.images += 1
            if a.get("src"):
                self.image_sources.append(a["src"])
        assert tag not in {"video", "source"}, "Only animated image previews may be published"
    def handle_data(self, data):
        if self._resource is not None:
            self._resource["text"].append(data)
    def handle_endtag(self, tag):
        if self._resource is not None and tag == self._resource["tag"]:
            self._resource["text"] = " ".join("".join(self._resource["text"]).split())
            self.resource_buttons.append(self._resource)
            self._resource = None
        if tag == "div" and self._publication_depth:
            self._publication_depth -= 1


def check_resource_buttons(buttons):
    assert len(buttons) == 5, "Expected five publication resource buttons"
    by_label = {re.sub(r"\W+", " ", b["text"].casefold()).strip(): b for b in buttons}
    expected = {"llm benchmark", "replays", "method comparison", "paper coming soon", "code coming soon"}
    assert set(by_label) == expected, "Publication resource button labels changed or are duplicated"
    for label, href in (("llm benchmark", "#benchmark"), ("replays", "#replays"),
                        ("method comparison", "#baseline")):
        b = by_label[label]
        assert b["tag"] == "a" and b["attrs"].get("href") == href, f"Incorrect resource link: {label}"
        assert "disabled" not in b["attrs"], f"Active resource link is disabled: {label}"
    for label in ("paper coming soon", "code coming soon"):
        b = by_label[label]
        assert b["tag"] == "button" and "disabled" in b["attrs"], f"Unavailable resource must be disabled: {label}"
        assert not b["attrs"].get("href"), f"Unavailable resource has a download link: {label}"
        accessible = b["attrs"].get("aria-label", "").casefold()
        assert "coming soon" in accessible and label.split()[0] in accessible, f"Unclear unavailable resource: {label}"


def check_public_file(path):
    assert path.suffix.lower() not in BLOCKED, f"Original replay/video in public tree: {path.name}"
    assert path.stem.casefold() not in REMOVED_FIGURES, f"Removed traffic figure remains public: {path.name}"
    assert path.name.casefold() not in REMOVED_PREVIEWS, f"Removed legacy preview remains public: {path.name}"


def check_native_preview(path):
    """Read the WebP container directly, keeping CI independent of image packages."""
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", f"Invalid preview: {path.name}"
    offset, canvas, frames = 12, None, 0
    while offset + 8 <= len(data):
        tag, size = data[offset:offset+4], int.from_bytes(data[offset+4:offset+8], "little")
        payload = data[offset+8:offset+8+size]
        if tag == b"VP8X":
            canvas = (1 + int.from_bytes(payload[4:7], "little"),
                      1 + int.from_bytes(payload[7:10], "little"))
        elif tag == b"ANMF":
            frames += 1
        offset += 8 + size + (size % 2)
    assert canvas == (1280, 720), f"Preview resolution changed: {path.name}: {canvas}"
    assert frames > 1, f"Replay is not animated: {path.name}"


def validate():
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "{{" not in page, "Unresolved build placeholder"
    for pattern in (r"sk-or-v1-", r"gh[pousr]_[A-Za-z0-9]", r"\bR0[0-9]\b", r"Request family kept", r"All 22 models", r"600 veh/h", r"tokens in /", r"HD video"):
        assert not re.search(pattern, page, re.I), f"Unwanted public content: {pattern}"
    p = Page()
    p.feed(page)
    check_resource_buttons(p.resource_buttons)
    for link in p.links:
        u = urlsplit(link)
        if u.scheme or u.netloc:
            continue
        if u.path:
            target = (ROOT / unquote(u.path)).resolve()
            assert target.is_relative_to(ROOT), f"Asset escapes site root: {link}"
            assert target.is_file(), f"Missing local asset: {link}"
        elif u.fragment:
            assert u.fragment in p.ids, f"Broken section link: {link}"
    weather = {Path(unquote(urlsplit(src).path)).name for src in p.image_sources
               if Path(unquote(urlsplit(src).path)).name.startswith("wx-")}
    assert weather == WEATHER_PREVIEWS, f"Expected four distinct weather previews; found: {sorted(weather)}"
    weather_files = [ROOT / "static" / "media" / name for name in sorted(WEATHER_PREVIEWS)]
    assert len({hashlib.sha256(f.read_bytes()).digest() for f in weather_files}) == 4, "Weather previews repeat the same asset"
    files = [ROOT / "index.html", *[f for f in (ROOT / "static").rglob("*") if f.is_file()]]
    for f in files:
        check_public_file(f)
        if f.parent == ROOT / "static" / "media" and f.suffix.lower() == ".webp":
            check_native_preview(f)
        if f.suffix.lower() in {".json", ".js", ".html", ".css"}:
            s = f.read_text(encoding="utf-8")
            assert not re.search(r"sk-or-v1-|gh[pousr]_[A-Za-z0-9]{20}", s), "Credential-like content in site"
    d = json.loads((ROOT / "static/data/review.json").read_text(encoding="utf-8"))
    assert "bundle" not in d, "Internal run metadata is not public content"
    assert set(d["maps"]) == {"Sai_Kung", "Tuen_Mun", "KOT"}, "Public map naming changed"
    assert sum(c["map"] == "KOT" for c in d["cases"]) == 49, "Kowloon Tong case count changed"
    assert all(c["corridor"].startswith("KOT-") for c in d["cases"] if c["map"] == "KOT"), "Kowloon Tong corridor naming changed"
    for c in d["cases"]:
        assert not {"ego_path", "partner_path", "trajectory", "trajectories", "source", "run"}.intersection(c), "Recorded paths in public case metadata"
    print(f"PASS: {p.images} images, {len(files)} public files; local links resolve; original replays/videos and credentials excluded.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-dir")
    args = ap.parse_args()
    validate()
    if args.build_dir:
        dest = (ROOT / args.build_dir).resolve()
        assert dest.is_relative_to(ROOT) and dest != ROOT, "Build must stay inside the site checkout"
        # This generated directory is reconstructed from validated sources.
        # A clean assembly prevents retired media from surviving an incremental copy.
        assert dest == ROOT / ".build", "Use the dedicated .build artifact directory"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("index.html", ".nojekyll", "MEDIA_NOTICE.md"):
            shutil.copy2(ROOT / name, dest / name)
        shutil.copytree(ROOT / "static", dest / "static", dirs_exist_ok=True)
        for f in dest.rglob("*"):
            if f.is_file():
                check_public_file(f)
        print("Public site assembled.")


if __name__ == "__main__":
    main()
