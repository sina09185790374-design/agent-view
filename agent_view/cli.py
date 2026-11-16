"""CLI for agent-view: describe / point / diff / check a screen JSON file."""

from __future__ import annotations

import argparse
import json
import sys

from .view import (
    AmbiguousError,
    NotFoundError,
    ViewError,
    check,
    describe,
    diff_views,
    load_screen,
    point,
)


def _dump(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="agent-view",
        description="Give an AI agent eyes: describe a screen as a compact "
                    "JSON tree, point at elements, diff two views, check quality.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("describe", help="compact JSON tree of a screen")
    p.add_argument("screen", help="screen JSON file")

    p = sub.add_parser("point", help="coordinates of one element")
    p.add_argument("screen", help="screen JSON file")
    p.add_argument("--text", help="substring of the element text/name")
    p.add_argument("--role", help="element role, e.g. button")
    p.add_argument("--name", help="substring of the accessible name")

    p = sub.add_parser("diff", help="what changed between two screens")
    p.add_argument("before", help="screen JSON file, before")
    p.add_argument("after", help="screen JSON file, after")

    p = sub.add_parser("check", help="quality gate for a screen")
    p.add_argument("screen", help="screen JSON file")

    args = parser.parse_args(argv)
    try:
        if args.command == "describe":
            _dump(describe(load_screen(args.screen)))
            return 0
        if args.command == "point":
            if not (args.text or args.role or args.name):
                parser.error("point needs --text, --role or --name")
            try:
                _dump(point(load_screen(args.screen),
                            text=args.text, role=args.role, name=args.name))
            except NotFoundError as exc:
                print(f"not found: {exc}", file=sys.stderr)
                return 2
            except AmbiguousError as exc:
                print(f"ambiguous: {exc}", file=sys.stderr)
                for m in exc.matches:
                    print(f"  {m['id']} {m.get('role','')} "
                          f"{m.get('text','')!r} {m['rect']}", file=sys.stderr)
                return 2
            return 0
        if args.command == "diff":
            result = diff_views(load_screen(args.before), load_screen(args.after))
            _dump(result)
            return 2 if result["changed"] else 0
        if args.command == "check":
            findings = check(load_screen(args.screen))
            _dump({"findings": findings, "clean": not findings})
            if findings:
                print(f"{len(findings)} finding(s)", file=sys.stderr)
                return 1
            print("clean", file=sys.stderr)
            return 0
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
