#!/usr/bin/env python3
"""
serial_helper.py — talk to a board over its FTDI USB-serial console.

Subcommands:
  check  --serial <ID> --baud 115200
  run    --serial <ID> --baud 115200 --cmd "cmd" [--timeout 60]
  push   --serial <ID> --baud 115200 --local-file f --remote-path /run/f

  --port can be used instead of --serial if needed.

Exit codes: 0 = PASS, non-zero = FAIL.

--- Fix history -------------------------------------------------------------
Fix 1  settle delay (time.sleep) after wake_shell() before sending command
       Board 2 shell prompt appears but board not yet ready to accept input
Fix 2  ping confirmation after wake_shell() — sends echo __READY__ and waits
       for response before sending real command, proves board is truly ready
Fix 5  serial ID resolution — --serial D3074GZG resolves to /dev/ttyUSBx at
       runtime via /dev/serial/by-id/, so port swap after replug never causes
       wrong board to be tested
-----------------------------------------------------------------------------
"""

import argparse
import re
import subprocess
import sys
import time
import glob
import os

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("❌ pyserial not installed.")
    sys.exit(1)

END_MARKER  = "___CMD_DONE___"
PUSH_MARKER = "___PUSH_DONE___"
HEREDOC_EOF = "___JENKINS_EOF___"
READY_MARKER = "__READY__"

BOARD_LOGIN_USER     = "root"
BOARD_LOGIN_PASSWORD = ""


# ---------------------------------------------------------------------------
# Fix 5 — Port resolution (serial ID → /dev/ttyUSBx)
# ---------------------------------------------------------------------------

def resolve_port(port_or_serial):
    """
    Fix 5: Accept either a direct port path (/dev/ttyUSBx) or a udev
    serial number (e.g. D3074GZG). If a serial number is given, find the
    matching device under /dev/serial/by-id/ and resolve the symlink to
    the real /dev/ttyUSBx path.

    This means port swap after replug never causes the wrong board to be
    tested — the serial number is physically burned into the FTDI adapter
    and never changes regardless of plug order.
    """
    if port_or_serial.startswith("/dev/"):
        return port_or_serial

    # Try /dev/serial/by-id/ first (udev symlinks)
    by_id = glob.glob(f"/dev/serial/by-id/*{port_or_serial}*")
    if by_id:
        resolved = os.path.realpath(by_id[0])
        print(f"   [resolve_port] {port_or_serial} → {resolved}")
        return resolved

    # Try pyserial's port list as fallback
    for p in serial.tools.list_ports.comports():
        if p.serial_number == port_or_serial:
            print(f"   [resolve_port] {port_or_serial} → {p.device}")
            return p.device

    print(f"❌ No USB-serial device with serial number '{port_or_serial}'.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Port open — DTR/RTS low to prevent reset pulse
# ---------------------------------------------------------------------------

def open_port(port_or_serial, baud, timeout=5):
    """
    Open port with DTR/RTS LOW before open() to prevent reset pulse.
    Also runs stty -hupcl to prevent hangup-on-close resetting the board.
    """
    resolved = resolve_port(port_or_serial)
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
    return ser


# ---------------------------------------------------------------------------
# Low-level I/O
# ---------------------------------------------------------------------------

def read_until_any(ser, markers, timeout=5):
    """
    Read until ANY marker in `markers` list appears, or timeout.
    Returns (full_buf_string, matched_marker_or_None).
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


def read_until(ser, marker, timeout=30):
    buf, _ = read_until_any(ser, [marker], timeout=timeout)
    return buf


def send_line(ser, line):
    ser.write((line + "\n").encode())


# ---------------------------------------------------------------------------
# Shell / login handling
# ---------------------------------------------------------------------------

def wake_shell(ser):
    """
    Guarantee the board is at a live root shell prompt before any command.

    Recovery sequence handles ALL stuck states:
      1. Ctrl+C       — kills any foreground command
      2. \\r\\n         — flush interrupted line
      3. HEREDOC_EOF  — closes any open heredoc
      4. \\r\\n         — prod for fresh prompt
      5. Read + handle login: or #/$ prompt
    """
    print("   [wake_shell] sending recovery sequence")
    ser.write(b"\x03")
    time.sleep(0.2)
    ser.write(b"\r\n")
    time.sleep(0.1)
    ser.write((HEREDOC_EOF + "\n").encode())
    time.sleep(0.2)
    ser.write(b"\r\n")
    time.sleep(0.1)

    buf, matched = read_until_any(ser, ["login:", "#", "$"], timeout=5)
    print(f"   [wake_shell] buf={buf!r:.120} matched={matched!r}")

    if matched and "login:" in matched:
        _do_login(ser)
        return

    if matched:
        print("   [wake_shell] shell confirmed")
        return

    # nudge
    print("   [wake_shell] nudge")
    ser.write(b"\r\n")
    buf2, matched2 = read_until_any(ser, ["login:", "#", "$"], timeout=5)
    print(f"   [wake_shell] nudge buf={buf2!r:.120} matched={matched2!r}")

    if matched2 and "login:" in matched2:
        _do_login(ser)
        return

    if matched2:
        print("   [wake_shell] shell confirmed after nudge")
        return

    # final attempt
    print("   [wake_shell] final 4s wait")
    ser.write(b"\r\n")
    buf3, matched3 = read_until_any(ser, ["login:", "#", "$"], timeout=4)
    if matched3 and "login:" in matched3:
        _do_login(ser)
    elif matched3:
        print("   [wake_shell] shell confirmed (final)")
    else:
        print("   [wake_shell] ⚠️  no prompt confirmed — command may fail")


def _do_login(ser):
    print(f"   [wake_shell] login prompt — sending '{BOARD_LOGIN_USER}'")
    ser.write((BOARD_LOGIN_USER + "\n").encode())
    time.sleep(1.0)
    resp, _ = read_until_any(ser, ["password:", "assword", "#", "$"], timeout=5)
    if "password:" in resp.lower() or "assword" in resp.lower():
        ser.write((BOARD_LOGIN_PASSWORD + "\n").encode())
        time.sleep(1.0)
        read_until_any(ser, ["#", "$"], timeout=5)
    ser.write(b"\r\n")
    buf, m = read_until_any(ser, ["#", "$"], timeout=5)
    if m:
        print("   [wake_shell] ✅ logged in — shell confirmed")
    else:
        print(f"   [wake_shell] ⚠️  no shell after login. buf={buf!r:.80}")


# ---------------------------------------------------------------------------
# Fix 1 + Fix 2 — settle delay + ping confirmation
# ---------------------------------------------------------------------------

def confirm_ready(ser, timeout=10):
    """
    Fix 1: sleep(0.5) gives the board time to settle after the shell
    prompt appears — Board 2 was failing because run_command fired before
    the board was ready to echo back a response.

    Fix 2: send echo __READY__ and wait for __READY__ back before sending
    the real command. This actively proves the board can receive and respond,
    instead of assuming it's ready just because a prompt was seen.
    """
    # Fix 1 — settle delay
    time.sleep(0.5)

    # Fix 2 — ping confirmation
    ser.write(f"echo {READY_MARKER}\n".encode())
    buf, m = read_until_any(ser, [READY_MARKER], timeout=timeout)
    if not m:
        raise Exception(
            f"Board did not respond to ready-check after wake_shell. "
            f"buf={buf!r:.120} — check baud rate, wiring, board power."
        )
    print("   [confirm_ready] ✅ board ready")


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------

def run_command(ser, cmd, timeout=60):
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
        confirm_ready(ser)          # Fix 1 + Fix 2
        out, rc = run_command(ser, "echo PING_OK", timeout=10)
        ser.close()
        if "PING_OK" in out or rc == 0:
            print(f"✅ Reachable: {args.port}")
            sys.exit(0)
        print(f"❌ No response. raw={out!r}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Could not open {args.port}: {e}")
        sys.exit(1)


def cmd_run(args):
    try:
        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser)
        confirm_ready(ser)          # Fix 1 + Fix 2
        out, rc = run_command(ser, args.cmd, timeout=args.timeout)
        print(out)
        ser.close()
        sys.exit(rc)
    except Exception as e:
        print(f"❌ Serial run failed on {args.port}: {e}")
        sys.exit(1)


def _writable_path(path):
    """Redirect /tmp/* → /run/* for read-only rootfs boards."""
    if path.startswith("/tmp/"):
        alt = "/run/" + path[len("/tmp/"):]
        print(f"   [push] /tmp is read-only — using {alt}")
        return alt
    return path


def cmd_push(args):
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
        confirm_ready(ser)          # Fix 1 + Fix 2

        send_line(ser, f"cat > {remote} << '{HEREDOC_EOF}'")
        buf, m = read_until_any(ser, [">"], timeout=5)
        if not m:
            print(f"❌ No heredoc '>' prompt. buf={buf!r}")
            ser.close()
            sys.exit(1)

        for line in content.splitlines():
            send_line(ser, line)
            time.sleep(0.06)

        send_line(ser, HEREDOC_EOF)
        buf2, m2 = read_until_any(ser, ["#", "$"], timeout=15)
        if not m2:
            print(f"❌ Heredoc did not close. buf={buf2!r}")
            ser.close()
            sys.exit(1)

        send_line(ser, f"echo {PUSH_MARKER}")
        confirm = read_until(ser, PUSH_MARKER, timeout=10)
        if PUSH_MARKER not in confirm:
            print(f"❌ PUSH_MARKER missing. buf={confirm!r}")
            ser.close()
            sys.exit(1)

        out, rc = run_command(ser, f"chmod +x {remote} && ls -l {remote}", timeout=10)
        print(out)
        ser.close()

        if rc == 0 and "No such file" not in out:
            print(f"✅ Pushed to {remote}")
            sys.exit(0)

        print(f"❌ File missing at {remote}. out={out!r}")
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

    # check
    pc = sub.add_parser("check")
    pc.add_argument("--port",   required=True,
                    help="Port path (/dev/ttyUSBx) or serial ID (e.g. D3074GZG)")
    pc.add_argument("--baud",   default="115200")
    pc.set_defaults(func=cmd_check)

    # run
    pr = sub.add_parser("run")
    pr.add_argument("--port",    required=True,
                    help="Port path (/dev/ttyUSBx) or serial ID (e.g. D3074GZG)")
    pr.add_argument("--baud",    default="115200")
    pr.add_argument("--cmd",     required=True)
    pr.add_argument("--timeout", type=int, default=60)
    pr.set_defaults(func=cmd_run)

    # push
    pp = sub.add_parser("push")
    pp.add_argument("--port",        required=True,
                    help="Port path (/dev/ttyUSBx) or serial ID (e.g. D3074GZG)")
    pp.add_argument("--baud",        default="115200")
    pp.add_argument("--local-file",  required=True)
    pp.add_argument("--remote-path", required=True)
    pp.add_argument("--timeout",     type=int, default=60)
    pp.set_defaults(func=cmd_push)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
