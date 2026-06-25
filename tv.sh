#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" && -x "$SCRIPT_DIR/.venv/bin/python3" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
fi
if [[ -z "$PYTHON_BIN" ]]; then
	PYTHON_BIN="python3"
fi
PRINT_COMMANDS=false
PASSTHROUGH_ARGS=()

for arg in "$@"; do
	case "$arg" in
		--print-commands)
			PRINT_COMMANDS=true
			;;
		*)
			PASSTHROUGH_ARGS+=("$arg")
			;;
	esac
done

PLAYLISTS=(
	"All media|"
	"Comedy|-g comedy"
	"Action|-g action"
	"Animation|-g animation"
	"Sci-Fi|-g sci-fi"
	"Fantasy|-g fantasy"
	"Star Wars|-f star-wars"
	"Star Trek|-f star-trek"
	"Marvel|-f marvel"
	"DC|-f dc"
	"Comfort Shows|-g comfort"
)

quote_command() {
	printf '%q' "$1"
	shift
	for arg in "$@"; do
		printf ' %q' "$arg"
	done
	printf '\n'
}

run_playlist() {
	local name="$1"
	local filter_args_text="$2"
	local filter_args=()
	local status=0

	if [[ -n "$filter_args_text" ]]; then
		read -r -a filter_args <<< "$filter_args_text"
	fi

	local command=("$PYTHON_BIN" "$SCRIPT_DIR/src/main.py" tvstation "${filter_args[@]}" "${PASSTHROUGH_ARGS[@]}")

	if [[ "$PRINT_COMMANDS" == true ]]; then
		quote_command "${command[@]}"
		return 0
	fi

	echo "Updating ${name} playlist..."
	"${command[@]}"
	status=$?

	if [[ $status -ne 0 ]]; then
		echo "ERROR: ${name} playlist update failed with exit code ${status}" >&2
	fi

	return "$status"
}

failures=0
for playlist in "${PLAYLISTS[@]}"; do
	name="${playlist%%|*}"
	filter_args="${playlist#*|}"

	if ! run_playlist "$name" "$filter_args"; then
		failures=$((failures + 1))
	fi
done

if [[ $failures -gt 0 ]]; then
	echo "Completed with ${failures} playlist update failure(s)." >&2
	exit 1
fi
