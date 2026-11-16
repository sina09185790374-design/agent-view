"""Tests for agent-view: describe, point, diff, check, and the CLI."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_view.view import (  # noqa: E402
    AmbiguousError,
    NotFoundError,
    check,
    describe,
    diff_views,
    load_screen,
    point,
)

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")


def screen_with(children, **root_extra):
    root = {"tag": "div", "role": "main", "x": 0, "y": 0,
            "w": 800, "h": 600, "children": children}
    root.update(root_extra)
    return {"name": "t", "width": 800, "height": 600, "root": root}


def node(tag="button", role="button", text="OK", x=10, y=10, w=100, h=40,
         children=None, **extra):
    n = {"tag": tag, "role": role, "x": x, "y": y, "w": w, "h": h}
    if text is not None:
        n["text"] = text
    if children is not None:
        n["children"] = children
    n.update(extra)
    return n


class TestDescribe(unittest.TestCase):
    def test_stable_ids_and_order(self):
        view = describe(screen_with([node(text="A"), node(text="B")]))
        self.assertEqual([v["id"] for v in view], ["e1", "e2", "e3"])
        self.assertEqual(view[1]["text"], "A")
        self.assertEqual(view[1]["rect"], {"x": 10, "y": 10, "w": 100, "h": 40})

    def test_zero_size_nodes_pruned(self):
        view = describe(screen_with(
            [node(text="seen"), node(text="hidden", w=0, h=40)]))
        self.assertEqual([v["text"] for v in view if "text" in v], ["seen"])

    def test_nested_children_counted(self):
        view = describe(screen_with(
            [node(text="Parent", children=[node(text="Child")])]))
        self.assertEqual(view[1]["children"], 1)
        self.assertEqual(view[2]["text"], "Child")

    def test_load_screen_rejects_bad_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as fh:
            fh.write("{not json")
            path = fh.name
        try:
            with self.assertRaises(Exception):
                load_screen(path)
        finally:
            os.unlink(path)


class TestPoint(unittest.TestCase):
    def test_center_coordinates(self):
        got = point(screen_with([node(text="Pay now", x=40, y=300, w=200, h=48)]),
                    text="pay now")
        self.assertEqual(got["point"], {"x": 140, "y": 324})
        self.assertEqual(got["text"], "Pay now")

    def test_role_filter(self):
        got = point(screen_with([node(text="Cart", role="link")]),
                    role="link")
        self.assertEqual(got["role"], "link")

    def test_not_found(self):
        with self.assertRaises(NotFoundError):
            point(screen_with([node(text="A")]), text="zzz")

    def test_ambiguous_never_guesses(self):
        with self.assertRaises(AmbiguousError) as ctx:
            point(screen_with([node(text="Save"), node(text="Save draft")]),
                  text="save")
        self.assertEqual(len(ctx.exception.matches), 2)


class TestDiff(unittest.TestCase):
    def test_text_change_and_added(self):
        before = screen_with([node(text="Pay now")])
        after = screen_with([node(text="Confirm payment"),
                             node(text="Help", x=500, y=10)])
        d = diff_views(before, after)
        self.assertTrue(d["changed"])
        self.assertEqual(len(d["added"]), 1)
        self.assertEqual(d["text_changed"][0]["before"], "Pay now")
        self.assertEqual(d["text_changed"][0]["after"], "Confirm payment")

    def test_moved_and_identical(self):
        a = screen_with([node(text="A", x=10, y=10)])
        self.assertFalse(diff_views(a, a)["changed"])
        b = screen_with([node(text="A", x=20, y=10)])
        d = diff_views(a, b)
        self.assertEqual(len(d["moved"]), 1)
        self.assertEqual(d["moved"][0]["before"]["x"], 10)
        self.assertEqual(d["moved"][0]["after"]["x"], 20)

    def test_removed(self):
        a = screen_with([node(text="A"), node(text="B")])
        b = screen_with([node(text="A")])
        self.assertEqual(len(diff_views(a, b)["removed"]), 1)


class TestCheck(unittest.TestCase):
    def test_clean_screen(self):
        self.assertEqual(check(screen_with([node(text="OK")])), [])

    def test_unnamed_interactive(self):
        findings = check(screen_with([node(text=None)]))
        self.assertTrue(any(f["rule"] == "unnamed-interactive"
                            for f in findings))

    def test_tiny_target(self):
        findings = check(screen_with([node(text="x", w=16, h=16)]))
        self.assertTrue(any(f["rule"] == "tiny-target" for f in findings))

    def test_overlap(self):
        findings = check(screen_with([
            node(text="A", x=10, y=10, w=100, h=40),
            node(text="B", x=50, y=20, w=100, h=40)]))
        self.assertTrue(any(f["rule"] == "overlap" for f in findings))

    def test_overflow(self):
        findings = check(screen_with(
            [node(text="Wide", x=750, y=10, w=100, h=40)]))
        self.assertTrue(any(f["rule"] == "overflow" for f in findings))


class TestCLI(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONPATH=os.path.join(
            os.path.dirname(__file__), ".."))
        return subprocess.run(
            [sys.executable, "-m", "agent_view", *args],
            capture_output=True, text=True, env=env,
            cwd=os.path.join(os.path.dirname(__file__), ".."))

    def test_describe_example(self):
        r = self.run_cli("describe",
                         os.path.join(EXAMPLES, "shop-checkout.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        view = json.loads(r.stdout)
        texts = [v.get("text", "") for v in view]
        self.assertIn("Pay now", texts)
        self.assertIn("Checkout", texts)

    def test_point_example(self):
        r = self.run_cli("point",
                         os.path.join(EXAMPLES, "shop-checkout.json"),
                         "--text", "Pay now")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout)
        self.assertEqual(got["point"], {"x": 140, "y": 324})

    def test_diff_examples(self):
        r = self.run_cli("diff",
                         os.path.join(EXAMPLES, "shop-checkout.json"),
                         os.path.join(EXAMPLES, "shop-checkout-v2.json"))
        self.assertEqual(r.returncode, 2, r.stderr)
        d = json.loads(r.stdout)
        self.assertTrue(d["changed"])
        self.assertEqual(len(d["added"]), 1)
        self.assertEqual(d["text_changed"][0]["after"], "Confirm payment")

    def test_check_v2_finds_problems(self):
        r = self.run_cli("check",
                         os.path.join(EXAMPLES, "shop-checkout-v2.json"))
        self.assertEqual(r.returncode, 1, r.stderr)
        out = json.loads(r.stdout)
        rules = {f["rule"] for f in out["findings"]}
        self.assertIn("unnamed-interactive", rules)
        self.assertIn("tiny-target", rules)

    def test_check_v1_clean(self):
        r = self.run_cli("check",
                         os.path.join(EXAMPLES, "shop-checkout.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)["clean"])


if __name__ == "__main__":
    unittest.main()
