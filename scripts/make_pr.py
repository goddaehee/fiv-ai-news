#!/usr/bin/env python3
"""Create a GitHub PR from local commit via API (no git CLI auth needed)."""
import base64
import json
import subprocess
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

OWNER = "goddaehee"
REPO = "fiv-ai-news"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"


def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{API}{path}", data=body, method=method,
                                 headers={"Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json"})
    add_surrogate_to_request(req, "custom.github", allowed_hosts=("api.github.com",))
    try:
        return read_json_response(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        print(f"{method} {path} -> {e.code}: {e.read().decode()[:400]}", file=sys.stderr)
        raise


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def main():
    branch = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else sh("git", "log", "-1", "--format=%s")
    base = "main"
    base_sha = api("GET", f"/git/ref/heads/{base}")["object"]["sha"]

    # Changed files vs base
    diff = sh("git", "diff", f"{base_sha}..HEAD", "--name-status")
    tree_items = []
    for line in diff.splitlines():
        parts = line.split("\t")
        status, path = parts[0], parts[-1]
        if status.startswith("D"):
            tree_items.append({"path": path, "sha": None})  # deletion marker
        else:
            content = open(path, "rb").read()
            b = api("POST", "/git/blobs", {
                "content": base64.b64encode(content).decode(), "encoding": "base64"})
            tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": b["sha"]})

    base_tree = api("GET", f"/git/commits/{base_sha}")["tree"]["sha"]
    # deletions: sha=None means delete in trees API
    tree_data = []
    for it in tree_items:
        if it.get("sha") is None and "mode" not in it:
            tree_data.append({"path": it["path"], "sha": None})
        else:
            tree_data.append(it)
    tree = api("POST", "/git/trees", {"base_tree": base_tree, "tree": tree_data})

    msg = sh("git", "log", "-1", "--format=%B")
    commit = api("POST", "/git/commits", {
        "message": msg, "tree": tree["sha"], "parents": [base_sha]})

    try:
        api("POST", "/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
    except urllib.error.HTTPError:
        api("PATCH", f"/git/refs/heads/{branch}", {"sha": commit["sha"], "force": True})

    pr = api("POST", "/pulls", {"title": title, "head": branch, "base": base,
        "body": "P0 출력 정리: validate 8종 게이트 + 템플릿 제거 + 단위 테스트 17개"})
    print(pr["html_url"])


main()
