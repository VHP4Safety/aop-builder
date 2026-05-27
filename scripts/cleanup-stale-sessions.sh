#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

MAX_AGE_MINUTES=15
APPLY_CHANGES=false
SHOW_QUEUES=true

usage() {
  cat <<'EOF'
Usage: scripts/cleanup-stale-sessions.sh [options]

Find stale CER sessions that are stuck in `waiting` or `extracting`.
Dry-run is the default behavior.

Options:
  --apply                 Mark matching sessions as canceled and append a canceled log entry.
  --max-age-minutes N     Treat sessions older than N minutes as stale. Default: 15
  --no-queue-report       Skip the RabbitMQ queue summary.
  --help                  Show this help text.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY_CHANGES=true
      shift
      ;;
    --max-age-minutes)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --max-age-minutes" >&2
        exit 1
      fi
      MAX_AGE_MINUTES="$2"
      shift 2
      ;;
    --no-queue-report)
      SHOW_QUEUES=false
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! [[ "$MAX_AGE_MINUTES" =~ ^[0-9]+$ ]]; then
  echo "--max-age-minutes must be a positive integer." >&2
  exit 1
fi

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgres_db}"
MONGO_CONTAINER="${MONGO_CONTAINER:-mongo_db}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-rabbitmq_broker}"
POSTGRES_USER="${POSTGRES_USER:-myuser}"
POSTGRES_DB="${POSTGRES_DB:-mydatabase}"
MONGO_DB="${MONGO_DB:-collection_storage}"

SQL_QUERY="
select id, status, to_char(updated_at at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') as updated_at_utc, title
from cer_sessions
where status in ('waiting', 'extracting')
order by updated_at asc;
"

echo "Scanning for stale sessions older than ${MAX_AGE_MINUTES} minute(s)..."

SESSION_ROWS="$(
  docker exec "$POSTGRES_CONTAINER" \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -At -F $'\t' -c "$SQL_QUERY"
)"

if [[ "$SHOW_QUEUES" == true ]]; then
  echo
  echo "Current RabbitMQ queues:"
  docker exec "$RABBITMQ_CONTAINER" rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers
fi

echo
if [[ -z "$SESSION_ROWS" ]]; then
  echo "No stale waiting/extracting sessions found."
  exit 0
fi

STALE_CANDIDATES=""
NOW_EPOCH="$(date -u +%s)"
MAX_AGE_SECONDS=$((MAX_AGE_MINUTES * 60))

while IFS=$'\t' read -r session_id status updated_at title; do
  if [[ -z "$session_id" ]]; then
    continue
  fi

  reference_timestamp="$updated_at"

  if [[ "$status" == "extracting" ]]; then
    telemetry_updated_at="$(
      docker exec "$MONGO_CONTAINER" \
        mongosh --quiet "$MONGO_DB" --eval "
const doc = db.session_telemetry.findOne(
  { session_id: ${session_id} },
  { _id: 0, updated_at: 1 }
);
if (doc && doc.updated_at) {
  print(doc.updated_at.toISOString());
}
"
    )"

    if [[ -n "$telemetry_updated_at" ]]; then
      reference_timestamp="$telemetry_updated_at"
    fi
  fi

  reference_epoch="$(date -u -d "$reference_timestamp" +%s)"
  age_seconds=$((NOW_EPOCH - reference_epoch))

  if (( age_seconds >= MAX_AGE_SECONDS )); then
    STALE_CANDIDATES+="${session_id}"$'\t'"${status}"$'\t'"${reference_timestamp}"$'\t'"${title}"$'\n'
  fi
done <<< "$SESSION_ROWS"

STALE_CANDIDATES="${STALE_CANDIDATES%$'\n'}"

if [[ -z "$STALE_CANDIDATES" ]]; then
  echo "No stale waiting/extracting sessions found."
  exit 0
fi

echo "Stale session candidates:"
printf '  %-6s %-12s %-22s %s\n' "ID" "STATUS" "UPDATED_AT_UTC" "TITLE"
while IFS=$'\t' read -r session_id status updated_at title; do
  printf '  %-6s %-12s %-22s %s\n' "$session_id" "$status" "$updated_at" "$title"
done <<< "$STALE_CANDIDATES"

if [[ "$APPLY_CHANGES" != true ]]; then
  echo
  echo "Dry-run only. Re-run with --apply to mark these sessions as canceled."
  exit 0
fi

mapfile -t SESSION_IDS < <(printf '%s\n' "$STALE_CANDIDATES" | cut -f1)
IDS_CSV="$(printf '%s,' "${SESSION_IDS[@]}")"
IDS_CSV="${IDS_CSV%,}"
ID_ARRAY="[${IDS_CSV}]"

echo
echo "Marking stale sessions as canceled in Postgres..."
docker exec "$POSTGRES_CONTAINER" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
begin;
update cer_sessions
set status = 'canceled',
    updated_at = now()
where id in (${IDS_CSV});

insert into cer_session_logs (session_id, timestamp, status)
select id, now(), 'canceled'
from cer_sessions
where id in (${IDS_CSV});
commit;
"

echo
echo "Updating telemetry phase in MongoDB..."
docker exec "$MONGO_CONTAINER" \
  mongosh --quiet "$MONGO_DB" --eval "
db.session_telemetry.updateMany(
  { session_id: { \$in: ${ID_ARRAY} } },
  {
    \$set: {
      phase: 'canceled',
      updated_at: new Date(),
      last_message: 'Marked canceled by cleanup-stale-sessions.sh',
      last_error: 'Session exceeded stale threshold while waiting for worker progress'
    }
  }
)
"

echo
echo "Cleanup complete for session ID(s): ${IDS_CSV}"
