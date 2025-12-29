# Retriever Parser - Streamlit App

En Streamlit-app för att bearbeta textfiler från Retriever-databasen.

## Installation

1. Se till att du har Python 3.8 eller senare installerat
2. Installera dependencies:

```bash
pip install -r requirements.txt
```

## Användning

Kör appen med:

```bash
streamlit run retriever_parser.py
```

Appen öppnas i din webbläsare på `http://localhost:8501`

## Funktioner

- **Upload av flera filer**: Ladda upp en eller flera `.txt` filer samtidigt
- **Automatisk parsing**: Extraherar artikeldata (rubrik, tidning, datum, sida, text, länk)
- **Förhandsgranskning**: Se resultatet i en interaktiv tabell
- **Filtrering**: Sök i rubriker/text och filtrera på tidning
- **Export**: Ladda ner data som CSV eller Excel (.xlsx)

## Filformat

Applikationen förväntar sig textfiler i UTF-16 format från Retriever med följande struktur:

```
Linnéuniversitetet BIBSAM
Uttag [datum]

Nyheter:

[Rubrik]
[Tidning], [Datum]
Sida [Sidnummer]
Publicerat i print.

[Artikeltext]

© Copyright
Läs hela artikeln på
http://ret.nu/[ID]
========================================
```

## Skillnader från original Colab notebook

- **Webbaserat gränssnitt**: Ingen kod behöver köras manuellt
- **Filtrering och sökning**: Inbyggda verktyg för att utforska data
- **Statistik**: Visar antal artiklar, tidningar och datumspann
- **Bättre felhantering**: Tydliga felmeddelanden om något går fel
- **Radbrytningshantering**: Konverterar automatiskt Windows-format (CRLF) till Unix-format
- **Uppdaterade regex-mönster**: Fungerar med moderna Retriever-exportformat

## Baserat på

Original Colab notebook för Retriever-parsing

## Felsökning

**Problem: Får bara 1 artikel istället för många**
- Detta kan hända om filen har ett oväntat format
- Lösningen är redan inbyggd: appen normaliserar automatiskt radbrytningar

**Problem: Kan inte läsa filen**
- Kontrollera att filen är i UTF-16 format (standard för Retriever)
- Om filen är i UTF-8 kommer appen att varna men försöka läsa den ändå

**Teknisk bakgrund**
Originalversionen av koden skrevs för äldre Retriever-exportformat. Moderna exporter:
- Använder Windows-stil radbrytningar (`\r\n` istället för `\n`)
- Har "Alla artiklar är skyddade..." text före varje artikel-separator
- Dessa skillnader hanteras nu automatiskt av appen
