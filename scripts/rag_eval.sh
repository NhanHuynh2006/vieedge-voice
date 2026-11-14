#!/usr/bin/env bash
# RAG answer quality: typed questions and Zipformer-transcribed questions, with retrieval (current template/budget), judged by the teacher.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
PY="env -u PYTHONPATH $ROOT/.venv/bin/python"
M=llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf
TAG=${1:-T}
pkill -x llama-server 2>/dev/null; sleep 2
(cd bench && $PY eval_rag_qa.py $M --max-chars 240 --docs 1 --tag $TAG)
(setsid nohup scripts/run_teacher.sh > results/logs/teacher-server.log 2>&1 &)
for i in $(seq 100); do curl -sf localhost:8090/health >/dev/null && break; sleep 3; done
$PY bench/judge.py results/raw/answers_RAGCLEAN${TAG}_qwen3.5-0.8b-vi-voice-Q4_K_M.jsonl results/raw/answers_RAGZIP${TAG}_qwen3.5-0.8b-vi-voice-Q4_K_M.jsonl
pkill -x llama-server
echo RAG-EVAL-DONE
