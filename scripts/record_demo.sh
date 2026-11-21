#!/bin/zsh
set -u
unsetopt BG_NICE

repo_dir=${0:A:h:h}
output_path=${1:-"$repo_dir/recordings/pixelpilot-healing.mov"}
record_seconds=${PP_RECORD_SECONDS:-120}
demo_pid=""
recorder_pid=""

stop_processes() {
  if [[ -n "$recorder_pid" ]] && kill -0 "$recorder_pid" 2>/dev/null; then
    kill -INT "$recorder_pid" 2>/dev/null || true
    wait "$recorder_pid" 2>/dev/null || true
  fi
  if [[ -n "$demo_pid" ]] && kill -0 "$demo_pid" 2>/dev/null; then
    kill -TERM "$demo_pid" 2>/dev/null || true
    wait "$demo_pid" 2>/dev/null || true
  fi
}

trap stop_processes EXIT INT TERM
cd "$repo_dir"
mkdir -p "${output_path:h}"

uv run --no-sync uvicorn demo_app.main:app --host 127.0.0.1 --port 8000 &
demo_pid=$!

for _attempt in {1..50}; do
  if curl --silent --fail --output /dev/null http://127.0.0.1:8000/; then
    break
  fi
  sleep 0.1
done

if ! curl --silent --fail --output /dev/null http://127.0.0.1:8000/; then
  print -- "demo app did not become ready on 127.0.0.1:8000" >&2
  exit 1
fi

screencapture -v -V"$record_seconds" -m -C -k "$output_path" &
recorder_pid=$!
sleep 1

run_one=0
run_two=0
uv run --no-sync pixelpilot run stories/checkout_expired_coupon.md \
  --url http://127.0.0.1:8000 --mutate || run_one=$?
uv run --no-sync pixelpilot run stories/checkout_expired_coupon.md \
  --url http://127.0.0.1:8000 --mutate || run_two=$?

stop_processes
trap - EXIT INT TERM

if (( run_one != 0 || run_two != 0 )); then
  exit 1
fi
