#!/usr/bin/env bash
# Fetch the CORD v2 receipt dataset (CC-BY-4.0) from Hugging Face. Not committed to the repo.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/cord
base="https://huggingface.co/datasets/naver-clova-ix/cord-v2/resolve/main/data"
for f in test-00000-of-00001-9c204eb3f4e11791 validation-00000-of-00001-cc3c5779fe22e8ca; do
  [ -s "data/cord/${f%%-*}.parquet" ] || curl -fL --retry 4 -o "data/cord/${f%%-*}.parquet" "$base/$f.parquet"
done
ls -la data/cord
