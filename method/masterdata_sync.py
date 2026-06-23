# -*- coding: utf-8 -*-
"""
Masterdata source resolution / git fallback
===========================================
The generators read game masterdata JSON via generate_card_list.load_mst(). Normally
that data comes from a local A.RA.YA database checkout sitting next to this toolset
(../A.RA.YA/MasterdataBase). When that checkout is absent -- e.g. a collaborator who
only has this toolbox and not the database -- the needed files are pulled from the
A.RA.YA GitHub repo and cached under ./masterdata, so every page still builds offline
afterwards.

Resolution order for one masterdata file (see resolve()):
  1. ../A.RA.YA/MasterdataBase/<file>   -- the live local database, if present (preferred)
  2. ./masterdata/<file>                -- local git cache, if already downloaded
  3. download from GitHub raw -> ./masterdata/<file>, then use it

So the live database always wins when it's there (it is the source of truth and may be
newer than git); the git cache is only consulted/created when the database is missing.

Refreshing the cache: set MASTERDATA_REFRESH=1 in the environment, or call sync(force=True),
to re-download the cached files even when they already exist (to pick up upstream updates).

Source repo: https://github.com/LaTlcia/A.RA.YA/tree/main/MasterdataBase
Standard library only.
"""

import os as _os, sys as _sys
# --- make the project root (config.py) and this method/ folder importable,
#     no matter the cwd or whether this file is run directly or imported ---
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_ROOT = _os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import os
import json
import urllib.request
import urllib.error
import concurrent.futures

import config

# ---------------------------------------------------------------------------
# All source/location settings now live in config.py. The module-level names
# below are thin aliases kept for the rest of the toolset (e.g. generate_card_list
# reads masterdata_sync.PRIMARY_DIR) and so this file reads naturally.
# ---------------------------------------------------------------------------
RAW_BASE = config.MASTERDATA_RAW_BASE            # GitHub raw base the fallback pulls from
PRIMARY_DIR = config.MASTERDATA_DB_DIR           # live local A.RA.YA database (preferred)
CACHE_DIR = config.MASTERDATA_CACHE_DIR          # git fallback cache (./masterdata)

_UA = {"User-Agent": config.USER_AGENT}
_REFRESH_ENV = config.MASTERDATA_REFRESH_ENV

# Masterdata files this toolset reads (card list + tactics list + deck builder).
# Used by sync() to pre-fetch everything in parallel. resolve() does NOT depend on this
# list -- it downloads whatever filename a generator asks for on demand -- so the build
# still works even if a generator starts reading a file not listed here.
NEEDED_FILES = config.MASTERDATA_FILES


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _primary_path(filename):
    return os.path.join(PRIMARY_DIR, filename)


def _cache_path(filename):
    return os.path.join(CACHE_DIR, filename)


def _exists_ok(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def has_local_db():
    """True if the live A.RA.YA database checkout is present next to this toolset."""
    return os.path.isdir(PRIMARY_DIR)


def _refresh_requested():
    if config.MASTERDATA_FORCE_REFRESH:
        return True
    return os.environ.get(_REFRESH_ENV, "").strip().lower() not in ("", "0", "false", "no")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def _http_get(url, timeout=config.HTTP_TIMEOUT):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _valid_masterdata(data):
    """A real masterdata file parses as JSON and carries payload.mstList; this rejects
    HTML error pages / truncated downloads so they never poison the cache."""
    try:
        obj = json.loads(data.decode("utf-8"))
    except Exception:
        return False
    return isinstance(obj, dict) and isinstance(obj.get("payload", {}).get("mstList"), list)


def _download_one(filename, overwrite):
    dst = _cache_path(filename)
    if not overwrite and _exists_ok(dst):
        return "skip", filename
    try:
        data = _http_get(RAW_BASE + filename)
    except Exception as e:                              # noqa: BLE001
        return "fail", "%s : %s" % (filename, e)
    if not _valid_masterdata(data):
        return "fail", "%s : not valid masterdata JSON (got %d bytes)" % (filename, len(data))
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = dst + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dst)                                # atomic: cache only ever holds whole files
    return "ok", filename


def _download_many(filenames, overwrite, workers=config.DOWNLOAD_WORKERS):
    filenames = list(filenames)
    total = len(filenames)
    if not total:
        return 0, 0, 0
    ok = skip = fail = 0
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_download_one, f, overwrite) for f in filenames]
        for fu in concurrent.futures.as_completed(futs):
            status, info = fu.result()
            done += 1
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
                print("    ! failed:", info)
            print("    download %d/%d (ok %d / cached %d / failed %d)" % (done, total, ok, skip, fail))
    return ok, skip, fail


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def ensure_cached(filename):
    """Make sure <filename> exists in the git cache (download on first need / on refresh).
    Returns the cache path. Raises RuntimeError if it can't be made available."""
    dst = _cache_path(filename)
    overwrite = _refresh_requested()
    if _exists_ok(dst) and not overwrite:
        return dst
    status, info = _download_one(filename, overwrite=overwrite or not _exists_ok(dst))
    if status == "fail" and not _exists_ok(dst):
        raise RuntimeError(
            "Could not obtain masterdata file '%s'.\n"
            "  No local A.RA.YA database (%s) and the GitHub download failed:\n"
            "    %s\n"
            "  Provide the database, or get online so it can be pulled from\n"
            "    %s" % (filename, PRIMARY_DIR, info, RAW_BASE + filename))
    return dst


def resolve(filename):
    """Return a readable path for <filename>, preferring the live local DB, otherwise the
    git cache (downloading it on first need). This is what load_mst() calls."""
    p = _primary_path(filename)
    if _exists_ok(p):
        return p
    return ensure_cached(filename)


def sync(files=NEEDED_FILES, force=None):
    """Pre-populate the masterdata source so the build can run, downloading from GitHub
    only what's needed. Used by build_all (and runnable standalone). Returns (ok, skipped,
    failed) for the download step.

      * Live A.RA.YA database present -> use it; only fetch files the DB happens to be
        missing (normally none). Pass force=True / MASTERDATA_REFRESH=1 to refresh the
        git cache anyway.
      * No database -> ensure every needed file is cached (download missing; or re-download
        all when refreshing).
    """
    files = list(files)
    refresh = bool(force) or _refresh_requested()
    print("== masterdata sync ==")

    if has_local_db() and not refresh:
        missing = [f for f in files if not _exists_ok(_primary_path(f))]
        if not missing:
            print("  Live A.RA.YA database found: %s" % PRIMARY_DIR)
            print("  Using it directly (%d file(s), no download)." % len(files))
            return 0, len(files), 0
        print("  Live A.RA.YA database found, but %d needed file(s) are absent from it;" % len(missing))
        print("  fetching just those from GitHub into the cache (%s)..." % CACHE_DIR)
        ok, skip, fail = _download_many(missing, overwrite=False)
    else:
        if has_local_db() and refresh:
            print("  Refresh requested: re-downloading the git cache even though a local DB exists.")
        elif not has_local_db():
            print("  No local A.RA.YA database (%s)." % PRIMARY_DIR)
            print("  Pulling masterdata from GitHub into the cache (%s)..." % CACHE_DIR)
        ok, skip, fail = _download_many(files, overwrite=refresh)

    if fail:
        print("  Note: %d file(s) failed; re-run (online) to retry." % fail)
    else:
        print("  Masterdata ready (downloaded %d / cached %d)." % (ok, skip))
    return ok, skip, fail


# Run directly to pre-download / refresh the masterdata cache:
#   python masterdata_sync.py            (download anything missing)
#   MASTERDATA_REFRESH=1 python masterdata_sync.py   (force re-download)
if __name__ == "__main__":
    sync()
