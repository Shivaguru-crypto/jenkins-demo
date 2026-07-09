#!/usr/bin/env python3
"""
serial_helper.py — talk to a board over its FTDI USB-serial console.

Subcommands:
  check  --port /dev/ttyUSB0 --baud 115200
  run    --port /dev/ttyUSB0 --baud 115200 --cmd "cmd" [--timeout 60]
  push   --port /dev/ttyUSB0 --baud 115200 --local-file f --remote-path /run/f

Exit codes: 0 = PASS, non-zero = FAIL.

--- Fix history -------------------------------------------------------------
v4  wake_shell() — guaranteed clean state sequence:
      Step 1: Send \x03 (Ctrl+C)  — kills any running foreground command
      Step 2: Send \r\n           — flush the line
      Step 3: Send ___JENKINS_EOF___\n — closes any open heredoc
      Step 4: Send \r\n           — flush again
      Step 5: Collect 2 s of output
      Step 6: If "login:" → log in
              If "#" or "$" found → shell confirmed, done
              Otherwise → one more \r\n + 2 s wait
    This guarantees recovery from:
      - Board stuck in heredoc (most common failure mode)
      - Board running a long command (Ctrl+C kills it)
      - Board at login prompt (handles login)
      - Board already at shell prompt (fastest path)
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
    print("❌ pyserial not installed.")
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
    Open port with DTR/RTS LOW before open() to prevent reset pulse.
    No reset_input_buffer() — we want to see what the board is sending.
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
    # intentionally NO reset_input_buffer()
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
    """Read until `marker` appears or timeout."""
    buf, _ = read_until_any(ser, [marker], timeout=timeout)
    return buf


def send_line(ser, line):
    ser.write((line + "\n").encode())


# ---------------------------------------------------------------------------
# Shell / login handling  (v4 — guaranteed clean state)
# ---------------------------------------------------------------------------

def wake_shell(ser):
    """
    Guarantee the board is at a live root shell prompt before any command.

    Recovery sequence (handles ALL stuck states):
      1. Ctrl+C          — kills any foreground command (perip_test, sleep, etc.)
      2. \\r\\n            — flush the interrupted line
      3. HEREDOC_EOF\\n   — closes any open heredoc (most common stuck state)
      4. \\r\\n            — flush again, triggers a fresh prompt
      5. Collect 2 s     — see what the board sends back
      6. Handle login:   — log in if needed
         Handle #/$      — shell confirmed, done
         Fallback        — one more nudge + 2 s wait

    This is idempotent: if the board is already at a clean shell prompt,
    steps 1-4 produce harmless "command not found" noise which is ignored.
    """
    # Step 1-4: clear any stuck state
    ser.write(b"\x03")              # Ctrl+C — interrupt running command
    time.sleep(0.2)
    ser.write(b"\r\n")              # flush interrupted line
    time.sleep(0.1)
    ser.write((HEREDOC_EOF + "\n").encode())  # close any open heredoc
    time.sleep(0.2)
    ser.write(b"\r\n")              # prod for a fresh prompt
    time.sleep(0.1)

    # Step 5: collect the board's response
    buf, matched = read_until_any(ser, ["login:", "#", "$"], timeout=3)
    print(f"   [wake_shell] initial buf={buf!r:.120} matched={matched!r}")

    # Step 6: handle what we got
    if matched and "login:" in matched:
        _do_login(ser)
        return

    if matched:  # '#' or '$'
        print("   [wake_shell] ✅ shell prompt confirmed")
        return

    # Nothing yet — one more nudge
    print("   [wake_shell] no prompt yet — sending extra nudge")
    ser.write(b"\r\n")
    buf2, matched2 = read_until_any(ser, ["login:", "#", "$"], timeout=3)
    print(f"   [wake_shell] nudge buf={buf2!r:.120} matched={matched2!r}")

    if matched2 and "login:" in matched2:
        _do_login(ser)
        return

    if matched2:
        print("   [wake_shell] ✅ shell prompt confirmed after nudge")
        return

    # Last resort — try one more time with a longer wait
    # (board may have been in the middle of booting or printing dmesg)
    print("   [wake_shell] still no prompt — final 4 s wait")
    ser.write(b"\r\n")
    buf3, matched3 = read_until_any(ser, ["login:", "#", "$"], timeout=4)
    print(f"   [wake_shell] final buf={buf3!r:.120} matched={matched3!r}")
    if matched3 and "login:" in matched3:
        _do_login(ser)
    elif matched3:
        print("   [wake_shell] ✅ shell prompt confirmed (final attempt)")
    else:
        print("   [wake_shell] ⚠️  proceeding without confirmed prompt — command may fail")


def _do_login(ser):
    """Handle a login: prompt — send username and optionally password."""
    print(f"   [wake_shell] login prompt — sending '{BOARD_LOGIN_USER}'")
    ser.write((BOARD_LOGIN_USER + "\n").encode())
    time.sleep(1.0)
    resp, _ = read_until_any(ser, ["password:", "assword", "#", "$"], timeout=3)
    if "password:" in resp.lower() or "assword" in resp.lower():
        ser.write((BOARD_LOGIN_PASSWORD + "\n").encode())
        time.sleep(1.0)
        read_until_any(ser, ["#", "$"], timeout=3)
    # Confirm we're at a shell
    ser.write(b"\r\n")
    buf, m = read_until_any(ser, ["#", "$"], timeout=3)
    if m:
        print("   [wake_shell] ✅ logged in — shell confirmed")
    else:
        print(f"   [wake_shell] ⚠️  no shell after login. buf={buf!r:.80}")


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------

def run_command(ser, cmd, timeout=60):
    """Send cmd, capture output + real exit code via END_MARKER."""
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
            print(f"✅ Serial console reachable on {args.port}")
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
    """Redirect /tmp/* → /run/* — SAMA5D2 rootfs is read-only squashfs."""
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

        # Open the heredoc
        send_line(ser, f"cat > {remote} << '{HEREDOC_EOF}'")

        # Wait for the '>' continuation prompt before streaming
        buf, m = read_until_any(ser, [">"], timeout=5)
        if not m:
            print(f"❌ No heredoc '>' prompt. buf={buf!r}")
            ser.close()
            sys.exit(1)

        # Stream file lines
        for line in content.splitlines():
            send_line(ser, line)
            time.sleep(0.06)

        # Close heredoc
        send_line(ser, HEREDOC_EOF)

        # Wait for shell '#' prompt — confirms heredoc closed cleanly
        buf2, m2 = read_until_any(ser, ["#", "$"], timeout=15)
        if not m2:
            if "read-only" in buf2.lower() or "Read-only" in buf2:
                print(f"❌ Remote FS is read-only: {remote}")
            else:
                print(f"❌ Heredoc did not close. buf={buf2!r}")
            ser.close()
            sys.exit(1)

        # Confirm with explicit marker
        send_line(ser, f"echo {PUSH_MARKER}")
        confirm = read_until(ser, PUSH_MARKER, timeout=10)
        if PUSH_MARKER not in confirm:
            print(f"❌ PUSH_MARKER missing. buf={confirm!r}")
            ser.close()
            sys.exit(1)

        # Make executable + verify
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
