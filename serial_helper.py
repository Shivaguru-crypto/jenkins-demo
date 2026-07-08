#!/usr/bin/env python3
"""
serial_helper.py

Talks to a board over a raw serial console (FTDI USB-serial, no network/SSH).

Key problem this solves:
    The board sits at a `login:` prompt. If you just write commands to the
    serial port without first logging in, the board treats your bytes as
    login-name input -> you get "Login incorrect" and garbage in the log,
    which is exactly what the Jenkins console showed.

Subcommands:
    check   -- confirm the board is alive and reachable on the given port
    run     -- log in (if needed), run one command, capture its output
    push    -- log in (if needed), write a local file to the board using
               a here-doc + base64, so binary-unsafe characters survive

Usage:
    python3 serial_helper.py check --port /dev/ttyUSB0 --baud 115200
    python3 serial_helper.py run   --port /dev/ttyUSB0 --baud 115200 --cmd "uname -a"
    python3 serial_helper.py push  --port /dev/ttyUSB0 --baud 115200 \
        --local-file perip_test.sh --remote-path /tmp/perip_test.sh

For scripts that block on `read -p "..."` prompts and can't be modified
(e.g. an instructor-provided test script), add --auto-enter to `run`:
    python3 serial_helper.py run --port /dev/ttyUSB0 --baud 115200 \
        --cmd "/tmp/perip_test.sh" --timeout 400 --auto-enter --idle-seconds 4
This sends a blank Enter whenever the board goes quiet for --idle-seconds,
which is enough to let a `read` call return (with empty input) and the
script continue, instead of hanging until Jenkins kills the stage.

Also supports resolving a port from a udev serial number, so port numbers
don't shift around when boards are unplugged/replugged:
    python3 serial_helper.py check --serial FT8U9XYZ --baud 115200
"""

import argparse
import base64
import glob
import os
import sys
import time

try:
    import serial
except ImportError:
    print("❌ pyserial not installed. pip3 install pyserial --break-system-packages", file=sys.stderr)
    sys.exit(1)


BOARD_USER = os.environ.get("BOARD_USER", "root")
BOARD_PASSWORD = os.environ.get("BOARD_PASSWORD", "")  # empty = no password expected

# Prompts we look for. Adjust SHELL_PROMPT to match your board's actual
# prompt if it's not one of these (e.g. "root@rugged-board-a5d2x:~#").
LOGIN_PROMPT_MARKERS = ["login:"]
PASSWORD_PROMPT_MARKERS = ["password:", "Password:"]
SHELL_PROMPT_MARKERS = ["# ", "$ ", "~# ", "~$ "]
INCORRECT_LOGIN_MARKERS = ["Login incorrect", "incorrect password"]


def get_port_by_serial(serial_number):
    """Dynamically find the port path for a given serial number."""
    path = f"/dev/serial/by-id/*{serial_number}*"
    devices = glob.glob(path)
    if not devices:
        raise Exception(f"Device with serial {serial_number} not found in /dev/serial/by-id/")
    return os.path.realpath(devices[0])


def _read_until(ser, markers, timeout, poke_newline_every=None, idle_auto_enter=None):
    """
    Read from the serial port until one of `markers` shows up in the
    accumulated buffer, or timeout elapses. Returns (matched_marker_or_None, buffer_text).

    poke_newline_every: send a bare \\r\\n on a fixed cadence (used during
        login, to re-print a prompt that hasn't appeared yet).

    idle_auto_enter: if set (seconds), send a bare \\r\\n whenever NO new
        bytes have arrived for that many seconds. This is what unblocks a
        script that's sitting at a `read -p "..."` prompt: we don't need to
        know what the script is asking -- an Enter with empty input is
        enough to let a `read` call return and the script continue. Use
        this only while running a script we're not allowed to modify
        (e.g. perip_test.sh), not while waiting for a login prompt.
    """
    end_time = time.time() + timeout
    buf = b""
    last_poke = time.time()
    last_data_time = time.time()
    while time.time() < end_time:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            last_data_time = time.time()
        text = buf.decode(errors="replace")
        for m in markers:
            if m in text:
                return m, text
        if poke_newline_every and (time.time() - last_poke) > poke_newline_every:
            ser.write(b"\r\n")
            last_poke = time.time()
        if idle_auto_enter and (time.time() - last_data_time) > idle_auto_enter:
            ser.write(b"\r\n")
            last_data_time = time.time()  # reset so we don't spam every loop tick
        if not chunk:
            time.sleep(0.05)
    return None, buf.decode(errors="replace")


def ensure_shell(ser, login_timeout=20):
    """
    Make sure we're sitting at a live shell prompt, logging in if the board
    is currently showing a login: prompt. Raises on failure.
    """
    # Nudge the board so it re-prints whatever prompt it's at.
    ser.write(b"\r\n")
    time.sleep(0.3)
    ser.reset_input_buffer()
    ser.write(b"\r\n")

    marker, text = _read_until(
        ser,
        LOGIN_PROMPT_MARKERS + SHELL_PROMPT_MARKERS,
        timeout=login_timeout,
        poke_newline_every=3,
    )

    if marker in SHELL_PROMPT_MARKERS:
        return  # already logged in

    if marker in LOGIN_PROMPT_MARKERS:
        ser.write((BOARD_USER + "\r\n").encode())
        marker2, text2 = _read_until(
            ser,
            PASSWORD_PROMPT_MARKERS + SHELL_PROMPT_MARKERS + INCORRECT_LOGIN_MARKERS,
            timeout=login_timeout,
        )
        if marker2 in INCORRECT_LOGIN_MARKERS:
            raise RuntimeError(f"Login failed for user '{BOARD_USER}':\n{text2}")
        if marker2 in PASSWORD_PROMPT_MARKERS:
            ser.write((BOARD_PASSWORD + "\r\n").encode())
            marker3, text3 = _read_until(
                ser, SHELL_PROMPT_MARKERS + INCORRECT_LOGIN_MARKERS, timeout=login_timeout
            )
            if marker3 in INCORRECT_LOGIN_MARKERS or marker3 is None:
                raise RuntimeError(f"Login failed (bad password?):\n{text3}")
            return
        if marker2 in SHELL_PROMPT_MARKERS:
            return
        raise RuntimeError(f"Timed out waiting for shell after sending username:\n{text2}")

    raise RuntimeError(f"Board did not show login or shell prompt within {login_timeout}s:\n{text}")


def cmd_check(args):
    ser = serial.Serial(args.port, args.baud, timeout=1)
    try:
        ensure_shell(ser, login_timeout=args.timeout)
        print("✅ Board is REACHABLE and shell is ready")
        return 0
    except Exception as e:
        print(f"❌ Board not reachable: {e}")
        return 1
    finally:
        ser.close()


def cmd_run(args):
    ser = serial.Serial(args.port, args.baud, timeout=1)
    try:
        ensure_shell(ser, login_timeout=args.timeout)

        marker_tag = "__CMD_DONE_MARKER__"
        full_cmd = f"{args.cmd}; echo {marker_tag}$?\r\n"
        ser.reset_input_buffer()
        ser.write(full_cmd.encode())

        idle_auto_enter = args.idle_seconds if args.auto_enter else None
        marker, text = _read_until(
            ser, [marker_tag], timeout=args.timeout, idle_auto_enter=idle_auto_enter
        )
        if marker is None:
            print("❌ Timed out waiting for command to finish")
            print(text)
            return 1

        # Strip the echoed command line and the marker line, print the rest.
        lines = text.splitlines()
        out_lines = [l for l in lines if args.cmd not in l]
        print("\n".join(out_lines))

        rc_line = [l for l in lines if marker_tag in l]
        rc = 1
        if rc_line:
            try:
                rc = int(rc_line[-1].split(marker_tag)[-1].strip())
            except ValueError:
                rc = 1
        return rc
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return 1
    finally:
        ser.close()


def cmd_push(args):
    ser = serial.Serial(args.port, args.baud, timeout=1)
    try:
        ensure_shell(ser, login_timeout=args.timeout)

        with open(args.local_file, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()

        # Write via base64 + here-doc so any special characters in the
        # script are transported safely over the serial link, then decode
        # on the board side. Chunk it so we don't overrun small UART buffers.
        remote_b64_path = args.remote_path + ".b64"
        ser.write(f"rm -f {remote_b64_path}\r\n".encode())
        time.sleep(0.2)
        ser.reset_input_buffer()

        chunk_size = 200
        for i in range(0, len(b64), chunk_size):
            chunk = b64[i:i + chunk_size]
            ser.write(f"echo '{chunk}' >> {remote_b64_path}\r\n".encode())
            # Drain so the board's UART buffer doesn't overflow on long files
            _read_until(ser, ["__never_match__"], timeout=0.3)

        decode_cmd = f"base64 -d {remote_b64_path} > {args.remote_path} && chmod +x {args.remote_path} && echo __PUSH_OK__"
        ser.write((decode_cmd + "\r\n").encode())
        marker, text = _read_until(ser, ["__PUSH_OK__"], timeout=args.timeout)

        if marker is None:
            print("❌ File did not land correctly on", args.remote_path)
            print(text)
            return 1

        print(f"✅ Pushed {args.local_file} -> {args.remote_path}")
        return 0
    except Exception as e:
        print(f"❌ Error pushing file: {e}")
        return 1
    finally:
        ser.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--serial", help="Unique board serial number (udev by-id)")
    p.add_argument("--port", help="Direct port path, e.g. /dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--timeout", type=int, default=30, help="Overall command/login timeout (s)")

    sub = p.add_subparsers(dest="command", required=True)

    sp_check = sub.add_parser("check")
    sp_check.set_defaults(func=cmd_check)

    sp_run = sub.add_parser("run")
    sp_run.add_argument("--cmd", required=True)
    sp_run.add_argument(
        "--auto-enter", action="store_true", default=False,
        help="Send a blank Enter whenever the board goes idle (unblocks scripts "
             "sitting at a `read -p` prompt, without needing to modify them)."
    )
    sp_run.add_argument(
        "--idle-seconds", type=float, default=4.0,
        help="How long the board must be silent before --auto-enter fires (default: 4s)."
    )
    sp_run.set_defaults(func=cmd_run)

    sp_push = sub.add_parser("push")
    sp_push.add_argument("--local-file", required=True)
    sp_push.add_argument("--remote-path", required=True)
    sp_push.set_defaults(func=cmd_push)

    args = p.parse_args()

    if args.serial:
        args.port = get_port_by_serial(args.serial)
    elif not args.port:
        print("❌ Error: Must provide either --serial or --port")
        sys.exit(1)

    rc = args.func(args)
    sys.exit(rc if isinstance(rc, int) else 0)


if __name__ == "__main__":
    main()
