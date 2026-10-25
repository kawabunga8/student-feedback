#!/bin/bash
# Start / stop the feedback app with as little compute as possible. Thin wrapper over ../rcs-launcher/rcs.sh.
#
#   ./start.sh                          light: Ollama + this app only (no Docker, no database, no Course Hub)
#   ./start.sh --with-course-hub        also Colima, the shared database and Course Hub (live courses + class lists)
#   ./start.sh stop                     stop the app, plus Ollama if nothing else is using it
#   ./start.sh stop --with-course-hub   ...and Course Hub, the database and Colima if this started them
#
# Light mode uses roughly the model's memory (~9 GB while it is loaded) and nothing else. Without Course Hub the
# page shows an orange note and uses its saved course list; class lists are unavailable, so you type names.

RCS="$HOME/Repos-folder/rcs-launcher/rcs.sh"
[ -x "$RCS" ] || { echo "Missing $RCS"; exit 1; }

MODE=start; HUB=0
for a in "$@"; do
  case "$a" in
    stop) MODE=stop ;;
    --with-course-hub) HUB=1 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a (try --help)"; exit 2 ;;
  esac
done

SERVICES="feedback"; [ "$HUB" = 1 ] && SERVICES="feedback course-hub"
"$RCS" "$MODE" $SERVICES || exit $?

if [ "$MODE" = start ]; then
  echo; echo "Open http://127.0.0.1:8765"
  [ "$HUB" = 0 ] && echo "(light mode: no Course Hub. Add --with-course-hub for live courses and class lists.)"
  echo "Stop with: ./start.sh stop$([ "$HUB" = 1 ] && echo ' --with-course-hub')"
fi
