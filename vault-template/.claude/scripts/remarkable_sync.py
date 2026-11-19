#!/usr/bin/env python3
"""reMarkable -> vault sync (rules: CLAUDE.md "reMarkable handwritten notes").

Reads the reMarkable desktop app's sync cache read-only via remarkable-mcp's own exporter,
and writes merged PDFs into 01 Courses/<course>/Handwritten/. Never overwrites.

Usage (inside a venv with `remarkable-mcp` installed):
  python remarkable_sync.py --vault VAULT --cache CACHE            # dry run (report only)
  python remarkable_sync.py --vault VAULT --cache CACHE --apply    # export changed notebooks
Options: --prefix SEMESTER_PREFIX, --course "<course folder>", --tz Europe/Berlin
Mappings come from each Course.md `## reMarkable` block (see vault-template/CLAUDE.md).
"""
import argparse, asyncio, datetime as dt, os, re, sys
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = None  # set from --tz (default: system local time zone)
STALE_DAYS = 50
NB_RE = re.compile(r"^- notebook:\s*(\S.*?)\s+role:\s*(\S+)", re.M)
IGN_RE = re.compile(r"^- ignore:\s*(\S.*?)\s+reason:", re.M)
LOG_RE = re.compile(r"^- \d{4}-\d{2}-\d{2} \d{2}:\d{2}: (.+?) modified (\S+) → (.+)$", re.M)

def parse_course(md: Path):
    s = md.read_text(encoding="utf-8")
    m = re.search(r"^type:\s*(\S+)", s, re.M)
    ctype = m.group(1) if m else "unknown"
    sec = re.search(r"^## reMarkable\n(.*?)(?=^## |\Z)", s, re.M | re.S)
    nbs = [(p.strip(), r) for p, r in NB_RE.findall(sec.group(1))] if sec else []
    ign = [p.strip() for p in IGN_RE.findall(sec.group(1))] if sec else []
    return ctype, nbs, ign

def last_logged(log: Path):
    out = {}
    if log.exists():
        for path, ts, _ in LOG_RE.findall(log.read_text(encoding="utf-8")):
            out[path] = ts  # later lines win
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True); ap.add_argument("--cache", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--prefix", default=None, help="course folder prefix, e.g. WiSeYY_YY")
    ap.add_argument("--course", default=None, help="only this course (folder name, or part of it)")
    ap.add_argument("--tz", default=None, help="IANA time zone for file-name dates, e.g. Europe/Berlin")
    a = ap.parse_args()
    global TZ
    TZ = ZoneInfo(a.tz) if a.tz else dt.datetime.now().astimezone().tzinfo
    os.environ["REMARKABLE_LOCAL_DIR"] = a.cache
    os.environ["REMARKABLE_USE_LOCAL_DIR"] = "1"
    os.environ["REMARKABLE_DISABLE_CLOUD_FALLBACK"] = "1"
    import logging; logging.disable(logging.WARNING)
    from remarkable_mcp import tools
    from remarkable_mcp.api import get_rmapi, get_items_by_id, get_item_path
    from remarkable_mcp.export_resources import export_store

    client = get_rmapi(); col = client.get_meta_items(); ib = get_items_by_id(col)
    docs = {get_item_path(i, ib): i for i in col if not i.is_folder}
    now = dt.datetime.now(TZ)
    report = {"exported": [], "unchanged": [], "missing": [], "stale": [], "skipped_course": [],
              "errors": [], "unmapped_folders": []}
    mapped_parents = set(); ignored_folders = set()

    courses = sorted((Path(a.vault) / "01 Courses").glob(f"{a.prefix or ''}*/Course.md"))
    for md in courses:
        cdir = md.parent; ctype, nbs, ign = parse_course(md)
        ignored_folders.update(ign)
        if not nbs: continue
        mapped_parents.update(p.rsplit("/", 1)[0] for p, _ in nbs)
        if a.course and a.course.lower() not in cdir.name.lower(): continue
        if ctype in ("seminar", "lab"):
            report["skipped_course"].append(f"{cdir.name} (type {ctype}: ignored by rule)"); continue
        hw = cdir / "Handwritten"; log = hw / "sync-log.md"; logged = last_logged(log)
        for path, role in nbs:
            mapped_parents.add(path.rsplit("/", 1)[0])
            item = docs.get(path)
            if item is None:
                report["missing"].append(f"{cdir.name}: {path} not in cache"); continue
            mod = item.ModifiedClient.replace(tzinfo=dt.timezone.utc)
            ts = mod.strftime("%Y-%m-%dT%H:%M:%SZ")
            if (now - mod).days >= STALE_DAYS:
                report["stale"].append(f"{cdir.name}: {path} last modified {mod.astimezone(TZ):%Y-%m-%d} (may stop syncing without Connect)")
            if logged.get(path) == ts:
                report["unchanged"].append(f"{cdir.name}: {path} ({mod.astimezone(TZ):%Y-%m-%d %H:%M})"); continue
            name = path.rsplit("/", 1)[1]
            base = f"{name} - {mod.astimezone(TZ):%Y-%m-%d}"
            target = hw / f"{base}.pdf"; n = 2
            while target.exists():
                target = hw / f"{base} ({n}).pdf"; n += 1
            if not a.apply:
                report["exported"].append(f"[dry-run] {cdir.name}: {path} → Handwritten/{target.name}"); continue
            try:
                res = asyncio.run(tools.remarkable_export(path))
                link = [r for r in res if getattr(r, "type", "") == "resource_link"]
                if not link: raise RuntimeError(getattr(res[0], "text", str(res))[:300])
                info = res[0].text
                if '"status": "complete"' not in info:
                    report["errors"].append(f"{cdir.name}: {path} export not complete: {info[:300]}")
                data = export_store.read_bytes(str(link[0].uri).rsplit("/", 1)[1], "pdf")
                hw.mkdir(exist_ok=True)
                with open(target, "xb") as f: f.write(data)   # x = never overwrite
                if not log.exists():
                    log.write_text("# reMarkable sync log\nOne line per export. Written by the tutor; see CLAUDE.md.\n\n", encoding="utf-8")
                with open(log, "a", encoding="utf-8") as f:
                    f.write(f"- {now:%Y-%m-%d %H:%M}: {path} modified {ts} → {target.name}\n")
                report["exported"].append(f"{cdir.name}: {path} → Handwritten/{target.name} ({len(data)//1024} KB)")
            except Exception as e:
                report["errors"].append(f"{cdir.name}: {path}: {e}")

    # semester folders on the tablet with no mapping (names only; contents not opened)
    sem_roots = {p.rsplit("/", 1)[0] for p in mapped_parents}
    folders = {get_item_path(i, ib) for i in col if i.is_folder}
    for f in sorted(folders):
        parent = f.rsplit("/", 1)[0]
        if parent in sem_roots and f not in mapped_parents and f not in ignored_folders:
            report["unmapped_folders"].append(f)
    for k, v in report.items():
        print(f"## {k} ({len(v)})"); [print("-", x) for x in v]
    return 1 if report["errors"] else 0

if __name__ == "__main__":
    sys.exit(main())
