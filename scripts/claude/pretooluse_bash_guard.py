#!/usr/bin/env python3
"""Claude Code PreToolUse guard for Bash and Monitor commands.

Reads the hook payload on stdin. Exit 0 allows (stdout may carry an "ask"
decision), exit 2 blocks with a message on stderr. Any unexpected failure,
including a failed import or the watchdog firing, exits 2 with a fixed
message that never repeats the tool input. Launched by run_hook.sh.
"""
import json
import signal
import sys

WATCHDOG_SECONDS = 10  # below the hook timeout in .claude/settings.json (30 s)
INTERNAL_ERROR = "ttr-hook: internal error, blocked"


def _expired(signum, frame):
    raise TimeoutError


def main() -> int:
    signal.signal(signal.SIGALRM, _expired)
    signal.alarm(WATCHDOG_SECONDS)
    import _policy

    payload = json.loads(sys.stdin.read())
    return _policy.emit(_policy.bash_decision(payload))


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        code = None
    if code is None:
        sys.stderr.write(INTERNAL_ERROR + "\n")
        code = 2
    sys.exit(code)
