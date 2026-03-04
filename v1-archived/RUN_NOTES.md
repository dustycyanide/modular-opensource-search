# Run Notes

## Repositories indexed

- `repos/OCRmyPDF`
- `repos/requests`

## Commands executed

```bash
python3 capability_index.py --db ./data/capabilities.db init
python3 capability_index.py --db ./data/capabilities.db ingest --repo-path ./repos/OCRmyPDF
python3 capability_index.py --db ./data/capabilities.db ingest --repo-path ./repos/requests
python3 capability_index.py --db ./data/capabilities.db search --query "python ocr document pipeline" --k 5
python3 capability_index.py --db ./data/capabilities.db search --query "apache python database persistence" --k 5
```

## Example results snapshot

- OCR query returns `OCRmyPDF: OCR processing` as rank 1.
- Structured Apache + database query returns `requests: Database persistence` as rank 1.

## Known limitations

- Capability extraction is heuristic and can produce false positives.
- Semantic fallback uses synonym expansion, not dense vectors.
- No deep call-graph or cross-file dataflow validation yet.
