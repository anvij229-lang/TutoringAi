import re

SOURCE_PATTERN = re.compile(
r"(Page\s+\d+|Slide\s+\d+|Video\s+(?:\d+:)?\d{1,2}:\d{2})",
re.IGNORECASE,
)


def clean_source_label(value):
    text = " ".join(str(value or "").split())
    match = SOURCE_PATTERN.search(text)
    if not match:
        return None
    kind, number = match.group(1).split(None, 1)
    return f"{kind.capitalize()} {number}"

def format_seconds(seconds) -> str:
    total = int(seconds or 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def source_label(file_type, page_number, start_seconds) -> str:
    if start_seconds is not None:
        return f"Video {format_seconds(start_seconds)}"
    if file_type == "pptx":
        return f"Slide {page_number}"
    return f"Page {page_number}"

def with_file_name(label, title, multi: bool):
    if not label or not multi or not title:
        return label
    return f"{title}, {label}"