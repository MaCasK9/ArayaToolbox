# -*- coding: utf-8 -*-
import os
import json
import urllib.request
import urllib.error
import concurrent.futures

GITHUB_OWNER = "LaTlcia"
GITHUB_REPO = "A.RA.YA"
GITHUB_BRANCH = "main"
GITHUB_SUBDIR = "MasterdataBase"
RAW_BASE = "https://raw.githubusercontent.com/%s/%s/%s/%s/" % (
    GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, GITHUB_SUBDIR)

# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
PRIMARY_DIR = os.path.join(ROOT, "A.RA.YA", "MasterdataBase")
CACHE_DIR = os.path.join(SCRIPT_DIR, "masterdata")

_UA = {"User-Agent": "ArayaToolbox-MasterdataSync/1.0"}
_REFRESH_ENV = "MASTERDATA_REFRESH"


NEEDED_FILES = (
    "masterdata_api_mst_getCardMstList.json",
    "masterdata_api_mst_getLimitBreakBonusMstList.json",
    "masterdata_api_mst_getSkillMstList.json",
    "masterdata_api_mst_getLegendarySkillGroupMstList.json",
    "masterdata_api_mst_getUltimateCardMstList.json",
    "masterdata_api_mst_getCardSuperAwakeningCardTypeMstList.json",
    "masterdata_api_mst_getTacticsMstList.json",
    "masterdata_api_mst_getTacticsEffectMstList.json",
)


def _primary_path(filename):
    return os.path.join(PRIMARY_DIR, filename)


def _cache_path(filename):
    return os.path.join(CACHE_DIR, filename)


def _exists_ok(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def has_local_db():
    return os.path.isdir(PRIMARY_DIR)


def _refresh_requested():
    return os.environ.get(_REFRESH_ENV, "").strip().lower() not in ("", "0", "false", "no")


# ---------------------------------------------------------------------------
def _http_get(url, timeout=60):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _valid_masterdata(data):
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
    except Exception as e:
        return "fail", "%s : %s" % (filename, e)
    if not _valid_masterdata(data):
        return "fail", "%s : not valid masterdata JSON (got %d bytes)" % (filename, len(data))
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = dst + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dst)
    return "ok", filename


def _download_many(filenames, overwrite, workers=8):
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
def ensure_cached(filename):
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
    p = _primary_path(filename)
    if _exists_ok(p):
        return p
    return ensure_cached(filename)


def sync(files=NEEDED_FILES, force=None):
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


if __name__ == "__main__":
    sync()
