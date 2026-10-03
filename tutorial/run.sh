#!/usr/bin/env bash
# Regenerate all tutorial outputs for every backend.
# Run from the repository root:  bash tutorial/run.sh
#
# Requires:
#   brew install tesseract poppler
#   pip install -r requirements.txt
#   ANTHROPIC_API_KEY set in .env (for the Claude backend only)

set -euo pipefail

IMAGES=(
  tests/fixtures/carthay-circle-premiere.jpg
  tests/fixtures/carthay-circle-postcard-back.png
  tests/fixtures/graumans-chinese-theatre.jpg
  tests/fixtures/inside-facts-1930-cover.jpg
  tests/fixtures/inside-facts-1930-page-six.jpg
  tests/fixtures/kar-mi-troupe-poster.jpg
)

PDFS=(
  tests/fixtures/king-of-kings-souvenir-1927.pdf
)

mkdir -p tutorial/output/{claude,tesseract,tesseract-auto,easyocr,paddle,marker,auto-local}

echo "==> Claude (gold standard — requires ANTHROPIC_API_KEY)"
for img in "${IMAGES[@]}"; do
  stem=$(basename "${img%.*}")
  echo "  $stem"
  python scripts/ocr_claude.py "$img" > "tutorial/output/claude/${stem}.md"
done
for pdf in "${PDFS[@]}"; do
  stem=$(basename "$pdf" .pdf)
  echo "  $stem (PDF)"
  python scripts/ocr_claude.py "$pdf" > "tutorial/output/claude/${stem}.md"
done

echo
echo "==> Tesseract (default contrast, default PSM)"
for img in "${IMAGES[@]}"; do
  stem=$(basename "${img%.*}")
  echo "  $stem"
  python scripts/ocr_tesseract.py "$img" > "tutorial/output/tesseract/${stem}.md"
done
for pdf in "${PDFS[@]}"; do
  stem=$(basename "$pdf" .pdf)
  echo "  $stem (PDF)"
  python scripts/ocr_tesseract.py "$pdf" > "tutorial/output/tesseract/${stem}.md"
done

echo
echo "==> Tesseract (auto-configured)"
for img in "${IMAGES[@]}"; do
  stem=$(basename "${img%.*}")
  echo "  $stem"
  python scripts/ocr_tesseract.py "$img" --auto > "tutorial/output/tesseract-auto/${stem}.md"
done
for pdf in "${PDFS[@]}"; do
  stem=$(basename "$pdf" .pdf)
  echo "  $stem (PDF)"
  python scripts/ocr_tesseract.py "$pdf" --auto > "tutorial/output/tesseract-auto/${stem}.md"
done

echo
echo "==> EasyOCR (first run downloads ~300 MB of model weights)"
echo "    Note: EasyOCR does not support PDFs — skipping ${PDFS[*]}"
for img in "${IMAGES[@]}"; do
  stem=$(basename "${img%.*}")
  echo "  $stem"
  python scripts/ocr_easyocr.py "$img" > "tutorial/output/easyocr/${stem}.md"
done

echo
echo "==> PaddleOCR (first run downloads ~100 MB of model weights)"
echo "    Note: PaddleOCR does not support PDFs — skipping ${PDFS[*]}"
for img in "${IMAGES[@]}"; do
  stem=$(basename "${img%.*}")
  echo "  $stem"
  python scripts/ocr_paddle.py "$img" > "tutorial/output/paddle/${stem}.md"
done

echo
echo "==> Marker (first run downloads ~500 MB–1 GB of Surya model weights)"
for img in "${IMAGES[@]}"; do
  stem=$(basename "${img%.*}")
  echo "  $stem"
  python scripts/ocr_marker.py "$img" > "tutorial/output/marker/${stem}.md"
done
for pdf in "${PDFS[@]}"; do
  stem=$(basename "$pdf" .pdf)
  echo "  $stem (PDF)"
  python scripts/ocr_marker.py "$pdf" > "tutorial/output/marker/${stem}.md"
done

echo
echo "==> auto-local (routes: images → paddle/easyocr, PDFs → tesseract-auto)"
for img in "${IMAGES[@]}"; do
  stem=$(basename "${img%.*}")
  echo "  $stem"
  python scripts/ocr_auto_local.py "$img" > "tutorial/output/auto-local/${stem}.md"
done
for pdf in "${PDFS[@]}"; do
  stem=$(basename "$pdf" .pdf)
  echo "  $stem (PDF)"
  python scripts/ocr_auto_local.py "$pdf" > "tutorial/output/auto-local/${stem}.md"
done

echo
echo "Done. Outputs written to tutorial/output/."
