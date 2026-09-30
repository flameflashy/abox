python3 - <<'PY'
from pathlib import Path
import re
image = Path('.lab/embeddings/llama-image.txt').read_text().strip()
if not re.fullmatch(r'ghcr\.io/ggml-org/llama\.cpp@sha256:[0-9a-f]{64}', image):
    raise SystemExit('Expected the llama.cpp digest saved by the local run')
template = Path('docs/examples/embeddings-sidecar.yaml.template').read_text()
Path('.lab/embeddings/sidecar.yaml').write_text(template.replace('__LLAMA_IMAGE__', image))
PY
