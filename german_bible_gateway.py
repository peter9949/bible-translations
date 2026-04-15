import argparse
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

PASSAGE_URL = "https://www.biblegateway.com/passage/"
REQUEST_TIMEOUT = 20
REQUEST_RETRY_COUNT = 4
REQUEST_RETRY_BACKOFF_SECONDS = 1.5
DEFAULT_REQUEST_DELAY_SECONDS = 0.2

BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth", "1 Samuel",
    "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalm", "Proverbs", "Ecclesiastes", "Song Of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel",
    "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai",
    "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
    "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]

NT_BOOKS = [
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
    "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]

# Source lists:
# - https://www.bible.com/de/languages/deu (popular German versions)
# - https://www.biblegateway.com/versions/ (code compatibility checks)
GERMAN_TRANSLATIONS = {
    "SCH2000": {
        "name": "Schlachter 2000",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "SCH1951": {
        "name": "Schlachter 1951",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "LUTH1545": {
        "name": "Luther Bibel 1545",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "HOF": {
        "name": "Hoffnung fur Alle",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "HFA": {
        "name": "Hoffnung fur Alle",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "NGU-DE": {
        "name": "Neue Genfer Ubersetzung",
        "books": NT_BOOKS,
        "is_nt_only": True,
    },
    "NGU2011": {
        "name": "Neue Genfer Ubersetzung",
        "books": NT_BOOKS,
        "is_nt_only": True,
    },
    "ELB": {
        "name": "Darby Unrevidierte Elberfelder",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "ELB71": {
        "name": "Elberfelder 1871",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "ELBBK": {
        "name": "Elberfelder Ubersetzung (bibelkommentare.de)",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "DELUT": {
        "name": "Lutherbibel 1912",
        "books": BOOKS,
        "is_nt_only": False,
    },
    "LUTheute": {
        "name": "luther.heute",
        "books": BOOKS,
        "is_nt_only": False,
    },
}

GERMAN_CODE_ALIASES = {
    "HFA": "HFA",
    "HOF": "HFA",
    "NGU2011": "NGU2011",
    "NGU-DE": "NGU2011",
    "LUTHEUTE": "LUTheute",
}

VERSE_CLASS_RE = re.compile(r"^[A-Za-z0-9]+-(?P<chapter>\d+)-(?P<verse>\d+)$")


def normalize_space(text):
    return re.sub(r"\s+", " ", text).strip()


def clean_verse_span(span):
    for removable in span.select(
        "sup, span.footnote, span.crossreference, span.citation, .crossreference, .footnote"
    ):
        removable.decompose()
    return normalize_space(span.get_text(" ", strip=True))


def request_with_retry(session, params):
    last_error = None
    for attempt in range(1, REQUEST_RETRY_COUNT + 1):
        try:
            response = session.get(PASSAGE_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < REQUEST_RETRY_COUNT:
                time.sleep(REQUEST_RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"Request failed after {REQUEST_RETRY_COUNT} attempts: {last_error}")


def fetch_chapter(session, translation_code, book_name, chapter_number):
    params = {
        "search": f"{book_name} {chapter_number}",
        "version": translation_code,
    }

    response = request_with_retry(session, params)
    soup = BeautifulSoup(response.text, "html.parser")

    verses = {}
    for span in soup.select("span.text"):
        matched_class = None
        for cls in span.get("class", []):
            match = VERSE_CLASS_RE.match(cls)
            if match:
                matched_class = match
                break

        if not matched_class:
            continue

        chapter_value = int(matched_class.group("chapter"))
        if chapter_value != chapter_number:
            continue

        verse_number = matched_class.group("verse")
        verse_text = clean_verse_span(span)
        if verse_text:
            verses[verse_number] = verse_text

    return verses


def ensure_folder(path):
    os.makedirs(path, exist_ok=True)


def ensure_clean_folder(path):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
        return 0

    deleted_count = 0
    for name in os.listdir(path):
        if not name.endswith(".json"):
            continue
        file_path = os.path.join(path, name)
        os.remove(file_path)
        deleted_count += 1

    return deleted_count


def combine_books(books_folder, output_file, translation_code, translation_name):
    combined_data = {}

    for file_name in os.listdir(books_folder):
        if not file_name.endswith(".json"):
            continue

        file_path = os.path.join(books_folder, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[+] Warning: cannot parse {file_name}: {exc}")
            continue

        combined_data.update(data)

    formatted = {
        "translation": f"{translation_code}: {translation_name}",
        "books": [],
    }

    for book in BOOKS:
        if book not in combined_data:
            continue

        chapters = combined_data[book]
        chapter_list = []

        for chapter_key in sorted(chapters.keys(), key=lambda value: int(value)):
            verses = chapters[chapter_key]
            verse_list = []

            for verse_key in sorted(verses.keys(), key=lambda value: int(value)):
                verse_list.append({
                    "verse": int(verse_key),
                    "text": verses[verse_key],
                })

            chapter_list.append({
                "chapter": int(chapter_key),
                "verses": verse_list,
            })

        formatted["books"].append({
            "name": book,
            "chapters": chapter_list,
        })

    with open(output_file, "w", encoding="utf-8") as out_file:
        json.dump(formatted, out_file, indent=4, ensure_ascii=False)


def download_book(session, translation_code, book_name, output_path, request_delay, max_chapters=0):
    chapters = {}
    chapter_number = 1

    while True:
        if max_chapters > 0 and chapter_number > max_chapters:
            break

        verses = fetch_chapter(session, translation_code, book_name, chapter_number)
        if not verses:
            break

        chapters[str(chapter_number)] = verses
        chapter_number += 1

        if request_delay > 0:
            time.sleep(request_delay)

    if not chapters:
        return False

    payload = {book_name: chapters}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)

    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Download German Bible translations from BibleGateway")
    parser.add_argument("--translation-code", default="SCH2000", help="German translation code, e.g. SCH2000")
    parser.add_argument("--max-books", type=int, default=0, help="Only download first N books (0 = all)")
    parser.add_argument("--max-chapters", type=int, default=0, help="Only download first N chapters per book (0 = all)")
    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
        help="Delay between chapter requests in seconds",
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        help="Keep existing book JSON files and only download missing ones",
    )
    parser.add_argument(
        "--fresh",
        dest="resume",
        action="store_false",
        help="Delete existing book JSON files before downloading",
    )
    parser.set_defaults(resume=True)
    return parser.parse_args()


def resolve_translation(translation_code):
    raw_code = translation_code.strip()
    code = GERMAN_CODE_ALIASES.get(raw_code.upper(), raw_code)
    if code in GERMAN_TRANSLATIONS:
        preset = GERMAN_TRANSLATIONS[code]
        return code, preset["name"], preset["books"]

    print(f"[+] Warning: '{code}' is not in known German presets. Using full book list.")
    return code, "Custom German Translation", BOOKS


def main():
    args = parse_args()
    translation_code, translation_name, books_to_download = resolve_translation(args.translation_code)

    root_folder = os.path.join("german", translation_code)
    books_folder = os.path.join(root_folder, f"{translation_code}_books")
    output_file = os.path.join(root_folder, f"{translation_code}_bible.json")

    ensure_folder(root_folder)
    ensure_folder(books_folder)

    if args.resume:
        existing_count = len([name for name in os.listdir(books_folder) if name.endswith(".json")])
        print(f"[+] Resume mode: keeping {existing_count} existing file(s) in {books_folder}")
    else:
        deleted_count = ensure_clean_folder(books_folder)
        print(f"[+] Cleared {deleted_count} file(s) from {books_folder}")

    books_queue = books_to_download
    if args.max_books > 0:
        books_queue = books_to_download[: args.max_books]

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
    )

    failed_books = []
    for index, book_name in enumerate(books_queue, start=1):
        output_path = os.path.join(books_folder, f"{book_name}.json")

        if args.resume and os.path.exists(output_path):
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (existing)", end="")
            continue

        try:
            ok = download_book(
                session,
                translation_code,
                book_name,
                output_path,
                request_delay=max(args.request_delay, 0.0),
                max_chapters=max(args.max_chapters, 0),
            )
        except Exception as exc:
            print(f"\n[+] Error while downloading {book_name}: {exc}")
            failed_books.append(book_name)
            continue

        status = "ok" if ok else "no verses"
        if not ok:
            failed_books.append(book_name)

        print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} ({status})", end="")

    print()

    combine_books(books_folder, output_file, translation_code, translation_name)
    print(f"[+] Combined output written to {output_file}")

    if failed_books:
        print(f"[+] Incomplete books ({len(failed_books)}): {', '.join(failed_books)}")


if __name__ == "__main__":
    main()
