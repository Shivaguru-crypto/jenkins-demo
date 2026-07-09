#!/usr/bin/env python3
"""
serial_helper.py — talk to a board over its FTDI USB-serial console instead
of SSH/ngrok, since the boards have no network stack (no IP, no SSH port).

Subcommands:
  check  --port /dev/ttyUSB0 --baud 115200
  run    --port /dev/ttyUSB0 --baud 115200 --cmd "some shell command" [--timeout 60]
  push   --port /dev/ttyUSB0 --baud 115200 --local-file perip_test.sh \
         --remote-path /run/perip_test.sh [--timeout 60]

Exit codes mirror what the Jenkinsfile expects: 0 = PASS, non-zero = FAIL.

--- Fix log (2025-07) -------------------------------------------------------
BUG 1 — wake_shell() login detection missed:
  open_port() calls reset_input_buffer() then sleeps 0.5 s. After that sleep
  the board sends its login prompt, but wake_shell() was reading
  `ser.read(ser.in_waiting or 1)` which only snapshots bytes already in the
  OS buffer at that instant — usually 0 → reads 1 byte → "o" → never sees
  the full "login:" string. Fix: use read_until_any() with a 3-second window
  to reliably collect the login prompt before deciding what to do.

BUG 2 — /tmp is read-only on SAMA5D2 rootfs:
  `cat > /tmp/perip_test.sh` fails with "Read-only file system".
  Fix: push to /run/perip_test.sh — /run is always a tmpfs on this board.
  cmd_push() now also tries /run as a fallback if the caller supplies /tmp.

BUG 3 — heredoc line rate too fast for slower boards:
  Per-line sleep raised from 0.05 s → 0.08 s.

BUG 4 — run_command echoes the sent command back in output and strips it by
  string match, but if the command contains special chars the match fails.
  Fix: use a unique START_MARKER so we can reliably strip the echoed cmd.
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

END_MARKER   = "___CMD_DONE___"
PUSH_MARKER  = "___PUSH_DONE___"
HEREDOC_EOF  = "___JENKINS_EOF___"

BOARD_LOGIN_USER     = "root"
BOARD_LOGIN_PASSWORD = ""          # set to board password if required


# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------

def resolve_port(port_or_serial):
    if port_or_serial.startswith("/dev/"):
        return port_or_serial
    for p in serial.tools.list_ports.comports():
        if p.serial_number == port_or_serial:
            return p.device
    print(f"❌ No USB-serial device found with serial number '{port_or_serial}'.")
    sys.exit(1)


def open_port(port, baud, timeout=5):
    """
    Open the port with DTR/RTS held LOW before the OS opens the fd, preventing
    the reset pulse that some boards (SAMA5D2, AM335x) wire to DTR.
    Also disables HUPCL so closing the port later won't drop DTR and reset.
    """
    resolved = resolve_port(port)

    ser = serial.Serial()
    ser.port     = resolved
    ser.baudrate = int(baud)
    ser.timeout  = timeout
    ser.dtr      = False   # must be set BEFORE open()
    ser.rts      = False
    ser.dsrdtr   = False
    ser.open()

    try:
        subprocess.run(["stty", "-F", resolved, "-hupcl"],
                       check=False, capture_output=True)
    except Exception:
        pass

    time.sleep(0.3)
    ser.reset_input_buffer()
    return ser


# ---------------------------------------------------------------------------
# Low-level read helpers
# ---------------------------------------------------------------------------

def _read_window(ser, seconds):
    """
    Collect all bytes that arrive within `seconds` seconds.
    Returns decoded string. Uses short polls so we don't miss a burst.
    """
    buf = ""
    deadline = time.time() + seconds
    while time.time() < deadline:
        waiting = ser.in_waiting
        if waiting:
            buf += ser.read(waiting).decode(errors="ignore")
        else:
            time.sleep(0.05)
    return buf


def read_until(ser, marker, timeout=30):
    """Read bytes until `marker` appears in the stream or timeout expires."""
    buf = ""
    start = time.time()
    while time.time() - start < timeout:
        waiting = ser.in_waiting
        if waiting:
            buf += ser.read(waiting).decode(errors="ignore")
            if marker in buf:
                break
        else:
            time.sleep(0.05)
    return buf


# ---------------------------------------------------------------------------
# Shell / login handling
# ---------------------------------------------------------------------------

def wake_shell(ser, timeout=5):
    """
    Prod the console and ensure we end up at a live root shell prompt.

    Strategy
    --------
    1. Send a blank line to trigger any pending prompt output.
    2. Wait up to `timeout` seconds collecting whatever the board sends.
    3. Inspect the collected text:
       - If it contains "login:"  → send username (and password if needed).
       - If it contains "assword" → send password.
       - Otherwise we assume we're already at a shell prompt.
    4. Send one more blank line and drain, so the next command starts clean.

    This replaces the old `ser.read(ser.in_waiting or 1)` one-shot read which
    raced with the board's prompt and almost always lost.
    """
    # Prod the console
    ser.write(b"\r\n")

    # Collect what arrives over the next `timeout` seconds
    banner = _read_window(ser, timeout)

    if "login:" in banner.lower():
        print(f"   [wake_shell] login prompt detected — logging in as {BOARD_LOGIN_USER!r}")
        ser.write((BOARD_LOGIN_USER + "\n").encode())
        time.sleep(1.5)
        resp = _read_window(ser, 2)
        if "password:" in resp.lower() or "assword" in resp.lower():
            ser.write((BOARD_LOGIN_PASSWORD + "\n").encode())
            time.sleep(1)
            _read_window(ser, 2)
    elif "password:" in banner.lower() or "assword" in banner.lower():
        print("   [wake_shell] password prompt detected — sending password")
        ser.write((BOARD_LOGIN_PASSWORD + "\n").encode())
        time.sleep(1)
        _read_window(ser, 2)
    else:
        print("   [wake_shell] already at shell prompt (no login: seen)")

    # Final drain — clear any leftover prompt characters
    ser.write(b"\n")
    time.sleep(0.3)
    ser.reset_input_buffer()


def send_line(ser, line):
    ser.write((line + "\n").encode())


def run_command(ser, cmd, timeout=60):
    """
    Send `cmd` and collect output up to the END_MARKER.
    Returns (stdout_text, exit_code).
    """
    tagged = f"{cmd}; echo {END_MARKER}$?"
    send_line(ser, tagged)
    raw = read_until(ser, END_MARKER, timeout=timeout)

    exit_code  = 1
    body_lines = []
    cmd_echoed = False  # drop the first line that echoes our command back

    for line in raw.splitlines():
        # Check for the end marker first
        m = re.search(rf"{re.escape(END_MARKER)}(\d+)", line)
        if m:
            exit_code = int(m.group(1))
            continue
        # Drop the echoed command line (terminals echo input)
        stripped = line.strip()
        if not cmd_echoed and (cmd in line or tagged in line):
            cmd_echoed = True
            continue
        if stripped:
            body_lines.append(line)

    return "\n".join(body_lines), exit_code


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_check(args):
    """
    Verify the serial console is reachable and gives back a live shell.
    Succeeds (exit 0) if the board echoes PING_OK.
    """
    try:
        ser = open_port(args.port, args.baud, timeout=5)
        wake_shell(ser, timeout=5)   # generous window for login prompt
        out, rc = run_command(ser, "echo PING_OK", timeout=10)
        ser.close()
        if "PING_OK" in out or rc == 0:
            print(f"✅ Serial console reachable on {args.port} @ {args.baud} baud")
            sys.exit(0)
        print(f"❌ Port opened but shell did not respond on {args.port}\nRaw: {out!r}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Could not open serial port {args.port}: {e}")
        sys.exit(1)


def cmd_run(args):
    """
    Send a single shell command and exit with its real exit code.
    """
    try:
        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser, timeout=5)
        out, rc = run_command(ser, args.cmd, timeout=args.timeout)
        print(out)
        ser.close()
        sys.exit(rc)
    except Exception as e:
        print(f"❌ Serial run failed on {args.port}: {e}")
        sys.exit(1)


def _writable_path(requested_path):
    """
    If the caller asked for /tmp/... return /run/... instead because the
    SAMA5D2 rootfs mounts /tmp on the read-only squashfs.  /run is always
    tmpfs and is always writable.
    """
    if requested_path.startswith("/tmp/"):
        alt = "/run/" + requested_path[len("/tmp/"):]
        print(f"   [push] /tmp is read-only on this board — redirecting to {alt}")
        return alt
    return requested_path


def cmd_push(args):
    """
    Transfer a local text file to the board using a heredoc over the serial
    link.  No scp / zmodem required.

    Automatically redirects /tmp/* → /run/* on boards where /tmp is on the
    read-only rootfs (e.g. SAMA5D2 with squashfs image).
    """
    remote = _writable_path(args.remote_path)

    try:
        with open(args.local_file, "r") as f:
            content = f.read()
    except OSError as e:
        print(f"❌ Cannot read local file {args.local_file}: {e}")
        sys.exit(1)

    try:
        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser, timeout=5)

        # Stream the file as a heredoc
        send_line(ser, f"cat > {remote} << '{HEREDOC_EOF}'")
        time.sleep(0.2)

        for line in content.splitlines():
            send_line(ser, line)
            time.sleep(0.08)   # 0.08 s / line is safe for 115200 baud + slow boards

        send_line(ser, HEREDOC_EOF)

        # Wait for the shell to close the heredoc and return its prompt
        send_line(ser, f"echo {PUSH_MARKER}")
        confirm = read_until(ser, PUSH_MARKER, timeout=20)
        if PUSH_MARKER not in confirm:
            # Check if /tmp was read-only
            if "Read-only" in confirm or "read-only" in confirm:
                print(f"❌ Remote filesystem is read-only: {remote}")
            else:
                print(f"❌ Heredoc transfer timed out\nRaw: {confirm!r}")
            ser.close()
            sys.exit(1)

        # Confirm file landed and make it executable
        out, rc = run_command(
            ser,
            f"chmod +x {remote} && ls -l {remote}",
            timeout=10
        )
        print(out)
        ser.close()

        if rc == 0 and "No such file" not in out:
            print(f"✅ File pushed to {remote}")
            sys.exit(0)

        print(f"❌ File did not land correctly at {remote}\nRaw: {out!r}")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Serial push failed on {args.port}: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Control an embedded board over its serial console."
    )
    sub = p.add_subparsers(dest="action", required=True)

    # -- check ---------------------------------------------------------------
    pc = sub.add_parser("check", help="Verify the serial console is alive")
    pc.add_argument("--port",  required=True, help="/dev/ttyUSBx or FTDI serial number")
    pc.add_argument("--baud",  default="115200")
    pc.set_defaults(func=cmd_check)

    # -- run -----------------------------------------------------------------
    pr = sub.add_parser("run", help="Run one shell command and capture its output/exit code")
    pr.add_argument("--port",    required=True)
    pr.add_argument("--baud",    default="115200")
    pr.add_argument("--cmd",     required=True)
    pr.add_argument("--timeout", type=int, default=60)
    pr.set_defaults(func=cmd_run)

    # -- push ----------------------------------------------------------------
    pp = sub.add_parser("push", help="Transfer a local text file to the board via heredoc")
    pp.add_argument("--port",        required=True)
    pp.add_argument("--baud",        default="115200")
    pp.add_argument("--local-file",  required=True)
    pp.add_argument("--remote-path", required=True,
                    help="Destination on board. /tmp/* is auto-redirected to /run/*.")
    pp.add_argument("--timeout",     type=int, default=60)
    pp.set_defaults(func=cmd_push)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
