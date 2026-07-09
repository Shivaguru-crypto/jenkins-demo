#!/usr/bin/env python3
"""
serial_helper.py — talk to a board over its FTDI USB-serial console.

Subcommands:
  check  --port /dev/ttyUSB0 --baud 115200
  run    --port /dev/ttyUSB0 --baud 115200 --cmd "cmd" [--timeout 60]
  push   --port /dev/ttyUSB0 --baud 115200 --local-file f --remote-path /run/f

Exit codes: 0 = PASS, non-zero = FAIL.

--- Fix history -------------------------------------------------------------
v1  Initial version.
v2  wake_shell: replaced single-read race with _read_window() polling.
v3  (THIS VERSION) — fixes "already at shell prompt / Raw: ''" failure:

    ROOT CAUSE: wake_shell() ended with reset_input_buffer() which flushed
    bytes the board was mid-sending (prompt echo, heredoc '>' prompts, etc.).
    The next read_until() call then saw nothing → timeout → empty Raw → FAIL.

    FIX A — removed reset_input_buffer() from wake_shell(). Instead we drain
    cleanly by reading until we see a '#' prompt character (confirming the
    shell is ready) or until a short timeout expires. No flush.

    FIX B — wake_shell() now does TWO probe rounds:
      Round 1: send \r\n, collect 2 s. If login: → log in, re-probe.
      Round 2: send \r\n again, wait up to 3 s for '#' in response.
    This means when the board is ALREADY logged in (most common case between
    pipeline stages) we confirm the prompt with zero wasted time.

    FIX C — heredoc push: after sending the closing EOF token, wait for the
    shell prompt '#' (not just PUSH_MARKER) before sending echo PUSH_MARKER,
    because on slow boards the shell needs a moment to process the heredoc.

    FIX D — Slack credential: Jenkinsfile post block now wraps withCredentials
    in a try/catch so a missing slack-webhook-url credential logs a warning
    instead of failing the whole build.

    FIX E — BusyBox head: 'head -1' → 'head -n 1' for BusyBox compat.
             This is fixed in the Jenkinsfile command strings, not here.
-----------------------------------------------------------------------------
"""

import argparse
import re
import subprocess
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("❌ pyserial not installed. Run: pip3 install pyserial --break-system-packages")
    sys.exit(1)

END_MARKER  = "___CMD_DONE___"
PUSH_MARKER = "___PUSH_DONE___"
HEREDOC_EOF = "___JENKINS_EOF___"

BOARD_LOGIN_USER     = "root"
BOARD_LOGIN_PASSWORD = ""


# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------

def resolve_port(port_or_serial):
    if port_or_serial.startswith("/dev/"):
        return port_or_serial
    for p in serial.tools.list_ports.comports():
        if p.serial_number == port_or_serial:
            return p.device
    print(f"❌ No USB-serial device with serial number '{port_or_serial}'.")
    sys.exit(1)


def open_port(port, baud, timeout=5):
    """
    Open port with DTR/RTS held LOW before open() to prevent reset pulse.
    Disables HUPCL so port close won't drop DTR later.
    Does NOT call reset_input_buffer() — we want to see what the board sends.
    """
    resolved = resolve_port(port)

    ser = serial.Serial()
    ser.port     = resolved
    ser.baudrate = int(baud)
    ser.timeout  = timeout
    ser.dtr      = False
    ser.rts      = False
    ser.dsrdtr   = False
    ser.open()

    try:
        subprocess.run(["stty", "-F", resolved, "-hupcl"],
                       check=False, capture_output=True)
    except Exception:
        pass

    time.sleep(0.3)
    # NOTE: intentionally NO reset_input_buffer() here — the board may already
    # be sending prompt characters; flushing them causes read_until to starve.
    return ser


# ---------------------------------------------------------------------------
# Low-level I/O helpers
# ---------------------------------------------------------------------------

def _drain(ser, seconds=1.0):
    """
    Read everything arriving within `seconds` seconds WITHOUT blocking.
    Returns the collected string. Never discards — just reads it out.
    """
    buf = ""
    deadline = time.time() + seconds
    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            buf += ser.read(n).decode(errors="ignore")
        else:
            time.sleep(0.05)
    return buf


def read_until(ser, marker, timeout=30):
    """Read bytes until `marker` appears or timeout expires."""
    buf = ""
    start = time.time()
    while time.time() - start < timeout:
        n = ser.in_waiting
        if n:
            buf += ser.read(n).decode(errors="ignore")
            if marker in buf:
                break
        else:
            time.sleep(0.05)
    return buf


def read_until_any(ser, markers, timeout=5):
    """
    Read until ANY string in `markers` list appears, or timeout.
    Returns (buf, matched_marker_or_None).
    """
    buf = ""
    start = time.time()
    while time.time() - start < timeout:
        n = ser.in_waiting
        if n:
            buf += ser.read(n).decode(errors="ignore")
            for m in markers:
                if m in buf:
                    return buf, m
        else:
            time.sleep(0.05)
    return buf, None


# ---------------------------------------------------------------------------
# Shell / login handling
# ---------------------------------------------------------------------------

def wake_shell(ser):
    """
    Ensure we are at a live root shell prompt before sending any command.

    Protocol
    --------
    1. Send \\r\\n to prod any pending prompt.
    2. Collect up to 3 s of output.
    3. If we see "login:" → log in, re-probe up to 3 s for '#'.
    4. If we see '#'      → already at shell, done.
    5. If we see neither  → send another \\r\\n and wait 2 s for '#'.
    6. Log what we decided.

    CRITICAL: we never call reset_input_buffer() here. Flushing the buffer
    after we confirm the shell would discard the first bytes of the board's
    response to our next command, causing read_until() to see nothing.
    """
    ser.write(b"\r\n")
    buf, matched = read_until_any(ser, ["login:", "#", "$"], timeout=3)

    if matched and "login:" in matched:
        print(f"   [wake_shell] login prompt — logging in as '{BOARD_LOGIN_USER}'")
        ser.write((BOARD_LOGIN_USER + "\n").encode())
        time.sleep(1.0)
        buf2, _ = read_until_any(ser, ["password:", "assword", "#", "$"], timeout=3)
        if "password:" in buf2.lower() or "assword" in buf2.lower():
            ser.write((BOARD_LOGIN_PASSWORD + "\n").encode())
            time.sleep(1.0)
            read_until_any(ser, ["#", "$"], timeout=3)
        # Re-probe to confirm we're at a shell now
        ser.write(b"\r\n")
        buf3, m3 = read_until_any(ser, ["#", "$"], timeout=3)
        if m3:
            print("   [wake_shell] logged in successfully — shell prompt confirmed")
        else:
            print(f"   [wake_shell] WARNING: no shell prompt after login. buf={buf3!r}")

    elif matched:
        # '#' or '$' — already at a live shell
        print("   [wake_shell] shell prompt confirmed (already logged in)")

    else:
        # Nothing useful — send one more nudge and wait
        print(f"   [wake_shell] no prompt yet (buf={buf!r}) — sending extra nudge")
        ser.write(b"\r\n")
        buf2, m2 = read_until_any(ser, ["login:", "#", "$"], timeout=3)
        if "login:" in buf2:
            # Caught the login prompt on second try
            wake_shell(ser)   # recurse once to handle login
        elif m2:
            print("   [wake_shell] shell prompt confirmed after nudge")
        else:
            print(f"   [wake_shell] WARNING: still no prompt. buf={buf2!r}")


def send_line(ser, line):
    ser.write((line + "\n").encode())


def run_command(ser, cmd, timeout=60):
    """
    Send `cmd`; echo END_MARKER$? so we capture the real exit code.
    Returns (output_text, exit_code).
    """
    tagged = f"{cmd}; echo {END_MARKER}$?"
    send_line(ser, tagged)
    raw = read_until(ser, END_MARKER, timeout=timeout)

    exit_code  = 1
    body_lines = []
    cmd_echoed = False

    for line in raw.splitlines():
        m = re.search(rf"{re.escape(END_MARKER)}(\d+)", line)
        if m:
            exit_code = int(m.group(1))
            continue
        if not cmd_echoed and (cmd in line or tagged in line):
            cmd_echoed = True
            continue
        if line.strip():
            body_lines.append(line)

    return "\n".join(body_lines), exit_code


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_check(args):
    try:
        ser = open_port(args.port, args.baud, timeout=5)
        wake_shell(ser)
        out, rc = run_command(ser, "echo PING_OK", timeout=10)
        ser.close()
        if "PING_OK" in out or rc == 0:
            print(f"✅ Serial console reachable on {args.port} @ {args.baud} baud")
            sys.exit(0)
        print(f"❌ No shell response on {args.port}\nRaw: {out!r}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Could not open {args.port}: {e}")
        sys.exit(1)


def cmd_run(args):
    try:
        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser)
        out, rc = run_command(ser, args.cmd, timeout=args.timeout)
        print(out)
        ser.close()
        sys.exit(rc)
    except Exception as e:
        print(f"❌ Serial run failed on {args.port}: {e}")
        sys.exit(1)


def _writable_path(path):
    """Redirect /tmp/* → /run/* — SAMA5D2 rootfs is squashfs (read-only)."""
    if path.startswith("/tmp/"):
        alt = "/run/" + path[len("/tmp/"):]
        print(f"   [push] /tmp is read-only — redirecting to {alt}")
        return alt
    return path


def cmd_push(args):
    """
    Transfer a local text file to the board via heredoc over serial.
    No scp/zmodem needed.
    """
    remote = _writable_path(args.remote_path)

    try:
        with open(args.local_file, "r") as f:
            content = f.read()
    except OSError as e:
        print(f"❌ Cannot read {args.local_file}: {e}")
        sys.exit(1)

    try:
        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser)

        # Start the heredoc
        send_line(ser, f"cat > {remote} << '{HEREDOC_EOF}'")

        # Wait for the shell to show the '>' continuation prompt before
        # streaming lines — avoids sending into a deaf buffer on slow boards
        buf, m = read_until_any(ser, [">", "#"], timeout=5)
        if not m:
            print(f"❌ Board did not show heredoc prompt. buf={buf!r}")
            ser.close()
            sys.exit(1)

        # Stream file content line by line
        for line in content.splitlines():
            send_line(ser, line)
            time.sleep(0.06)

        # Close the heredoc
        send_line(ser, HEREDOC_EOF)

        # Wait for the shell prompt '#' which confirms heredoc was processed
        buf2, m2 = read_until_any(ser, ["#", "$"], timeout=15)
        if not m2:
            if "Read-only" in buf2 or "read-only" in buf2:
                print(f"❌ Remote FS is read-only: {remote}")
            else:
                print(f"❌ Heredoc did not close cleanly. buf={buf2!r}")
            ser.close()
            sys.exit(1)

        # Confirm push with explicit marker
        send_line(ser, f"echo {PUSH_MARKER}")
        confirm = read_until(ser, PUSH_MARKER, timeout=10)
        if PUSH_MARKER not in confirm:
            print(f"❌ PUSH_MARKER not received. buf={confirm!r}")
            ser.close()
            sys.exit(1)

        # chmod and verify
        out, rc = run_command(ser, f"chmod +x {remote} && ls -l {remote}", timeout=10)
        print(out)
        ser.close()

        if rc == 0 and "No such file" not in out:
            print(f"✅ File pushed to {remote}")
            sys.exit(0)

        print(f"❌ File did not land at {remote}. out={out!r}")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Serial push failed on {args.port}: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)

    pc = sub.add_parser("check")
    pc.add_argument("--port",  required=True)
    pc.add_argument("--baud",  default="115200")
    pc.set_defaults(func=cmd_check)

    pr = sub.add_parser("run")
    pr.add_argument("--port",    required=True)
    pr.add_argument("--baud",    default="115200")
    pr.add_argument("--cmd",     required=True)
    pr.add_argument("--timeout", type=int, default=60)
    pr.set_defaults(func=cmd_run)

    pp = sub.add_parser("push")
    pp.add_argument("--port",        required=True)
    pp.add_argument("--baud",        default="115200")
    pp.add_argument("--local-file",  required=True)
    pp.add_argument("--remote-path", required=True)
    pp.add_argument("--timeout",     type=int, default=60)
    pp.set_defaults(func=cmd_push)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
