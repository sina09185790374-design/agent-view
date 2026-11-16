"""Agent view of a screen — the compact description an AI agent reads before it acts.

A screen is a JSON tree of nodes. Each node:

    {"tag": "button", "role": "button", "text": "Pay now",
     "x": 40, "y": 300, "w": 200, "h": 48, "children": [...]}

`describe` turns that tree into a short JSON list — id, tag, role, text and
rect per node — the way a person sees the screen: what is there, what it
says, and where it is. `point` finds one element and returns the coordinates
to click. `diff` compares two views the way a snapshot diff compares pixels.
`check` is the quality gate: unnamed controls, tiny tap targets, text that
overflows its parent, and controls that overlap each other.

Stdlib only. No network, no keys, no screenshots — the screen JSON is the
input, so any tool that can dump a layout (browser, app inspector, design
file) can feed this CLI.
"""

from __future__ import annotations

import json

INTERACTIVE_ROLES = {
    "button", "link", "textbox", "checkbox", "radio", "switch",
    "menuitem", "tab", "slider", "combobox",
}

MIN_TARGET = 24  # px — smallest side of a tappable control


class ViewError(Exception):
    """Bad screen input (missing file, bad JSON, bad shape)."""


class NotFoundError(Exception):
    """No element matches the point query."""


class AmbiguousError(Exception):
    """More than one element matches the point query."""

    def __init__(self, matches):
        super().__init__(f"{len(matches)} elements match")
        self.matches = matches


def load_screen(path):
    """Load and validate a screen JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            screen = json.load(fh)
    except FileNotFoundError:
        raise ViewError(f"no such file: {path}")
    except json.JSONDecodeError as exc:
        raise ViewError(f"{path} is not valid JSON: {exc}")
    if not isinstance(screen, dict) or "root" not in screen:
        raise ViewError(f"{path}: screen must be an object with a 'root' node")
    return screen


def _rect(node):
    return {
        "x": int(node.get("x", 0)),
        "y": int(node.get("y", 0)),
        "w": int(node.get("w", 0)),
        "h": int(node.get("h", 0)),
    }


def _is_empty(node):
    """A node with no size is not on the screen."""
    rect = _rect(node)
    return rect["w"] <= 0 or rect["h"] <= 0


def walk(node, path="root"):
    """Yield (path, node) in document order, skipping zero-size nodes."""
    if not isinstance(node, dict):
        return
    if _is_empty(node):
        return
    yield path, node
    for i, child in enumerate(node.get("children") or []):
        yield from walk(child, f"{path}/{i}")


def describe(screen):
    """Compact agent view: one short dict per visible node, stable ids."""
    nodes = []
    for n, (path, node) in enumerate(walk(screen["root"]), start=1):
        item = {
            "id": f"e{n}",
            "path": path,
            "tag": node.get("tag", ""),
            "role": node.get("role", ""),
            "rect": _rect(node),
        }
        label = node.get("text") or node.get("name") or ""
        if label:
            item["text"] = label
        children = node.get("children") or []
        if children:
            item["children"] = len(children)
        nodes.append(item)
    return nodes


def _matches(node, text=None, role=None, name=None):
    if role and node.get("role") != role:
        return False
    label = (node.get("text") or "") + "\n" + (node.get("name") or "")
    if text and text.lower() not in label.lower():
        return False
    if name and name.lower() not in label.lower():
        return False
    return True


def point(screen, text=None, role=None, name=None):
    """Find one element and return where to click it.

    Raises NotFoundError (0 matches) or AmbiguousError (>1 match) — never
    guesses between two candidates.
    """
    view = describe(screen)
    raw = {path: node for path, node in walk(screen["root"])}
    matches = [
        item for item in view
        if _matches(raw[item["path"]], text=text, role=role, name=name)
    ]
    if not matches:
        raise NotFoundError("no element matches")
    if len(matches) > 1:
        raise AmbiguousError(matches)
    item = dict(matches[0])
    rect = item["rect"]
    item["point"] = {"x": rect["x"] + rect["w"] // 2,
                     "y": rect["y"] + rect["h"] // 2}
    return item


def diff_views(before, after):
    """What changed between two screens, keyed by tree path."""
    b = {item["path"]: item for item in describe(before)}
    a = {item["path"]: item for item in describe(after)}
    out = {"added": [], "removed": [], "moved": [], "text_changed": []}
    for path, item in a.items():
        if path not in b:
            out["added"].append(item)
    for path, item in b.items():
        if path not in a:
            out["removed"].append(item)
        else:
            if item["rect"] != a[path]["rect"]:
                out["moved"].append({"path": path, "before": item["rect"],
                                     "after": a[path]["rect"]})
            if item.get("text", "") != a[path].get("text", ""):
                out["text_changed"].append(
                    {"path": path, "before": item.get("text", ""),
                     "after": a[path].get("text", "")})
    out["changed"] = bool(
        out["added"] or out["removed"] or out["moved"] or out["text_changed"])
    return out


def _intersects(r1, r2):
    x = max(0, min(r1["x"] + r1["w"], r2["x"] + r2["w"]) - max(r1["x"], r2["x"]))
    y = max(0, min(r1["y"] + r1["h"], r2["y"] + r2["h"]) - max(r1["y"], r2["y"]))
    return x * y


def check(screen):
    """Quality gate findings for a screen. Empty list = clean."""
    findings = []
    view = describe(screen)
    by_path = {item["path"]: item for item in view}
    raw = {path: node for path, node in walk(screen["root"])}

    for item in view:
        node = raw[item["path"]]
        role = node.get("role", "")
        label = (node.get("text") or node.get("name") or "").strip()
        rect = item["rect"]
        if role in INTERACTIVE_ROLES:
            if not label:
                findings.append({"rule": "unnamed-interactive",
                                 "id": item["id"], "path": item["path"],
                                 "detail": f"{role} with no text or name"})
            if rect["w"] < MIN_TARGET or rect["h"] < MIN_TARGET:
                findings.append({"rule": "tiny-target",
                                 "id": item["id"], "path": item["path"],
                                 "detail": f"{role} is {rect['w']}x{rect['h']}px, "
                                           f"smaller than {MIN_TARGET}px"})

    for path, node in walk(screen["root"]):
        parent = _rect(node)
        for i, child in enumerate(node.get("children") or []):
            if not isinstance(child, dict) or _is_empty(child):
                continue
            crect = _rect(child)
            if (crect["x"] < parent["x"] or crect["y"] < parent["y"]
                    or crect["x"] + crect["w"] > parent["x"] + parent["w"]
                    or crect["y"] + crect["h"] > parent["y"] + parent["h"]):
                findings.append({"rule": "overflow",
                                 "id": by_path.get(f"{path}/{i}", {}).get("id", "?"),
                                 "path": f"{path}/{i}",
                                 "detail": "child rect extends beyond its parent"})

    siblings = {}
    for item in view:
        parent = item["path"].rsplit("/", 1)[0]
        siblings.setdefault(parent, []).append(item)
    for group in siblings.values():
        interactive = [i for i in group
                       if raw[i["path"]].get("role") in INTERACTIVE_ROLES]
        for a in range(len(interactive)):
            for b in range(a + 1, len(interactive)):
                if _intersects(interactive[a]["rect"], interactive[b]["rect"]):
                    findings.append({"rule": "overlap",
                                     "id": interactive[a]["id"],
                                     "path": interactive[a]["path"],
                                     "detail": f"overlaps {interactive[b]['id']} "
                                               f"({interactive[b]['path']})"})
    return findings
