#!/usr/bin/env bash
# Push the demo API to a Hugging Face Space.
#
#   HF_TOKEN=hf_xxx ./server/deploy-space.sh <hf-username> [space-name]
#
# Afterwards set GROQ_API_KEY (and optionally OPENROUTER_API_KEY) in the Space's
# Settings > Variables and secrets. Do not put keys in this repo.
set -euo pipefail

USER_NAME="${1:?usage: deploy-space.sh <hf-username> [space-name]}"
SPACE_NAME="${2:-ai-review-api}"
: "${HF_TOKEN:?set HF_TOKEN to a Hugging Face write token}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# A Space needs its own README with the sdk frontmatter, which is why this stages a
# directory rather than pushing the repo as-is.
cat > "$STAGE/README.md" <<EOF
---
title: AI Review API
emoji: 🔍
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

Backend for the code review, test generation and locator repair demos on
https://priya123z.github.io

Source: https://github.com/Priya123z/ai-code-review
EOF

cp "$ROOT/server/Dockerfile" "$STAGE/Dockerfile"
mkdir -p "$STAGE/server"
cp -r "$ROOT/ai_review" "$STAGE/ai_review"
cp "$ROOT/server"/*.py "$ROOT/server/requirements.txt" "$STAGE/server/"
cp -r "$ROOT/server/samples" "$STAGE/server/samples"
find "$STAGE" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

cd "$STAGE"
git init -q
git checkout -q -b main
git add -A
git -c user.name="Priya Bhagoriya" -c user.email="prbhagoriya20@gmail.com" \
    commit -q -m "Deploy demo API"
git push -q --force \
    "https://${USER_NAME}:${HF_TOKEN}@huggingface.co/spaces/${USER_NAME}/${SPACE_NAME}" main

echo "Pushed to https://huggingface.co/spaces/${USER_NAME}/${SPACE_NAME}"
echo "API will be at https://${USER_NAME}-${SPACE_NAME}.hf.space"
echo
echo "Now set GROQ_API_KEY in the Space settings, then check:"
echo "  curl https://${USER_NAME}-${SPACE_NAME}.hf.space/api/health"
