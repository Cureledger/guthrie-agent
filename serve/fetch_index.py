#!/usr/bin/env python3
"""Download the retrieval index from this repo's `index-latest` release.

    INDEX_READ_TOKEN=...  python fetch_index.py /tmp/idx.tgz

The repo is private, so the plain release URL answers 404. A token that may
read this repo's contents can ask the release API for the asset instead. The
API answers with a redirect to a short-lived address on another host; the
token goes to the API only and is never sent on to that host.
"""
import json
import os
import shutil
import sys
import urllib.error
import urllib.request

REPO = "Cureledger/Guthrie"
TAG = "index-latest"
ASSET = "pku_index.tar.gz"
API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
AGENT = "guthrie-index-fetch"


class _StopAtRedirect(urllib.request.HTTPRedirectHandler):
    """urllib would repeat every header, the token included, to the next host."""

    def redirect_request(self, *args, **kwargs):
        return None


def _api(url: str, token: str, accept: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": AGENT,
    })


def main(out: str) -> None:
    token = os.environ.get("INDEX_READ_TOKEN", "").strip()
    if not token:
        sys.exit("INDEX_READ_TOKEN is not set. The build needs a token that may "
                 f"read the contents of {REPO}; see DEPLOY.md.")

    try:
        with urllib.request.urlopen(
                _api(f"{API}/repos/{REPO}/releases/tags/{TAG}", token,
                     "application/vnd.github+json"), timeout=60) as resp:
            release = json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"Could not read the {TAG} release of {REPO} (HTTP {e.code}). "
                 "401 or 404 means the token is missing, expired, or may not read this repo.")

    asset = next((a for a in release.get("assets", []) if a.get("name") == ASSET), None)
    if asset is None:
        sys.exit(f"The {TAG} release has no {ASSET}. Run the Build PKU index workflow once.")

    opener = urllib.request.build_opener(_StopAtRedirect)
    try:
        body = opener.open(_api(asset["url"], token, "application/octet-stream"), timeout=300)
    except urllib.error.HTTPError as e:
        location = e.headers.get("Location")
        if e.code not in (301, 302, 303, 307, 308) or not location:
            sys.exit(f"Could not download {ASSET} (HTTP {e.code}).")
        body = urllib.request.urlopen(
            urllib.request.Request(location, headers={"User-Agent": AGENT}), timeout=300)

    with body, open(out, "wb") as f:
        shutil.copyfileobj(body, f)
    print(f"downloaded {ASSET} ({os.path.getsize(out)} bytes) from {REPO} {TAG}")


if __name__ == "__main__":
    main(sys.argv[1])
