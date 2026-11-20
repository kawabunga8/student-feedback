#!/usr/bin/env python3
"""Read-only export of a class team's Student Work file LISTING (metadata only) to a local JSON file.

    python3 sharepoint_listing.py --site https://<tenant>.sharepoint.com/sites/<team site>

Opens the team's SharePoint site in the app's automated Chrome profile (the same profile and lock as the Teams and
OneNote readers), makes read-only GET requests to the site's own list API from inside that signed-in page, and writes
`entries.json` for evidence_collect.py (--entries). Only names, sizes, dates and links are listed: no file is opened or
downloaded. Student and file names go into the local file only; stdout and logs show counts only.

Safety: only https *.sharepoint.com addresses are accepted; paging follows only links on the same host; nothing is
clicked, typed, created, renamed, moved, deleted or shared. Exit codes are teams_read.py's.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import teams_read as T

SHAREPOINT_HOST = re.compile(r"(^|\.)sharepoint\.com$", re.I)
LIBRARY = "Student Work"
SUBFOLDER = "Submitted files"
MAX_ITEMS = 20000
FIELDS = "FileSystemObjectType,FileRef,FileSizeDisplay,Modified"
OUT_DIR = T.APP_DATA / "evidence-listings"


# ---------------------------------------------------------------------------------------------------- pure functions
def check_site_url(url):
    """https, a sharepoint.com host, no credentials, path /sites/<name> (anything after is dropped). Returns (origin, '/sites/<name>')."""
    p = urllib.parse.urlsplit((url or "").strip())
    m = re.match(r"^/(sites|teams)/([A-Za-z0-9._~%-]+)", p.path or "")
    if p.scheme != "https" or p.username or p.password or not SHAREPOINT_HOST.search(p.hostname or "") or not m:
        raise T.ReadError("error", "That doesn't look like a class team site address (https://….sharepoint.com/sites/<team site>).")
    return f"https://{p.hostname}", f"/{m.group(1)}/{m.group(2)}"


def check_library(name):
    if not re.fullmatch(r"[A-Za-z0-9 _-]{1,60}", name or ""):
        raise T.ReadError("error", "The library name may only contain letters, numbers, spaces, dashes and underscores.")
    return name


def api_url(origin, site_path, library=LIBRARY):
    lib = check_library(library).replace("'", "''")
    return (f"{origin}{site_path}/_api/web/lists/getbytitle('{urllib.parse.quote(lib)}')/items"
            f"?$select={FIELDS}&$top=5000")


def to_entries(items, origin, site_path, library=LIBRARY, sub=SUBFOLDER):
    """List-API items -> evidence_collect entries (files under <library>/<sub>/ only; folders and other folders skipped).
    path is relative to <sub>: '<student>/<assignment>/[<subfolder>/]<file>'."""
    prefix = f"{site_path}/{library}/{sub}/".lower()
    out = []
    for it in items or []:
        if not isinstance(it, dict) or int(it.get("FileSystemObjectType") or 0) != 0:
            continue
        ref = str(it.get("FileRef") or "")
        if not ref.lower().startswith(prefix):
            continue
        rel = ref[len(prefix):].strip("/")
        if not rel or ".." in rel.split("/"):
            continue
        try:
            size = int(it.get("FileSizeDisplay") or it.get("File_x0020_Size") or 0)
        except (TypeError, ValueError):
            size = 0
        out.append({"path": rel, "bytes": size, "modified": str(it.get("Modified") or ""),
                    "url": origin + urllib.parse.quote(ref, safe="/"), "cloud_only": False})
        if len(out) >= MAX_ITEMS:
            break
    return out


def summary(entries):
    """Counts only."""
    depth, kinds = {}, {}
    import observe
    students = set()
    for e in entries:
        parts = e["path"].split("/")
        students.add(parts[0])
        depth[len(parts) - 1] = depth.get(len(parts) - 1, 0) + 1
        k = observe.classify(parts[-1]); kinds[k] = kinds.get(k, 0) + 1
    return {"files": len(entries), "student_folders_with_files": len(students), "files_by_depth_below_student": depth, "files_by_kind": kinds}


# ---------------------------------------------------------------------------------------------------- browser part
FETCH_JS = """async ([first, origin, cap]) => {
  let url = first, all = [];
  while (url && all.length < cap) {
    if (!url.startsWith(origin + '/')) return {error: 'paging left the site'};
    const r = await fetch(url, {headers: {Accept: 'application/json;odata=nometadata'}, credentials: 'include'});
    if (!r.ok) {
      let msg = '';
      try { const t = await r.json(); msg = (t.error && t.error.message && (t.error.message.value || t.error.message)) || (t['odata.error'] && t['odata.error'].message && t['odata.error'].message.value) || ''; } catch (e) {}
      let libs = [];
      try {
        const lr = await fetch(origin + new URL(first).pathname.split('/_api')[0] + "/_api/web/lists?$select=Title,BaseTemplate&$filter=BaseTemplate eq 101 and Hidden eq false", {headers: {Accept: 'application/json;odata=nometadata'}, credentials: 'include'});
        if (lr.ok) libs = ((await lr.json()).value || []).map(x => x.Title);
      } catch (e) {}
      return {error: 'status ' + r.status + (msg ? ': ' + String(msg).slice(0, 160) : '') + (libs.length ? ' | libraries on this site: ' + libs.join(', ') : '')};
    }
    const j = await r.json();
    all = all.concat(j.value || []);
    url = j['odata.nextLink'] || null;
  }
  return {items: all};
}"""


def listing(site_url, library=LIBRARY, wait=60, signin_wait=240):
    """Raw list-API items for the library, from inside the signed-in site page (read-only GETs)."""
    origin, site_path = check_site_url(site_url)
    first = api_url(origin, site_path, library)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise T.ReadError("setup", "Playwright isn't installed for this Python (see the setup lines in tools/spike_onenote_text.py).")
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    home = origin + site_path + "/"
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(home, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            if T._host(page.url) in T.LOGIN_HOSTS:
                end = time.time() + signin_wait
                while T._host(page.url) in T.LOGIN_HOSTS and time.time() < end:
                    page.wait_for_timeout(2000)
                if T._host(page.url) in T.LOGIN_HOSTS:
                    raise T.ReadError("sign_in", "Sign in to Microsoft in the Chrome window that opened, then run this again.")
                page.goto(home, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
            if not SHAREPOINT_HOST.search(T._host(page.url)) or T._host(page.url) != urllib.parse.urlsplit(origin).hostname:
                raise T.ReadError("differs", "The browser ended up on a different site than the team site; nothing was read.")
            r = page.evaluate(FETCH_JS, [first, origin, MAX_ITEMS])
            if not isinstance(r, dict) or r.get("error") or not isinstance(r.get("items"), list):
                raise T.ReadError("error", f"SharePoint did not return the library listing ({(r or {}).get('error', 'unexpected reply')}).")
            return r["items"]
        finally:
            ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True, help="the class team's SharePoint site address")
    ap.add_argument("--library", default=LIBRARY)
    ap.add_argument("--out", help=f"where to write entries.json (default: {OUT_DIR}/<site>.entries.json, outside git)")
    ap.add_argument("--signin-wait", type=int, default=240)
    a = ap.parse_args()
    try:
        origin, site_path = check_site_url(a.site)
        items = listing(a.site, a.library, signin_wait=a.signin_wait)
        entries = to_entries(items, origin, site_path, a.library)
        out = Path(a.out) if a.out else OUT_DIR / (site_path.strip("/").replace("/", "_") + ".entries.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
        os.replace(tmp, out)
        print(json.dumps({"ok": True, "written": str(out), **summary(entries)}, ensure_ascii=False))
        return T.EXIT["ok"]
    except T.ReadError as e:
        print(json.dumps({"ok": False, "kind": e.kind, "error": str(e)}))
        return T.EXIT.get(e.kind, 1)
    except Exception as e:
        print(json.dumps({"ok": False, "kind": "error", "error": f"{type(e).__name__}: {str(e)[:200]}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
