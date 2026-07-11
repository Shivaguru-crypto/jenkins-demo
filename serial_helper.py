#!/usr/bin/env python3
"""
serial_helper.py — Final stable version for embedded board CI/CD testing.

Subcommands:
  check  --port /dev/ttyUSB0 --baud 115200
  run    --port /dev/ttyUSB0 --baud 115200 --cmd "cmd" [--timeout 60]
  push   --port /dev/ttyUSB0 --baud 115200 --local-file f --remote-path /run/f

Exit codes: 0 = PASS, non-zero = FAIL.

=============================================================================
COMPLETE ERROR LOG & FIX HISTORY
=============================================================================

ERROR #1 — wake_shell() missed login prompt (buf always empty)
  Symptom : [wake_shell] already at shell prompt / Raw: ''
  Cause   : ser.read(ser.in_waiting or 1) reads only bytes in buffer at that
            instant. After open_port() + reset_input_buffer() + sleep(0.5),
            buffer is empty so reads 1 byte and misses "login:" prompt.
  Fix     : Replaced with read_until_any() which polls ser.in_waiting in a
            loop for a full timeout window — collects everything the board
            sends before deciding what state it is in.

ERROR #2 — reset_input_buffer() flushed board response
  Symptom : Raw: '' even though board was alive and responding.
  Cause   : open_port() called reset_input_buffer() which discarded bytes
            the board was already sending (prompt echo, login prompt etc).
            run_command() then had nothing to read → timeout → empty raw.
  Fix     : Removed reset_input_buffer() from open_port() entirely.
            Board bytes are now read and kept, never discarded.

ERROR #3 — /tmp read-only on SAMA5D2 (squashfs rootfs)
  Symptom : -sh: can't create /tmp/perip_test.sh: Read-only file system
  Cause   : SAMA5D2 rootfs is squashfs (read-only). /tmp lives on it.
  Fix     : _writable() redirects /tmp/* → /run/* automatically.
            /run is always tmpfs (writable) on this board.

ERROR #4 — Heredoc transfer timed out (Raw: '')
  Symptom : ❌ Heredoc transfer timed out. Raw: ''
  Cause   : Board stuck inside open heredoc from a previous failed push.
            Every \r\n we sent was absorbed as heredoc content — board
            never sent back a # prompt so read_until() starved.
  Fix     : wake_shell() now sends HEREDOC_EOF before probing for prompt,
            guaranteed to close any open heredoc on every call.

ERROR #5 — Minicom holding serial ports exclusively
  Symptom : buf='' on EVERY call for BOTH boards. Port opens but 0 bytes.
  Cause   : minicom processes (PID 100509, 100515) were running since 10:08,
            holding /dev/ttyUSB0 and /dev/ttyUSB1. Jenkins could open the
            fd but received nothing because minicom owned the RX line.
  Fix     : sudo pkill minicom before every Jenkins run.
            Never leave minicom open while pipeline is running.

ERROR #6 — slave-1 not in dialout group
  Symptom : Port opens but reads nothing (permission issue on RX).
  Cause   : Jenkins runs as user slave-1 who was not in the dialout group.
            /dev/ttyUSB* is owned by root:dialout (crw-rw----).
  Fix     : sudo usermod -aG dialout slave-1
            sudo pkill -u slave-1 java  (restart agent to pick up group)

ERROR #7 — END_MARKER ___CMD_DONE___ wrapped at 80 columns
  Symptom : Board1 Serial Session FAIL. echo ___CMD_DONE___$? appeared in
            output but marker was never found by read_until().
  Cause   : Board terminal is 80 columns wide. Command echo wrapped the
            marker across two lines: ___CMD_DONE__\n_0 — read_until()
            looks for the marker as one string, never finds split version.
  Fix     : END_MARKER shortened to XQ7DONE7QX (10 chars). Will never
            wrap regardless of command length or terminal width.

ERROR #8 — stty cols 200 in run_command() drained script output
  Symptom : Peripheral Test returns in 2s, output cut at /dev/gpiochi
  Cause   : run_command() sent "stty cols 200\n" then sleep(0.3) then
            ser.read(ser.in_waiting) to drain the stty echo. But the board
            had already started running perip_test.sh output during that
            0.3s — the drain read and discarded the first lines of script
            output. read_until() then missed the marker and hit idle gap.
  Fix     : Moved stty cols 200 into wake_shell() after prompt confirmed.
            run_command() no longer touches stty.

ERROR #9 — idle_limit too short, dmesg output caused gaps
  Symptom : Output cut mid-dmesg: VFS: Mounted root (squa
  Cause   : dmesg | tail -30 sends 30 lines in bursts with pauses between
            them. idle_limit=1.5s fired during a pause, stopped reading
            before the end marker arrived.
  Fix     : idle_limit raised to 4.0s. dmesg removed from perip_test.sh.

ERROR #10 — perip_test.sh printed FAIL for missing mmcblk (Board1)
  Symptom : Board1 Peripheral Test FAIL due to "FAIL: no /dev/mmcblk*"
  Cause   : Board1 runs from squashfs — no SD card/eMMC. Script printed
            FAIL which triggered our log scanner to mark stage as failed.
  Fix     : Changed to INFO in perip_test.sh. Board1 has no storage device
            by design — this is expected and not a real failure.

=============================================================================
"""

import argparse, re, subprocess, sys, time
try:
    import serial, serial.tools.list_ports
except ImportError:
    print("pip3 install pyserial --break-system-packages"); sys.exit(1)

END_MARKER  = "XQ7DONE7QX"    # short+unique — never wraps at 80 cols, never
PUSH_MARKER = "XQ7PUSH7QX"    # appears in any board output or command echo
HEREDOC_EOF = "___JENKINS_EOF___"
BOARD_LOGIN_USER     = "root"
BOARD_LOGIN_PASSWORD = ""


# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------

def resolve_port(p):
    if p.startswith("/dev/"): return p
    for port in serial.tools.list_ports.comports():
        if port.serial_number == p: return port.device
    print(f"No device with serial number '{p}'"); sys.exit(1)


def open_port(port, baud, timeout=5):
    """
    Open port with DTR/RTS LOW before open() — prevents reset pulse.
    No reset_input_buffer() — board bytes must never be discarded (Error #2).
    """
    resolved = resolve_port(port)
    ser = serial.Serial()
    ser.port = resolved; ser.baudrate = int(baud); ser.timeout = timeout
    ser.dtr = False; ser.rts = False; ser.dsrdtr = False
    ser.open()
    try:
        subprocess.run(["stty","-F",resolved,"-hupcl"],
                       check=False, capture_output=True)
    except: pass
    time.sleep(0.3)
    # NO reset_input_buffer() here — see Error #2
    return ser


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def read_until_any(ser, markers, timeout=5):
    """
    Non-blocking poll: read ser.in_waiting bytes until any marker found.
    Uses in_waiting (not ser.read(N)) to avoid blocking (see Error #1).
    """
    buf = ""; start = time.time()
    while time.time() - start < timeout:
        n = ser.in_waiting
        if n:
            buf += ser.read(n).decode(errors="ignore")
            for m in markers:
                if m in buf: return buf, m
        else:
            time.sleep(0.05)
    return buf, None


def read_until(ser, marker, timeout=30):
    """
    Read until marker found or timeout.
    idle_limit: keeps reading during burst output (dmesg etc) — only stops
    after 4.0s of complete silence AND we already have some data (Error #9).
    """
    buf = ""
    start    = time.time()
    last_data = time.time()
    idle_limit = 8.0

    while time.time() - start < timeout:
        n = ser.in_waiting
        if n:
            buf += ser.read(n).decode(errors="ignore")
            last_data = time.time()
            if marker in buf:
                break
        else:
            if buf and (time.time() - last_data) > idle_limit:
                break
            time.sleep(0.05)
    return buf


def send_line(ser, line):
    ser.write((line + "\n").encode())


# ---------------------------------------------------------------------------
# Shell / login handling
# ---------------------------------------------------------------------------

def wake_shell(ser):
    """
    Guarantee a clean root shell prompt before any command.

    Recovery sequence (fixes Error #4 — stuck heredoc):
      1. Ctrl+C          — kills any running foreground command
      2. \\r\\n            — flushes interrupted line
      3. HEREDOC_EOF\\n   — closes any open heredoc
      4. \\r\\n            — prods for fresh prompt
      5. stty cols 200   — widens terminal, prevents 80-col wrap (Error #7,8)
      6. Wait for # or login:

    Idempotent: if already at clean shell, steps 1-4 produce harmless noise.
    """
    print("   [wake_shell] sending recovery sequence")
    ser.write(b"\x03");                         time.sleep(0.2)  # Ctrl+C
    ser.write(b"\r\n");                         time.sleep(0.1)  # flush
    ser.write((HEREDOC_EOF + "\n").encode());   time.sleep(0.2)  # close heredoc
    ser.write(b"\r\n");                         time.sleep(0.1)  # prod prompt

    buf, m = read_until_any(ser, ["login:", "#", "$"], timeout=4)
    print(f"   [wake_shell] buf={buf!r:.120} matched={m!r}")

    if m and "login:" in m:
        _do_login(ser)
    elif m:
        print("   [wake_shell] shell confirmed")
        # Set wide terminal now that we have a shell (Error #7, #8)
        ser.write(b"stty cols 200\n"); time.sleep(0.3)
        ser.read(ser.in_waiting or 1)
        return
    else:
        # Second nudge
        ser.write(b"\r\n")
        buf2, m2 = read_until_any(ser, ["login:", "#", "$"], timeout=4)
        print(f"   [wake_shell] nudge buf={buf2!r:.120} matched={m2!r}")
        if m2 and "login:" in m2:
            _do_login(ser)
        elif m2:
            print("   [wake_shell] shell confirmed after nudge")
            ser.write(b"stty cols 200\n"); time.sleep(0.3)
            ser.read(ser.in_waiting or 1)
            return
        else:
            print("   [wake_shell] WARNING: no prompt — proceeding anyway")
            return

    # After login, set wide terminal
    ser.write(b"stty cols 200\n"); time.sleep(0.3)
    ser.read(ser.in_waiting or 1)


def _do_login(ser):
    """Handle login: prompt — send username and password."""
    print(f"   [wake_shell] login prompt — sending '{BOARD_LOGIN_USER}'")
    ser.write((BOARD_LOGIN_USER + "\n").encode()); time.sleep(1.0)
    resp, _ = read_until_any(ser, ["password:", "assword", "#", "$"], timeout=3)
    if "assword" in resp.lower():
        ser.write((BOARD_LOGIN_PASSWORD + "\n").encode()); time.sleep(1.0)
        read_until_any(ser, ["#", "$"], timeout=3)
    ser.write(b"\r\n")
    _, m = read_until_any(ser, ["#", "$"], timeout=3)
    print("   [wake_shell] logged in ✅" if m else
          "   [wake_shell] WARNING: no shell after login")


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------

def run_command(ser, cmd, timeout=60):
    """
    Send cmd and capture output + real exit code.
    Marker XQ7DONE7QX is short and unique — never wraps, never false-matches.
    """
    send_line(ser, f"{cmd}; echo {END_MARKER}$?")
    raw = read_until(ser, END_MARKER, timeout=timeout)

    exit_code = 1; body = []; echoed = False
    for line in raw.splitlines():
        m = re.search(rf"{re.escape(END_MARKER)}(\d+)", line)
        if m: exit_code = int(m.group(1)); continue
        if not echoed and cmd in line: echoed = True; continue
        if line.strip(): body.append(line)
    return "\n".join(body), exit_code


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_check(args):
    try:
        ser = open_port(args.port, args.baud)
        wake_shell(ser)
        out, rc = run_command(ser, "echo PING_OK", timeout=10)
        ser.close()
        if "PING_OK" in out or rc == 0:
            print(f"✅ Reachable: {args.port}"); sys.exit(0)
        print(f"❌ No response. raw={out!r}"); sys.exit(1)
    except Exception as e:
        print(f"❌ {args.port}: {e}"); sys.exit(1)


def cmd_run(args):
    try:
        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser)
        out, rc = run_command(ser, args.cmd, timeout=args.timeout)
        print(out); ser.close(); sys.exit(rc)
    except Exception as e:
        print(f"❌ run failed: {e}"); sys.exit(1)


def _writable(path):
    """Redirect /tmp/* → /run/* — SAMA5D2 rootfs is read-only (Error #3)."""
    if path.startswith("/tmp/"):
        alt = "/run/" + path[5:]
        print(f"   [push] /tmp is read-only — using {alt}"); return alt
    return path


def cmd_push(args):
    """Transfer local text file to board via heredoc over serial."""
    remote = _writable(args.remote_path)
    try:
        content = open(args.local_file).read()
    except OSError as e:
        print(f"❌ {e}"); sys.exit(1)

    try:
        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser)

        # Open heredoc
        send_line(ser, f"cat > {remote} << '{HEREDOC_EOF}'")
        buf, m = read_until_any(ser, [">"], timeout=5)
        if not m:
            print(f"❌ no heredoc prompt. buf={buf!r}"); ser.close(); sys.exit(1)

        # Stream file lines
        for line in content.splitlines():
            send_line(ser, line); time.sleep(0.06)

        # Close heredoc — wait for shell # prompt
        send_line(ser, HEREDOC_EOF)
        buf2, m2 = read_until_any(ser, ["#", "$"], timeout=15)
        if not m2:
            print(f"❌ heredoc did not close. buf={buf2!r}"); ser.close(); sys.exit(1)

        # Confirm with explicit marker
        send_line(ser, f"echo {PUSH_MARKER}")
        confirm = read_until(ser, PUSH_MARKER, timeout=10)
        if PUSH_MARKER not in confirm:
            print(f"❌ push marker missing. buf={confirm!r}"); ser.close(); sys.exit(1)

        # Make executable + verify
        out, rc = run_command(ser, f"chmod +x {remote} && ls -l {remote}", timeout=10)
        print(out); ser.close()

        if rc == 0 and "No such file" not in out:
            print(f"✅ pushed to {remote}"); sys.exit(0)
        print(f"❌ file missing at {remote}. out={out!r}"); sys.exit(1)

    except Exception as e:
        print(f"❌ push failed: {e}"); sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)

    pc = sub.add_parser("check")
    pc.add_argument("--port", required=True)
    pc.add_argument("--baud", default="115200")
    pc.set_defaults(func=cmd_check)

    pr = sub.add_parser("run")
    pr.add_argument("--port", required=True)
    pr.add_argument("--baud", default="115200")
    pr.add_argument("--cmd", required=True)
    pr.add_argument("--timeout", type=int, default=60)
    pr.set_defaults(func=cmd_run)

    pp = sub.add_parser("push")
    pp.add_argument("--port", required=True)
    pp.add_argument("--baud", default="115200")
    pp.add_argument("--local-file", required=True)
    pp.add_argument("--remote-path", required=True)
    pp.add_argument("--timeout", type=int, default=60)
    pp.set_defaults(func=cmd_push)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
