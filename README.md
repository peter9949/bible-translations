# BibleTranslations
<p align=center>
  <img alt="Github Created At" src="https://img.shields.io/github/created-at/jadenzaleski/bible-translations?style=flat-square&color=orange">
  <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/jadenzaleski/bible-translations?style=flat-square&label=last%20master%20commit">
  <img alt="GitHub last commit (branch)" src="https://img.shields.io/github/last-commit/jadenzaleski/bible-translations/development?style=flat-square&label=last%20development%20commit">
</p>

<p>Here you can generate a formatted version of all the Holy Bible translations that are availabe at <a href="https://www.biblegateway.com">Bible Gateway</a>, in JSON and SQL format.
Text is downloaded with the help of the <a href="https://github.com/daniel-tran/meaningless">meaningless</a> package. Run the <code>bible_gateway.py</code> script to get started. Feel free to create any issues or pull requests as needed.
I will add more versions as they are supported by the <a href="https://github.com/daniel-tran/meaningless">meaningless</a> package.</p>

## Polish Translations via Biblia-Online.pl

If you want full Polish Bible datasets, use <code>biblia_online_polish.py</code>.
It downloads text from <a href="https://biblia-online.pl">biblia-online.pl</a> and writes output in the same JSON format used by this repository.

### Quick start

<pre><code>python biblia_online_polish.py --translation-code BW
</code></pre>

<pre><code>pip install requests beautifulsoup4
</code></pre>

### Examples

<pre><code># Biblia Jakuba Wujka
python biblia_online_polish.py --translation-code WUJ

# Uwspółcześniona Biblia Gdańska
python biblia_online_polish.py --translation-code UBG

# Force a full redownload instead of resuming from existing book files
python biblia_online_polish.py --translation-code UBG --fresh

# Direct custom slug from biblia-online.pl
python biblia_online_polish.py --translation-code CUSTOM --translation-slug Warszawska
</code></pre>

### Notes

<ul>
  <li>This script uses HTML parsing (no public API was found).</li>
  <li>By default the downloader resumes from existing per-book JSON files and retries failed requests.</li>
  <li>Use <code>--fresh</code> if you want to clear the book folder and redownload everything from scratch.</li>
  <li>Please respect site terms, translation copyrights, and fair-use limits.</li>
  <li>Use <code>--max-books</code> for quick testing before full downloads.</li>
</ul>

## German Translations via BibleGateway

If you want German Bible datasets, use <code>german_bible_gateway.py</code>.
It scrapes the BibleGateway passage URL (<code>https://www.biblegateway.com/passage/</code>) and writes output into <code>german/&lt;CODE&gt;/</code>.

### Quick start

<pre><code>python german_bible_gateway.py
</code></pre>

<pre><code>pip install requests beautifulsoup4
</code></pre>

<pre><code># Download only first book for a quick smoke test
python german_bible_gateway.py --translation-code SCH2000 --max-books 1

# Force a clean full redownload
python german_bible_gateway.py --translation-code SCH2000 --fresh
</code></pre>

### Presets (from BibleGateway versions page)

<ul>
  <li>SCH2000 - Schlachter 2000</li>
  <li>SCH1951 - Schlachter 1951</li>
  <li>LUTH1545 - Luther Bibel 1545</li>
  <li>HOF - Hoffnung fur Alle</li>
  <li>NGU-DE - Neue Genfer Ubersetzung (NT only)</li>
</ul>

You can also pass a custom translation code with <code>--translation-code</code>.

## French Translations via Multiple Sources

If you want French Bible datasets, use <code>french_translations.py</code>.
It supports multiple sources for the same translation:

<ul>
  <li><code>beblia</code> (XML files from Holy-Bible-XML-Format)</li>
  <li><code>bible-com</code> (YouVersion GraphQL endpoint)</li>
  <li><code>auto</code> (default: tries beblia first, then bible-com fallback)</li>
</ul>

### Quick start

<pre><code>python french_translations.py --translation-code LSG
</code></pre>

<pre><code>pip install requests beautifulsoup4
</code></pre>

### Popular presets

<ul>
  <li>LSG - Louis Segond 1910</li>
  <li>S21 - Segond 21</li>
  <li>BDS - Bible du Semeur 2015</li>
  <li>BFC - Bible en Francais Courant</li>
  <li>PDV2017 - Parole de Vie 2017</li>
  <li>NBS - Nouvelle Bible Segond</li>
  <li>NEG79 - Nouvelle Edition de Geneve 1979</li>
  <li>JND - J.N. Darby</li>
  <li>OST - Ostervald</li>
</ul>

### Examples

<pre><code># Force a specific source
python french_translations.py --translation-code S21 --source beblia
python french_translations.py --translation-code S21 --source bible-com

# Run a quick smoke test
python french_translations.py --translation-code LSG --max-books 1 --max-chapters 2

# Force a full clean redownload
python french_translations.py --translation-code BDS --fresh

# Custom translation with explicit source parameters
python french_translations.py --translation-code CUSTOM --source bible-com --bible-com-id 93
python french_translations.py --translation-code CUSTOM --source beblia --beblia-file FrenchS21Bible.xml
</code></pre>

> [!WARNING]
> Due to copyright issues, all formatted bible text has been removed from the repository. If you want to use the
> formatted files, you will have to generate them yourself with the script.

> [!IMPORTANT]
> This repository is **actively under development**. You can follow along in the <a href="https://github.com/users/jadenzaleski/projects/7">bible-translations project</a>. You’re welcome to open issues for feature ideas or bug reports.

<h3>Available Translations:</h3>

 * **AMP**
 * **ASV**
 * **AKJV**
 * **BRG**
 * **CSB**
 * **EHV**
 * **ESV**
 * **ESVUK**
 * **GNV**
 * **GW**
 * **ISV**
 * **JUB**
 * **KJV**
 * **KJ21**
 * **LEB**
 * **MEV**
 * **NASB**
 * **NASB1995**
 * **NET**
 * **NIV**
 * **NIVUK**
 * **NKJV**
 * **NLT**
 * **NLV**
 * **NMB\***
 * **NOG**
 * **NRSV**
 * **NRSVUE**
 * **WEB**
 * **YLT**
 * **RVA\*** 
> [!IMPORTANT]
> \* Both the **NMB** and **RVA** translations are not generated by the script since complete versions of them are not available on [Bible Gateway](https://www.biblegateway.com) yet. The [meaningless](https://github.com/daniel-tran/meaningless) package still works for those translations, just not the entire Bible.

If you would like more resources, I have found that the 
[Holy-Bible-XML-Format](https://github.com/Beblia/Holy-Bible-XML-Format) is a great repo if you are willing to use XML. 

# Disclaimer

The Bible text formatted by the script(s) in this repository is for educational, personal, non-commercial, and reference
purposes only.

Many of the Bible translations listed here are protected by copyright and may not be legally redistributed or used in
other projects without explicit permission from their respective copyright holders.

Bible text is retrieved via the [meaningless](https://github.com/daniel-tran/meaningless) package, which sources content
from [BibleGateway.com](https://www.biblegateway.com). Use of this content may be subject to BibleGateway's Terms of
Service and the individual licenses for each Bible translation. Some translations (such as KJV, ASV, YLT, and WEB) are
in the public domain and may be freely used. Others (e.g., ESV, NIV, NLT, NASB, etc.) are licensed, and require
permission for redistribution or certain uses.

You are solely responsible for ensuring you have the proper rights or licenses before using, distributing, or publishing
any of these translations.

If you fork this repository, you must maintain compliance with all applicable copyright laws and licensing requirements.
Forking does not grant you any additional rights to distribute or use copyrighted Bible translations beyond what is
explicitly permitted by their respective copyright holders.

This project does not claim ownership of any Bible text and is not affiliated with BibleGateway or any copyright holder.
