# agent-view

Give an AI agent eyes: a compact, pointable description of a screen, as a stdlib-only Python CLI. No screenshots, no network, no keys — any tool that can dump a layout (browser, app inspector, design file) feeds this CLI a screen JSON tree, and the agent gets back what is on the screen, what it says, and where it is.

**Pattern** (original code; pattern only, learned from today's radar): berkantay/gpucanvas puts thousands of live DOM nodes on a GPU canvas and gives the agent an *agent view* — what is on the canvas as a short JSON tree with ids, plus an image of any region, so the agent can read the UI and point at it. This tool is that idea as a small local CLI for any screen: the JSON tree is the view, `point` is the finger, `diff` is the snapshot comparison, and `check` is the quality gate.

## How it works

A screen is a JSON tree of nodes:

```json
{"name": "shop checkout", "width": 1280, "height": 800,
 "root": {"tag": "div", "role": "main", "x": 0, "y": 0, "w": 1280, "h": 800,
  "children": [
    {"tag": "button", "role": "button", "text": "Pay now",
     "x": 40, "y": 300, "w": 200, "h": 48}]}}
```

1. `describe` — the agent view: one short dict per visible node (`id`, `tag`, `role`, `text`, `rect`), stable ids in document order, zero-size nodes pruned.
2. `point` — find one element by `--text`, `--role` or `--name` and return its center coordinates. Zero matches → exit 2; more than one match → exit 2 with the candidates listed. It never guesses between two candidates.
3. `diff` — what changed between two screens: `added`, `removed`, `moved` (rect changed), `text_changed`. Exit 0 identical, exit 2 changed.
4. `check` — the quality gate: `unnamed-interactive` (a button/link/textbox with no text or name), `tiny-target` (interactive smaller than 24px), `overflow` (child rect outside its parent), `overlap` (two interactive siblings on top of each other). Exit 0 clean, exit 1 findings.

## Usage

```bash
python3 -m agent_view describe examples/shop-checkout.json
# [{"id": "e1", "path": "root", "tag": "div", "role": "main", ...},
#  {"id": "e6", "path": "root/1/0", "tag": "h2", "role": "heading",
#   "text": "Checkout", "rect": {"x": 40, "y": 96, "w": 200, "h": 40}},
#  {"id": "e9", "path": "root/1/3", "tag": "button", "role": "button",
#   "text": "Pay now", "rect": {"x": 40, "y": 300, "w": 200, "h": 48}}]

python3 -m agent_view point examples/shop-checkout.json --text "Pay now"
# {"id": "e9", ..., "point": {"x": 140, "y": 324}}

python3 -m agent_view diff examples/shop-checkout.json examples/shop-checkout-v2.json
# {"added": [...], "removed": [], "moved": [],
#  "text_changed": [{"path": "root/1/3", "before": "Pay now",
#                    "after": "Confirm payment"}], "changed": true}

python3 -m agent_view check examples/shop-checkout.json
# {"findings": [], "clean": true}
```

Exit codes: `0` ok / clean / identical · `1` bad input or check findings · `2` point not found or ambiguous, diff changed.

## Tests

```bash
python3 -m unittest discover -s tests
# 21 tests, all passing
```

---

# agent-view

به یک ایجنت هوش مصنوعی «چشم» بده: توصیف فشرده و قابل‌اشاره از یک صفحه، با یک CLI فقط-stdlib پایتون. بدون اسکرین‌شات، بدون شبکه، بدون کلید — هر ابزاری که بتواند چیدمان یک صفحه را خروجی بدهد (مرورگر، بازرس اپ، فایل طراحی)، یک درخت JSON به این CLI می‌دهد و ایجنت برمی‌گرداند که روی صفحه چه چیزی هست، چه می‌گوید و کجاست.

**الگو** (کد اصلی؛ فقط الگو، آموخته از رادار امروز): berkantay/gpucanvas هزاران نود زندهٔ DOM را روی یک بوم GPU می‌گذارد و به ایجنت یک *نمای ایجنت* می‌دهد — آنچه روی بوم هست به‌صورت یک درخت JSON کوتاه با شناسه، به‌علاوهٔ تصویر هر ناحیه — تا ایجنت بتواند رابط کاربری را بخواند و به آن اشاره کند. این ابزار همان ایده است به‌صورت یک CLI کوچک محلی برای هر صفحه: درخت JSON همان نماست، `point` انگشت اشاره است، `diff` مقایسهٔ اسنپ‌شات است و `check` دروازهٔ کیفیت.

## روش کار

یک صفحه یک درخت JSON از نودهاست (مثال بالا). چهار دستور:

1. `describe` — نمای ایجنت: یک دیکشنری کوتاه برای هر نود قابل‌مشاهده (`id`، `tag`، `role`، `text`، `rect`)، شناسه‌های پایدار به ترتیب سند، نودهای صفر‌اندازه حذف می‌شوند.
2. `point` — پیدا کردن یک عنصر با `--text` یا `--role` یا `--name` و برگرداندن مختصات مرکز آن. صفر تطابق → خروج ۲؛ بیش از یک تطابق → خروج ۲ با فهرست نامزدها. هرگز بین دو نامزد حدس نمی‌زند.
3. `diff` — چه چیزی بین دو صفحه تغییر کرده: `added`، `removed`، `moved` (تغییر مستطیل)، `text_changed`. خروج ۰ یعنی یکسان، خروج ۲ یعنی تغییر کرده.
4. `check` — دروازهٔ کیفیت: `unnamed-interactive` (دکمه/لینک/فیلد بدون متن یا نام)، `tiny-target` (عنصر تعاملی کوچک‌تر از ۲۴ پیکسل)، `overflow` (مستطیل فرزند بیرون از والد)، `overlap` (دو عنصر تعاملی هم‌خانواده روی هم). خروج ۰ یعنی تمیز، خروج ۱ یعنی یافته دارد.

## تست‌ها

```bash
python3 -m unittest discover -s tests
# ۲۱ تست، همه پاس
```
