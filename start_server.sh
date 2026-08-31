#!/usr/bin/env bash
# Persistent launcher. Execs into the Flask app.
cd "$(dirname "$0")"
exec python3 -m app.server