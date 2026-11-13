import json
import hashlib
import atexit
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

from studip_browser import BrowserResponse, BrowserSession

HERE = Path(__file__).resolve().parent
APP_DATA_DIR = Path(
    os.environ.get(
        "STUDIP_DATA_DIR",
        Path.home() / ".local" / "share" / "studip-mcp",
    )
).expanduser()

HOST = os.environ.get("STUDIP_BASE_URL", "https://studip.example.edu").rstrip("/")
BASE = f"{HOST}/jsonapi.php/v1"
CACHE_PATH = APP_DATA_DIR / "cache.json"
UPDATE_STATE_PATH = APP_DATA_DIR / "update_state.json"
PENDING_BASELINE_PATH = APP_DATA_DIR / "pending_baseline.json"
COURSE_CACHE_TTL = timedelta(hours=1)

SESSION_EXPIRED = (
    "Stud.IP is not signed in in the dedicated browser. Call open_studip_login, "
    "complete the sign-in yourself, then retry."
)

session = BrowserSession()
atexit.register(session.close)


# ---------------------------------------------------------------- helpers
def _vault_root() -> Path:
    value = os.environ.get("STUDIP_VAULT_DIR")
    if not value:
        raise RuntimeError("STUDIP_VAULT_DIR must point to the university vault")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"University vault directory does not exist: {root}")
    return root


def _staging_dir() -> Path:
    return _vault_root() / ".tmp" / "StudIP"


def _ensure_app_data_dir() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(APP_DATA_DIR, 0o700)


def _get(
    url: str,
    params: dict | None = None,
) -> BrowserResponse:
    is_absolute_url = url.startswith(("http://", "https://"))
    request_url = url if is_absolute_url else f"{BASE}/{url.lstrip('/')}"
    r = session.get(request_url, params=params, timeout=30)
    if r.status_code == 401:
        raise PermissionError(SESSION_EXPIRED)
    if r.status_code != 200:
        raise ValueError(f"Stud.IP returned {r.status_code} for {url}: {r.text[:200]}")
    return r


def _fetch_all(url: str, params: dict | None = None) -> list[dict]:
    """Fetch all pages of a JSON:API collection, following its next links."""
    items = []
    next_url = url
    next_params = params
    while next_url:
        request_url = (
            next_url
            if next_url.startswith(("http://", "https://"))
            else f"{BASE}/{next_url.lstrip('/')}"
        )
        body = _get(
            next_url,
            next_params,
        ).json()
        data = body.get("data", [])
        if not isinstance(data, list):
            raise ValueError(f"Expected a collection response from {next_url}")
        items.extend(data)

        next_link = body.get("links", {}).get("next")
        if not next_link:
            page = body.get("meta", {}).get("page", {})
            offset = page.get("offset")
            limit = page.get("limit")
            total = page.get("total")
            if (
                isinstance(offset, int)
                and isinstance(limit, int)
                and isinstance(total, int)
                and offset + limit < total
            ):
                next_url = url
                next_params = dict(params or {})
                next_params["page[offset]"] = offset + limit
            else:
                next_url = None
            continue

        next_url = urljoin(request_url, next_link)
        next_params = None
    return items


def _parse_date(value: str | None, parameter: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{parameter} must be an ISO 8601 date or datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _date_in_range(
    value: str | None,
    start: datetime | None,
    end: datetime | None,
    start_is_date: bool = False,
    end_is_date: bool = False,
) -> bool:
    if start is None and end is None:
        return True
    if value is None:
        return False
    parsed = _parse_date(value, "date")
    return (
        start is None
        or (parsed.date() >= start.date() if start_is_date else parsed >= start)
    ) and (
        end is None
        or (parsed.date() <= end.date() if end_is_date else parsed <= end)
    )


# ---------------------------------------------------------------- cache
def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def save_cache(cache: dict) -> None:
    _ensure_app_data_dir()
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


# ---------------------------------------------------------------- user & semester
def get_user_id() -> str:
    cache = load_cache()
    if "user_id" not in cache:
        cache["user_id"] = _get(f"{BASE}/users/me").json()["data"]["id"]
        save_cache(cache)
    return cache["user_id"]


def open_studip_login() -> dict:
    session.open_login()
    return {
        "opened": True,
        "message": "Sign in to Stud.IP in the opened Firefox window. Then call verify_studip_login.",
    }


def verify_studip_login() -> dict:
    try:
        _get("users/me")
    except PermissionError:
        return {
            "authenticated": False,
            "message": "Not signed in yet. Complete the interactive Stud.IP login and retry.",
        }
    return {
        "authenticated": True,
        "message": "Stud.IP browser session is valid. The MCP can use it without copying cookies.",
    }


def _fetch_current_semester() -> dict:
    r = _get(f"{BASE}/semesters", params={"page[limit]": 100}).json()["data"]
    for s in r:
        if s["attributes"]["is-current"]:
            return {
                "id": s["id"],
                "title": s["attributes"]["title"],
                "end": s["attributes"]["end"],
            }
    raise ValueError("No current semester found")


def get_current_semester() -> dict:
    cache = load_cache()
    sem = cache.get("semester")
    now = datetime.now(timezone.utc)

    if sem is None or datetime.fromisoformat(sem["end"]) < now:
        sem = _fetch_current_semester()
        cache["semester"] = sem
        save_cache(cache)

    return sem


# ---------------------------------------------------------------- courses
def _fetch_my_courses(semester_id: str) -> list[dict]:
    r = _fetch_all(
        f"users/{get_user_id()}/courses",
        {"filter[semester]": semester_id},
    )

    courses = []
    for c in r:
        rel = c["relationships"]
        if "end-semester" not in rel:
            continue
        if rel["start-semester"]["data"]["id"] != semester_id:
            continue
        courses.append({
            "title": c["attributes"]["title"],
            "id": c["id"],
        })
    return sorted(courses, key=lambda c: c["title"])

def get_my_courses(refresh: bool = False) -> list[dict]:
    sem = get_current_semester()          # refetches itself once the semester has ended
    now = datetime.now(timezone.utc)
    cached_at = sem.get("courses_cached_at")
    courses_are_fresh = False
    if cached_at is not None:
        cached_at_dt = datetime.fromisoformat(cached_at)
        if cached_at_dt.tzinfo is None:
            cached_at_dt = cached_at_dt.replace(tzinfo=timezone.utc)
        age = now - cached_at_dt
        courses_are_fresh = timedelta(0) <= age < COURSE_CACHE_TTL

    if refresh or "courses" not in sem or not courses_are_fresh:
        sem["courses"] = _fetch_my_courses(sem["id"])
        sem["courses_cached_at"] = now.isoformat()
        cache = load_cache()
        cache["semester"] = sem
        save_cache(cache)
    return sem["courses"]


# ---------------------------------------------------------------- folders & files
def _folder_index(course_id: str) -> dict[str, dict]:
    resources = _fetch_all(f"courses/{course_id}/folders", {"page[limit]": 100})
    return {
        folder["id"]: {
            "id": folder["id"],
            "name": folder["attributes"]["name"],
            "parent_id": folder.get("relationships", {}).get("parent", {}).get("data", {}).get("id"),
            "file_count": folder.get("relationships", {}).get("file-refs", {}).get("meta", {}).get("count", 0),
        }
        for folder in resources
    }


def _folder_path(folder_id: str, folders: dict[str, dict]) -> str:
    parts = []
    seen = set()
    current_id = folder_id
    while current_id in folders and current_id not in seen:
        seen.add(current_id)
        folder = folders[current_id]
        if folder["parent_id"] is not None:
            parts.append(folder["name"])
        current_id = folder["parent_id"]
    return str(Path(*reversed(parts)))


def get_folders(course_id: str) -> list[dict]:
    folders = _folder_index(course_id)

    return [
        {
            **folder,
            "path": _folder_path(folder["id"], folders),
        }
        for folder in folders.values()
        if folder["file_count"] > 0
    ]


def get_files(folder_id: str) -> list[dict]:
    r = _fetch_all(f"folders/{folder_id}/file-refs", {"page[limit]": 100})

    return [
        {
            "id": f["id"],
            "name": f["attributes"]["name"],
            "description": f["attributes"].get("description"),
            "size": f["attributes"]["filesize"],
            "mime_type": f["attributes"]["mime-type"],
            "is_downloadable": f["attributes"]["is-downloadable"],
            "download_url": HOST + f["meta"]["download-url"],
        }
        for f in r
    ]


def get_course_files(course_id: str) -> list[dict]:
    folders = _folder_index(course_id)
    files = []
    for folder in folders.values():
        if folder["file_count"] == 0:
            continue
        for file in get_files(folder["id"]):
            file["folder"] = folder["name"]
            file["folder_path"] = _folder_path(folder["id"], folders)
            files.append(file)
    return files


def download_file(file_id: str) -> Path:
    response = _get(f"file-refs/{file_id}").json()["data"]
    relationships = response.get("relationships", {})
    parent_id = relationships.get("parent", {}).get("data", {}).get("id")
    course_id = relationships.get("range", {}).get("data", {}).get("id")
    file = {
        "name": response["attributes"]["name"],
        "download_url": HOST + response["meta"]["download-url"],
        "is_downloadable": response["attributes"]["is-downloadable"],
    }
    if not file["is_downloadable"]:
        raise PermissionError(f"File {file_id} is not downloadable")

    if not course_id or not parent_id:
        raise ValueError(f"File {file_id} is missing its course or folder relationship")
    course = next(
        (course for course in get_my_courses() if course["id"] == course_id),
        None,
    )
    if course is None:
        raise ValueError(f"Course {course_id} for file {file_id} is not in the current course list")

    folders = _folder_index(course_id)
    if parent_id not in folders:
        raise ValueError(f"Folder {parent_id} for file {file_id} was not found in course {course_id}")

    def safe_segment(value: str) -> str:
        segment = Path(value).name.strip()
        return segment if segment not in {"", ".", ".."} else "_"

    folder_parts = Path(_folder_path(parent_id, folders)).parts
    path = _staging_dir() / safe_segment(course["title"])
    path = path.joinpath(*(safe_segment(part) for part in folder_parts), safe_segment(file["name"]))
    path.parent.mkdir(parents=True, exist_ok=True)

    r = session.get(file["download_url"], timeout=30)
    if r.status_code == 401:
        raise PermissionError(SESSION_EXPIRED)
    if r.status_code != 200:
        raise ValueError(f"Download failed with {r.status_code}: {r.text[:200]}")

    content_hash = hashlib.sha256(r.content).digest()
    if path.exists():
        if hashlib.sha256(path.read_bytes()).digest() == content_hash:
            return path

        updated_at = datetime.now().astimezone().strftime("%Y-%m-%d")
        versioned_path = path.with_name(f"{path.stem} (Stud.IP {updated_at}){path.suffix}")
        version = 2
        while versioned_path.exists():
            if hashlib.sha256(versioned_path.read_bytes()).digest() == content_hash:
                return versioned_path
            versioned_path = path.with_name(
                f"{path.stem} (Stud.IP {updated_at} {version}){path.suffix}"
            )
            version += 1
        path = versioned_path

    path.write_bytes(r.content)
    return path


def _fetch_dated_resources(
    endpoint: str,
    start_date: str | None,
    end_date: str | None,
    date_attributes: tuple[str, ...],
) -> list[dict]:
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if start and end and start > end:
        raise ValueError("start_date must be earlier than or equal to end_date")

    resources = _fetch_all(endpoint, {"page[limit]": 100})
    results = []
    for resource in resources:
        attributes = resource.get("attributes", {})
        resource_date = next(
            (attributes.get(key) for key in date_attributes if attributes.get(key)),
            None,
        )
        if _date_in_range(
            resource_date,
            start,
            end,
            start_is_date=bool(start_date and len(start_date) == 10),
            end_is_date=bool(end_date and len(end_date) == 10),
        ):
            results.append({
                "id": resource["id"],
                "type": resource.get("type"),
                **attributes,
            })
    return results


def get_course_events(
    course_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """List course events, optionally filtered by inclusive ISO 8601 dates."""
    return _fetch_dated_resources(
        f"courses/{course_id}/events",
        start_date,
        end_date,
        ("start", "start-date", "date"),
    )


def get_my_events(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """List events from the user's personal Stud.IP event collection."""
    return _fetch_dated_resources(
        f"users/{get_user_id()}/events",
        start_date,
        end_date,
        ("start", "start-date", "date"),
    )


def get_announcements(
    course_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """List course announcements, optionally for one course and date-filtered."""
    courses = (
        [course for course in get_my_courses() if course["id"] == course_id]
        if course_id is not None
        else get_my_courses()
    )
    if course_id is not None and not courses:
        raise ValueError(f"Course {course_id} is not in the current course list")

    announcements = []
    for course in courses:
        course_announcements = _fetch_dated_resources(
            f"courses/{course['id']}/news",
            start_date,
            end_date,
            ("publication-start", "date", "mkdate"),
        )
        announcements.extend(
            {
                **announcement,
                "course_id": course["id"],
                "course_title": course["title"],
            }
            for announcement in course_announcements
        )
    return sorted(
        announcements,
        key=lambda announcement: announcement.get("publication-start", ""),
        reverse=True,
    )


def _fingerprint(resource: dict) -> str:
    encoded = json.dumps(resource, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_update_state() -> dict:
    if not UPDATE_STATE_PATH.exists():
        return {}
    state = json.loads(UPDATE_STATE_PATH.read_text())
    if not isinstance(state, dict) or not isinstance(state.get("courses", {}), dict):
        raise ValueError(f"Invalid update state file: {UPDATE_STATE_PATH}")
    return state


def _save_update_state(state: dict) -> None:
    _ensure_app_data_dir()
    temporary_path = UPDATE_STATE_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(state, indent=2))
    temporary_path.replace(UPDATE_STATE_PATH)


def _course_snapshots(courses: list[dict]) -> dict[str, dict]:
    snapshots = {}
    for course in courses:
        course_id = course["id"]
        news_resources = _fetch_all(f"courses/{course_id}/news", {"page[limit]": 100})
        announcements = {
            resource["id"]: {
                "fingerprint": _fingerprint(resource.get("attributes", {})),
                "title": resource.get("attributes", {}).get("title"),
                "publication_start": resource.get("attributes", {}).get("publication-start"),
            }
            for resource in news_resources
        }
        files = get_course_files(course_id)
        file_snapshots = {
            file["id"]: {
                "fingerprint": _fingerprint(file),
                "name": file["name"],
                "folder_path": file["folder_path"],
                "size": file["size"],
            }
            for file in files
        }
        snapshots[course_id] = {
            "title": course["title"],
            "announcements": announcements,
            "files": file_snapshots,
        }
    return snapshots


def _semester_start_date(title: str) -> str:
    winter = re.fullmatch(r"WiSe\s+(\d{4})/(\d{2}|\d{4})", title, re.IGNORECASE)
    if winter:
        return f"{winter.group(1)}-10-01"
    summer = re.fullmatch(r"(?:SS|SoSe)\s*(\d{4})", title, re.IGNORECASE)
    if summer:
        return f"{summer.group(1)}-04-01"
    raise ValueError(f"Cannot infer semester start date from Stud.IP title: {title!r}")


def preview_initial_sync(start_date: str | None = None) -> dict:
    """Preview semester-start announcements, current files and events without setting a baseline."""
    semester = get_current_semester()
    start = start_date or _semester_start_date(semester["title"])
    parsed_start = _parse_date(start, "start_date")
    if parsed_start is None:
        raise ValueError("start_date is required")
    start = parsed_start.date().isoformat()
    today = datetime.now().astimezone().date().isoformat()
    courses = get_my_courses()
    all_announcements = get_announcements()
    announcements = []
    for item in all_announcements:
        published = (
            item.get("publication-start")
            or item.get("date")
            or item.get("mkdate")
        )
        published_date = str(published)[:10] if published else None
        if published_date is None or start <= published_date <= today:
            announcements.append({
                **item,
                "inventory_date": published_date,
                "date_confidence": "dated" if published_date else "undated; included for review",
            })
    course_files = {
        course["id"]: get_course_files(course["id"])
        for course in courses
    }

    semester_end = semester.get("end")
    course_events = []
    for course in courses:
        for event in get_course_events(course["id"], start, semester_end):
            course_events.append({
                "course_id": course["id"],
                "course_title": course["title"],
                "id": event.get("id"),
                "title": event.get("title"),
                "description": event.get("description"),
                "start": event.get("start"),
                "end": event.get("end"),
                "is_cancelled": event.get("is-cancelled", False),
            })

    preview_id = uuid.uuid4().hex
    pending = {
        "preview_id": preview_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": {
            "initialized": True,
            "semester_id": semester["id"],
            "semester_title": semester["title"],
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "courses": _course_snapshots(courses),
        },
    }
    _ensure_app_data_dir()
    PENDING_BASELINE_PATH.write_text(json.dumps(pending, indent=2))

    return {
        "preview_id": preview_id,
        "baseline_saved": False,
        "semester": semester["title"],
        "announcement_start_date": start,
        "announcements": [
            {
                "id": item["id"],
                "course_title": item["course_title"],
                "title": item.get("title"),
                "publication_start": item.get("inventory_date"),
                "date_confidence": item.get("date_confidence"),
            }
            for item in announcements
        ],
        "files": [
            {
                "id": file["id"],
                "course_title": course["title"],
                "name": file["name"],
                "folder_path": file["folder_path"],
                "size": file["size"],
                "date_available": False,
            }
            for course in courses
            for file in course_files[course["id"]]
        ],
        "course_events": sorted(course_events, key=lambda event: event.get("start") or ""),
    }


def confirm_initial_sync(preview_id: str) -> dict:
    """Record the exact previewed snapshot as the update baseline after explicit approval."""
    if not PENDING_BASELINE_PATH.exists():
        raise ValueError("No pending initial-sync preview exists; call preview_initial_sync first")
    pending = json.loads(PENDING_BASELINE_PATH.read_text())
    if pending.get("preview_id") != preview_id:
        raise ValueError("preview_id does not match the current pending initial-sync preview")
    state = pending.get("state")
    if not isinstance(state, dict) or not state.get("semester_id"):
        raise ValueError("Pending initial-sync preview is invalid")
    _save_update_state(state)
    PENDING_BASELINE_PATH.unlink()
    return {
        "baseline_saved": True,
        "semester": state["semester_title"],
        "last_checked": state["last_checked"],
        "course_count": len(state["courses"]),
        "announcement_count": sum(
            len(course["announcements"]) for course in state["courses"].values()
        ),
        "file_count": sum(len(course["files"]) for course in state["courses"].values()),
    }


def check_updates(
    upcoming_days: int = 14,
) -> dict:
    """Report new course news/files since the previous check and upcoming events.

    Requires a reviewed, confirmed initial-sync snapshot for the current semester.
    Reports new or changed content without downloading files.
    """
    if upcoming_days < 0:
        raise ValueError("upcoming_days must be zero or greater")

    previous_state = _load_update_state()
    semester = get_current_semester()
    if (
        not previous_state.get("initialized")
        or previous_state.get("semester_id") != semester["id"]
    ):
        return {
            "baseline_required": True,
            "semester": semester["title"],
            "message": (
                "Review preview_initial_sync first, then call confirm_initial_sync "
                "with its preview_id before checking incremental updates."
            ),
        }
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=upcoming_days)
    courses = get_my_courses()
    new_announcements = []
    changed_announcements = []
    new_files = []
    changed_files = []
    upcoming_events = []
    course_snapshots = {}

    for course in courses:
        course_id = course["id"]
        old_course = previous_state.get("courses", {}).get(course_id, {})
        course_baseline = not old_course
        news_resources = _fetch_all(f"courses/{course_id}/news", {"page[limit]": 100})
        news_snapshot = {}
        for resource in news_resources:
            attributes = resource.get("attributes", {})
            snapshot = {
                "fingerprint": _fingerprint(attributes),
                "title": attributes.get("title"),
                "publication_start": attributes.get("publication-start"),
            }
            news_snapshot[resource["id"]] = snapshot
            old_news = old_course.get("announcements", {}).get(resource["id"])
            item = {
                "id": resource["id"],
                "course_id": course_id,
                "course_title": course["title"],
                **attributes,
            }
            if old_news is None and not course_baseline:
                new_announcements.append(item)
            elif old_news and old_news.get("fingerprint") != snapshot["fingerprint"]:
                changed_announcements.append(item)

        course_files = get_course_files(course_id)
        file_snapshot = {}
        file_changes = []
        for file in course_files:
            snapshot = {
                "fingerprint": _fingerprint(file),
                "name": file["name"],
                "folder_path": file["folder_path"],
                "size": file["size"],
            }
            file_snapshot[file["id"]] = snapshot
            old_file = old_course.get("files", {}).get(file["id"])
            if old_file is None and not course_baseline:
                file_changes.append(("new", file))
            elif old_file and old_file.get("fingerprint") != snapshot["fingerprint"]:
                file_changes.append(("updated", file))

        for status, file in file_changes:
            result = {
                "id": file["id"],
                "course_id": course_id,
                "course_title": course["title"],
                "name": file["name"],
                "folder_path": file["folder_path"],
                "size": file["size"],
                "status": status,
            }
            if status == "new":
                new_files.append(result)
            else:
                changed_files.append(result)

        events = get_course_events(course_id, now.isoformat(), deadline.isoformat())
        upcoming_events.extend(
            {
                **event,
                "course_id": course_id,
                "course_title": course["title"],
            }
            for event in events
        )
        course_snapshots[course_id] = {
            "title": course["title"],
            "announcements": news_snapshot,
            "files": file_snapshot,
        }

    state = {
        "initialized": True,
        "semester_id": semester["id"],
        "semester_title": semester["title"],
        "last_checked": now.isoformat(),
        "courses": course_snapshots,
    }
    _save_update_state(state)

    upcoming_events.sort(key=lambda event: event.get("start", ""))
    return {
        "checked_at": now.isoformat(),
        "upcoming_days": upcoming_days,
        "new_announcements": new_announcements,
        "updated_announcements": changed_announcements,
        "new_files": new_files,
        "updated_files": changed_files,
        "upcoming_events": upcoming_events,
    }


# ---------------------------------------------------------------- quick test
if __name__ == "__main__":
    # sem = get_current_semester()
    # print("Current semester:", sem)
    # usr = get_user_id()
    courses = get_my_courses()

    # folders = get_folders(courses[0]["id"])
    # files = get_files(folders[0]["id"])
    # print(files)
    # print("saved to", download_file(files[0]))