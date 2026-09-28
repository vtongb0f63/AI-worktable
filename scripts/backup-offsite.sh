#!/usr/bin/env sh
set -eu
backup_file=$(python3 scripts/backup.py)
restic backup "$backup_file"
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6
rm -f "$backup_file"
