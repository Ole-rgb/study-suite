"""Stud.IP MCP server."""

from functools import wraps
from mcp.server.mcpserver import MCPServer

import studip_client as studip

mcp = MCPServer("Stud.IP Study Suite")


def safe_tool(f):
    """Turn exceptions into {"error": ...} so the chat can relay the real failure."""
    @wraps(f)
    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as exc:
            return {"error": str(exc)}
    return inner


@mcp.tool()
@safe_tool
def open_studip_login() -> dict:
    """Open a dedicated Firefox window for you to sign in to Stud.IP interactively."""
    return studip.open_studip_login()


@mcp.tool()
@safe_tool
def verify_studip_login() -> dict:
    """Check whether the dedicated browser is signed in, without exposing cookies."""
    return studip.verify_studip_login()


@mcp.tool()
@safe_tool
def current_semester() -> dict:
    """Return the current Stud.IP semester (id, title, end date)."""
    sem = studip.get_current_semester()
    return {
        "id": sem["id"],
        "title": sem["title"],
        "end": sem["end"]
    }

@mcp.tool()
@safe_tool
def list_courses(refresh: bool = False) -> list[dict] | dict:
    """List the courses I'm enrolled in. Defaults to the current semester."""
    return studip.get_my_courses(refresh)


@mcp.tool()
@safe_tool
def list_course_files(course_id: str) -> list[dict] | dict:
    """List course files with their full nested folder path."""
    return studip.get_course_files(course_id)


@mcp.tool()
@safe_tool
def download_file(file_id: str) -> str | dict:
    """Stage a selected Stud.IP file in the vault's .tmp/StudIP folder and return its path."""
    return str(studip.download_file(file_id))


@mcp.tool()
@safe_tool
def list_course_events(
    course_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict] | dict:
    """List course events; filter inclusively using ISO 8601 start_date/end_date."""
    return studip.get_course_events(course_id, start_date, end_date)


@mcp.tool()
@safe_tool
def list_events(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict] | dict:
    """List personal Stud.IP events; optionally filter by inclusive ISO 8601 dates."""
    return studip.get_my_events(start_date, end_date)


@mcp.tool()
@safe_tool
def list_announcements(
    course_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict] | dict:
    """List announcements for enrolled courses, or one course; optionally filter dates.

    Dates are inclusive ISO 8601 dates or datetimes. Omit course_id to search all
    courses; use list_courses to find a course ID.
    """
    return studip.get_announcements(course_id, start_date, end_date)


@mcp.tool()
@safe_tool
def preview_initial_sync(start_date: str | None = None) -> dict:
    """Preview announcements, course files and events without recording an update baseline.

    Defaults to the semester start inferred from Stud.IP. Review the returned inventory
    before confirming it; files are not downloaded.
    """
    return studip.preview_initial_sync(start_date)


@mcp.tool()
@safe_tool
def confirm_initial_sync(preview_id: str) -> dict:
    """Record a previously reviewed initial-sync preview as the update baseline."""
    return studip.confirm_initial_sync(preview_id)


@mcp.tool()
@safe_tool
def check_updates(
    upcoming_days: int = 14,
) -> dict:
    """Check all enrolled courses for new announcements/files and upcoming events.

    Requires a reviewed and confirmed initial-sync preview for the current semester.
    This tool reports candidates but does not download files. Use download_file only
    after selecting a file; it stages the download for the tutor to organize.
    """
    return studip.check_updates(upcoming_days)


if __name__ == "__main__":
    mcp.run()