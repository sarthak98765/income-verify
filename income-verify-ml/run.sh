set -e
CONCURRENCY=$(python -c "import config; print(config.WORKER_CONCURRENCY)")
PORT=$(python -c "import config; print(config.ML_PORT)")
HEALTH_PORT="$PORT" python worker.py &
for _ in $(seq 2 "$CONCURRENCY"); do
  HEALTH_PORT=0 python worker.py &
done
wait
