import json
import os
import sys

import meaningless.utilities.common as common
from meaningless import JSONDownloader
from meaningless.utilities.common import BIBLE_TRANSLATIONS


def custom_get_capped_integer(number, min_value=1, max_value=200):
    return min(max(int(number), int(min_value)), int(max_value))


common.get_capped_integer = custom_get_capped_integer

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

# Verified from BibleGateway versions page (as of 2026-04-12).
# These Polish versions are listed as NT-only.
POLISH_TRANSLATIONS = {
    "NP": {
        "name": "Nowe Przymierze",
        "books": NT_BOOKS,
        "is_nt_only": True,
    },
    "SZ-PL": {
        "name": "Slowo Zycia",
        "books": NT_BOOKS,
        "is_nt_only": True,
    },
    "UBG": {
        "name": "Updated Gdansk Bible",
        "books": NT_BOOKS,
        "is_nt_only": True,
    },
}


def download_book(book_name, folder, translation_code):
    downloader = JSONDownloader(
        translation=translation_code,
        show_passage_numbers=False,
        strip_excess_whitespace=True,
    )
    output_file = os.path.join(folder, f"{book_name}.json")
    return downloader.download_book(book_name, output_file) == 1


def combine_books(folder, output_file, translation_code):
    combined_data = {}

    for file_name in os.listdir(folder):
        if not file_name.endswith(".json"):
            continue

        file_path = os.path.join(folder, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing {file_name}: {e}")
            continue

        if "Info" in data:
            del data["Info"]

        for book, chapters in data.items():
            for chapter, verses in chapters.items():
                for verse_num, verse_content in verses.items():
                    data[book][chapter][verse_num] = verse_content.strip()

        combined_data.update(data)

    translation_name = BIBLE_TRANSLATIONS.get(translation_code, "Unknown translation")
    formatted = {
        "translation": f"{translation_code}: {translation_name}",
        "books": [],
    }

    for book in BOOKS:
        if book not in combined_data:
            continue

        chapters = combined_data[book]
        chapter_list = []

        for chapter_key in sorted(chapters.keys(), key=lambda x: int(x)):
            verses = chapters[chapter_key]
            verse_list = []

            for verse_key in sorted(verses.keys(), key=lambda x: int(x)):
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


def generate_progress_bar(progress, total, length=30):
    progress_ratio = min(progress / total, 1)
    progress_bar_length = int(progress_ratio * length)
    progress_bar = "#" * progress_bar_length + "-" * (length - progress_bar_length)
    return f"[{progress_bar}] {progress:2d}/{total}"


def generate_polish_bible(translation_code, books_to_download):
    root_folder = translation_code
    books_folder = os.path.join(root_folder, f"{translation_code}_books")

    if not os.path.exists(root_folder):
        os.makedirs(root_folder)

    if not os.path.exists(books_folder):
        os.makedirs(books_folder)

    existing_files = os.listdir(books_folder)
    for file_name in existing_files:
        os.remove(os.path.join(books_folder, file_name))

    print(f"[+] Cleared {len(existing_files)} file(s) from {books_folder}")

    failed_book = ""
    for i, book in enumerate(books_to_download):
        ok = download_book(book, books_folder, translation_code)
        if not ok:
            failed_book = book
            break

        print(
            f"\r[+] Downloading {translation_code:<7} "
            f"({generate_progress_bar(i + 1, len(books_to_download))})",
            end="",
        )

    print()

    if failed_book:
        print(f"[+] ERROR: failed while downloading {failed_book}.")
        print("[+] Tip: try a different Polish code or use the custom option.")
        return

    output_file = os.path.join(root_folder, f"{translation_code}_bible.json")
    combine_books(books_folder, output_file, translation_code)
    print(f"[+] Done: combined output written to {output_file}")


def pick_translation_code():
    print("[+] Polish translation presets:")

    preset_codes = list(POLISH_TRANSLATIONS.keys())
    for index, code in enumerate(preset_codes, start=1):
        label = POLISH_TRANSLATIONS[code]["name"]
        suffix = " (NT only)" if POLISH_TRANSLATIONS[code]["is_nt_only"] else ""
        print(f"    {index}. {code} - {label}{suffix}")

    print("    0. Custom code")

    choice = input("[+] Pick option: ").strip()

    if choice == "0":
        code = input("[+] Enter custom BibleGateway translation code: ").strip().upper()
        custom_scope = input("[+] Download scope for custom code? (NT/FULL, default NT): ").strip().upper()
        if custom_scope == "FULL":
            return code, BOOKS
        return code, NT_BOOKS

    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(preset_codes):
            code = preset_codes[index - 1]
            return code, POLISH_TRANSLATIONS[code]["books"]

    print("[+] Invalid option. Falling back to NP (NT only).")
    return "NP", NT_BOOKS


if __name__ == "__main__":
    print("[+] BibleGateway Polish Bible Downloader")
    print(f"[+] Installed translations available via meaningless: {len(BIBLE_TRANSLATIONS)}")

    translation, books_to_download = pick_translation_code()

    if translation not in BIBLE_TRANSLATIONS:
        print(
            f"[+] Warning: '{translation}' is not currently listed in BIBLE_TRANSLATIONS. "
            "Download may still work if BibleGateway supports it."
        )

    if books_to_download == NT_BOOKS:
        print("[+] Download mode: NT only")
    else:
        print("[+] Download mode: Full Bible")

    generate_polish_bible(translation, books_to_download)
