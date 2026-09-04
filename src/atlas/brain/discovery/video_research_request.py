"""Strict task contract for bounded YouTube video research."""

from atlas.brain.models import Task

VIDEO_RESEARCH_TASK_CATEGORY = "video_research"
VIDEO_RESEARCH_TASK_PREFIX = "Research YouTube video: "
VIDEO_RESEARCH_CATEGORY_MARKER = " | category: "


def video_research_task_description(category: str, youtube_url: str) -> str:
    category = category.strip()
    youtube_url = youtube_url.strip()

    if not category:
        raise ValueError("video research category must not be empty")
    if not youtube_url:
        raise ValueError("video research YouTube URL must not be empty")
    if VIDEO_RESEARCH_CATEGORY_MARKER in youtube_url:
        raise ValueError("invalid YouTube URL")

    return (
        f"{VIDEO_RESEARCH_TASK_PREFIX}{youtube_url}"
        f"{VIDEO_RESEARCH_CATEGORY_MARKER}{category}"
    )


def parse_video_research_task(task: Task) -> tuple[str, str]:
    if task.category != VIDEO_RESEARCH_TASK_CATEGORY:
        raise ValueError(
            f"task {task.id!r} has category {task.category!r}, "
            f"not {VIDEO_RESEARCH_TASK_CATEGORY!r}"
        )

    description = task.description
    if not description.startswith(VIDEO_RESEARCH_TASK_PREFIX):
        raise ValueError(
            f"task {task.id!r} is not a real video-research task"
        )

    payload = description[len(VIDEO_RESEARCH_TASK_PREFIX):]

    if VIDEO_RESEARCH_CATEGORY_MARKER not in payload:
        raise ValueError(
            f"task {task.id!r} has no video research category marker"
        )

    youtube_url, category = payload.rsplit(
        VIDEO_RESEARCH_CATEGORY_MARKER,
        1,
    )

    youtube_url = youtube_url.strip()
    category = category.strip()

    if not youtube_url or not category:
        raise ValueError(
            f"task {task.id!r} has incomplete video research payload"
        )

    return category, youtube_url
