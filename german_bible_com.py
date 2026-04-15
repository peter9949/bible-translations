import argparse
import json
import os
import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

GRAPHQL_URL = "https://presentation.youversionapi.com/graphql"
REQUEST_TIMEOUT = 30
REQUEST_RETRY_COUNT = 4
REQUEST_RETRY_BACKOFF_SECONDS = 1.5
DEFAULT_REQUEST_DELAY_SECONDS = 0.1

BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth", "1 Samuel",
    "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalm", "Proverbs", "Ecclesiastes", "Song Of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel",
    "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai",
    "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
    "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation",
]

USFM_BOOK_CODES = {
    "Genesis": "GEN",
    "Exodus": "EXO",
    "Leviticus": "LEV",
    "Numbers": "NUM",
    "Deuteronomy": "DEU",
    "Joshua": "JOS",
    "Judges": "JDG",
    "Ruth": "RUT",
    "1 Samuel": "1SA",
    "2 Samuel": "2SA",
    "1 Kings": "1KI",
    "2 Kings": "2KI",
    "1 Chronicles": "1CH",
    "2 Chronicles": "2CH",
    "Ezra": "EZR",
    "Nehemiah": "NEH",
    "Esther": "EST",
    "Job": "JOB",
    "Psalm": "PSA",
    "Proverbs": "PRO",
    "Ecclesiastes": "ECC",
    "Song Of Solomon": "SNG",
    "Isaiah": "ISA",
    "Jeremiah": "JER",
    "Lamentations": "LAM",
    "Ezekiel": "EZK",
    "Daniel": "DAN",
    "Hosea": "HOS",
    "Joel": "JOL",
    "Amos": "AMO",
    "Obadiah": "OBA",
    "Jonah": "JON",
    "Micah": "MIC",
    "Nahum": "NAM",
    "Habakkuk": "HAB",
    "Zephaniah": "ZEP",
    "Haggai": "HAG",
    "Zechariah": "ZEC",
    "Malachi": "MAL",
    "Matthew": "MAT",
    "Mark": "MRK",
    "Luke": "LUK",
    "John": "JHN",
    "Acts": "ACT",
    "Romans": "ROM",
    "1 Corinthians": "1CO",
    "2 Corinthians": "2CO",
    "Galatians": "GAL",
    "Ephesians": "EPH",
    "Philippians": "PHP",
    "Colossians": "COL",
    "1 Thessalonians": "1TH",
    "2 Thessalonians": "2TH",
    "1 Timothy": "1TI",
    "2 Timothy": "2TI",
    "Titus": "TIT",
    "Philemon": "PHM",
    "Hebrews": "HEB",
    "James": "JAS",
    "1 Peter": "1PE",
    "2 Peter": "2PE",
    "1 John": "1JN",
    "2 John": "2JN",
    "3 John": "3JN",
    "Jude": "JUD",
    "Revelation": "REV",
}

GERMAN_BIBLE_COM_TRANSLATIONS = {
    "DELUT": {
        "id": 51,
        "name": "Lutherbibel 1912",
    },
    "ELB": {
        "id": 57,
        "name": "Darby Unrevidierte Elberfelder",
    },
    "ELB71": {
        "id": 58,
        "name": "Elberfelder 1871",
    },
    "ELBBK": {
        "id": 2351,
        "name": "Elberfelder Ubersetzung (Version von bibelkommentare.de)",
    },
    "HFA": {
        "id": 73,
        "name": "Hoffnung fur Alle",
    },
    "LUTheute": {
        "id": 3100,
        "name": "luther.heute",
    },
    "NGU2011": {
        "id": 108,
        "name": "Neue Genfer Ubersetzung",
    }
}

GRAPHQL_GET_BIBLE_VERSES = """
query GetBibleVerses($references: [String!], $id: Int!, $format: Format = HTML) {
  getBibleVerses(format: $format, id: $id, references: $references) {
    response {
      data {
        verses {
          content
        }
      }
    }
  }
}
"""


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def request_with_retry(session: requests.Session, payload: dict) -> dict:
    last_error: Optional[Exception] = None

    for attempt in range(1, REQUEST_RETRY_COUNT + 1):
        try:
            response = session.post(
                GRAPHQL_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < REQUEST_RETRY_COUNT:
                time.sleep(REQUEST_RETRY_BACKOFF_SECONDS * attempt)

    raise RuntimeError(f"Request failed after {REQUEST_RETRY_COUNT} attempts: {last_error}")


def fetch_verses_html(
    session: requests.Session,
    translation_id: int,
    references_expr: str,
) -> Optional[str]:
    payload = {
        "query": GRAPHQL_GET_BIBLE_VERSES,
        "variables": {
            "references": [references_expr],
            "id": translation_id,
            "format": "HTML",
        },
        "operationName": "GetBibleVerses",
    }

    data = request_with_retry(session, payload)

    if "errors" in data:
        return None

    verses = (
        data.get("data", {})
        .get("getBibleVerses", {})
        .get("response", {})
        .get("data", {})
        .get("verses", [])
    )

    if not verses:
        return None

    return verses[0].get("content")


def parse_verses_from_html(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    verses: Dict[str, str] = {}

    for verse_node in soup.select("span.verse[data-usfm]"):
        for removable in verse_node.select(
            "span.label, sup, span.note, span.crossreference, span.footnote, .footnote, .crossreference"
        ):
            removable.decompose()

        usfm_ref = verse_node.get("data-usfm", "")
        verse_number = usfm_ref.split(".")[-1]
        verse_text = normalize_space(verse_node.get_text(" ", strip=True))

        if verse_number.isdigit() and verse_text:
            verses[verse_number] = verse_text

    return verses


def ensure_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def ensure_clean_folder(path: str) -> int:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
        return 0

    deleted_count = 0
    for name in os.listdir(path):
        if not name.endswith(".json"):
            continue
        os.remove(os.path.join(path, name))
        deleted_count += 1

    return deleted_count


def load_template_chapter_verse_counts(template_books_folder: str) -> Dict[str, Dict[int, int]]:
    counts: Dict[str, Dict[int, int]] = {}

    for file_name in os.listdir(template_books_folder):
        if not file_name.endswith(".json"):
            continue

        file_path = os.path.join(template_books_folder, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(data, dict) or len(data) != 1:
            continue

        book_name = next(iter(data.keys()))
        chapters = data.get(book_name, {})
        if not isinstance(chapters, dict):
            continue

        chapter_counts: Dict[int, int] = {}
        for chapter_key, verses in chapters.items():
            if not chapter_key.isdigit() or not isinstance(verses, dict) or not verses:
                continue

            verse_numbers = [int(v) for v in verses.keys() if str(v).isdigit()]
            if not verse_numbers:
                continue

            chapter_counts[int(chapter_key)] = max(verse_numbers)

        if chapter_counts:
            counts[book_name] = chapter_counts

    return counts


def fetch_chapter_with_fallback(
    session: requests.Session,
    translation_id: int,
    usfm_book: str,
    chapter_number: int,
    verse_numbers: List[int],
) -> Dict[str, str]:
    if not verse_numbers:
        return {}

    refs = "+".join(f"{usfm_book}.{chapter_number}.{verse_number}" for verse_number in verse_numbers)
    html = fetch_verses_html(session, translation_id, refs)

    if html:
        parsed = parse_verses_from_html(html)
        if parsed:
            return parsed

    if len(verse_numbers) == 1:
        return {}

    mid = len(verse_numbers) // 2
    left = fetch_chapter_with_fallback(session, translation_id, usfm_book, chapter_number, verse_numbers[:mid])
    right = fetch_chapter_with_fallback(session, translation_id, usfm_book, chapter_number, verse_numbers[mid:])

    merged = {}
    merged.update(left)
    merged.update(right)
    return merged


def combine_books(books_folder: str, output_file: str, translation_code: str, translation_name: str) -> None:
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
                verse_list.append(
                    {
                        "verse": int(verse_key),
                        "text": verses[verse_key],
                    }
                )

            chapter_list.append(
                {
                    "chapter": int(chapter_key),
                    "verses": verse_list,
                }
            )

        formatted["books"].append(
            {
                "name": book,
                "chapters": chapter_list,
            }
        )

    with open(output_file, "w", encoding="utf-8") as out_file:
        json.dump(formatted, out_file, indent=4, ensure_ascii=False)


def parse_args():
    parser = argparse.ArgumentParser(description="Download German Bible translations from Bible.com")
    parser.add_argument("--translation-code", default="LUTheute", help="Translation code, e.g. LUTheute")
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


def main() -> None:
    args = parse_args()
    translation_code = args.translation_code.strip()

    if translation_code not in GERMAN_BIBLE_COM_TRANSLATIONS:
        available = ", ".join(sorted(GERMAN_BIBLE_COM_TRANSLATIONS.keys()))
        raise ValueError(f"Unknown translation code '{translation_code}'. Available: {available}")

    translation_config = GERMAN_BIBLE_COM_TRANSLATIONS[translation_code]
    translation_id = int(translation_config["id"])
    translation_name = str(translation_config["name"])

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

    template_counts = load_template_chapter_verse_counts(os.path.join("german", "SCH2000", "SCH2000_books"))
    if not template_counts:
        raise RuntimeError("Could not load template chapter counts from german/SCH2000/SCH2000_books")

    books_queue = BOOKS[:]
    if args.max_books > 0:
        books_queue = books_queue[: args.max_books]

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
        }
    )

    failed_books: List[str] = []
    skipped_books: List[str] = []

    for index, book_name in enumerate(books_queue, start=1):
        output_path = os.path.join(books_folder, f"{book_name}.json")

        if args.resume and os.path.exists(output_path):
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (existing)", end="")
            continue

        usfm_book = USFM_BOOK_CODES.get(book_name)
        if not usfm_book:
            failed_books.append(book_name)
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (missing usfm)", end="")
            continue

        chapter_templates = template_counts.get(book_name, {})
        if not chapter_templates:
            failed_books.append(book_name)
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (no template)", end="")
            continue

        probe_ref = f"{usfm_book}.1.1"
        probe_html = fetch_verses_html(session, translation_id, probe_ref)
        if not probe_html:
            skipped_books.append(book_name)
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (not available)", end="")
            continue

        chapters_payload: Dict[str, Dict[str, str]] = {}
        chapter_numbers = sorted(chapter_templates.keys())

        if args.max_chapters > 0:
            chapter_numbers = chapter_numbers[: args.max_chapters]

        for chapter_number in chapter_numbers:
            max_verse = chapter_templates[chapter_number]
            verse_numbers = list(range(1, max_verse + 1))
            parsed = fetch_chapter_with_fallback(
                session,
                translation_id,
                usfm_book,
                chapter_number,
                verse_numbers,
            )

            if parsed:
                ordered = {
                    str(verse_number): parsed[str(verse_number)]
                    for verse_number in sorted(int(v) for v in parsed.keys())
                }
                chapters_payload[str(chapter_number)] = ordered

            if args.request_delay > 0:
                time.sleep(args.request_delay)

        if not chapters_payload:
            failed_books.append(book_name)
            print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (no chapters)", end="")
            continue

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({book_name: chapters_payload}, f, indent=4, ensure_ascii=False)

        print(f"\r[+] {index:2d}/{len(books_queue):2d} {book_name:<20} (ok)", end="")

    print()

    combine_books(books_folder, output_file, translation_code, translation_name)
    print(f"[+] Combined output written to {output_file}")

    if skipped_books:
        print(f"[+] Not available in this version ({len(skipped_books)}): {', '.join(skipped_books)}")
    if failed_books:
        print(f"[+] Incomplete books ({len(failed_books)}): {', '.join(failed_books)}")


if __name__ == "__main__":
    main()
