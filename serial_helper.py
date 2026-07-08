#!/usr/bin/env python3

import argparse
import base64
import glob
import os
import re
import sys
import time

try:
    import serial
except ImportError:
    print("❌ pyserial not installed. pip3 install pyserial --break-system-packages", file=sys.stderr)
    sys.exit(1)

BOARD_USER = os.environ.get("BOARD_USER", "root")
BOARD_PASSWORD = os.environ.get("BOARD_PASSWORD", "")
LOGIN_TIMEOUT_DEFAULT = 60

LOGIN_PROMPT_MARKERS = ["login:"]
PASSWORD_PROMPT_MARKERS = ["password:", "Password:"]
SHELL_PROMPT_MARKERS = ["# ", "$ ", "~# ", "~$ "]
INCORRECT_LOGIN_MARKERS = ["Login incorrect", "incorrect password"]


def open_serial(port, baud):
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 0.5
    ser.write_timeout = 5
    ser.bytesize = serial.EIGHTBITS
    ser.parity = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.xonxoff = False
    ser.rtscts = False
    ser.dsrdtr = False
    try:
        ser.dtr = False
        ser.rts = False
    except Exception:
        pass
    ser.open()
    time.sleep(0.5)
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception:
        pass
    return ser


def get_port_by_serial(serial_number):
    path = f"/dev/serial/by-id/*{serial_number}*"
    devices = glob.glob(path)
    if not devices:
        raise Exception(f"Device with serial {serial_number} not found in /dev/serial/by-id/")
    return os.path.realpath(devices[0])


def _safe_decode(buf):
    return buf.decode(errors="replace")


def _read_until(ser, markers, timeout, poke_newline_every=None, idle_auto_enter=None):
    end_time = time.time() + timeout
    buf = b""
    last_poke = time.time()
    last_data_time = time.time()

    while time.time() < end_time:
        waiting = ser.in_waiting if hasattr(ser, "in_waiting") else 0
        chunk = ser.read(waiting or 1)

        if chunk:
            buf += chunk
            last_data_time = time.time()

        text = _safe_decode(buf)
        for marker in markers:
            if marker in text:
                return marker, text

        now = time.time()

        if poke_newline_every and (now - last_poke) >= poke_newline_every:
            ser.write(b"\r\n")
            ser.flush()
            last_poke = now

        if idle_auto_enter and (now - last_data_time) >= idle_auto_enter:
            ser.write(b"\r\n")
            ser.flush()
            last_data_time = now

        if not chunk:
            time.sleep(0.05)

    return None, _safe_decode(buf)


def _drain_briefly(ser, seconds=0.4):
    end = time.time() + seconds
    buf = b""
    while time.time() < end:
        waiting = ser.in_waiting if hasattr(ser, "in_waiting") else 0
        chunk = ser.read(waiting or 1)
        if chunk:
            buf += chunk
        else:
            time.sleep(0.05)
    return _safe_decode(buf)


def _normalize_output(text):
    return text.replace("\r", "")


def _strip_command_echo(text, original_cmd, marker_tag):
    lines = _normalize_output(text).splitlines()
    cleaned = []
    marker_re = re.compile(rf"{re.escape(marker_tag)}\s*(-?\d+)")
    cmd_core = original_cmd.strip()

    for line in lines:
        s = line.strip()
        if marker_tag in s:
            continue
        if cmd_core and cmd_core in s:
            continue
        cleaned.append(line)

    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    return "\n".join(cleaned), marker_re


def ensure_shell(ser, login_timeout=LOGIN_TIMEOUT_DEFAULT):
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception:
        pass

    ser.write(b"\r\n")
    ser.flush()
    time.sleep(0.3)
    ser.write(b"\r\n")
    ser.flush()

    marker, text = _read_until(
        ser,
        LOGIN_PROMPT_MARKERS + SHELL_PROMPT_MARKERS,
        timeout=login_timeout,
        poke_newline_every=3,
    )

    if marker in SHELL_PROMPT_MARKERS:
        return

    if marker in LOGIN_PROMPT_MARKERS:
        ser.write((BOARD_USER + "\r\n").encode())
        ser.flush()

        marker2, text2 = _read_until(
            ser,
            PASSWORD_PROMPT_MARKERS + SHELL_PROMPT_MARKERS + INCORRECT_LOGIN_MARKERS,
            timeout=login_timeout,
            poke_newline_every=3,
        )

        if marker2 in INCORRECT_LOGIN_MARKERS:
            raise RuntimeError(f"Login failed for user '{BOARD_USER}':\n{text2}")

        if marker2 in PASSWORD_PROMPT_MARKERS:
            ser.write((BOARD_PASSWORD + "\r\n").encode())
            ser.flush()

            marker3, text3 = _read_until(
                ser,
                SHELL_PROMPT_MARKERS + INCORRECT_LOGIN_MARKERS,
                timeout=login_timeout,
                poke_newline_every=3,
            )

            if marker3 in INCORRECT_LOGIN_MARKERS or marker3 is None:
                raise RuntimeError(f"Login failed (bad password?):\n{text3}")
            return

        if marker2 in SHELL_PROMPT_MARKERS:
            return

        raise RuntimeError(f"Timed out waiting for shell after sending username:\n{text2}")

    raise RuntimeError(f"Board did not show login or shell prompt within {login_timeout}s:\n{text}")


def cmd_check(args):
    ser = open_serial(args.port, args.baud)
    try:
        ensure_shell(ser, login_timeout=args.login_timeout)
        print("✅ Board is REACHABLE and shell is ready")
        return 0
    except Exception as e:
        print(f"❌ Board not reachable: {e}")
        return 1
    finally:
        ser.close()


def cmd_run(args):
    ser = open_serial(args.port, args.baud)
    try:
        ensure_shell(ser, login_timeout=args.login_timeout)

        marker_tag = f"__CMD_DONE_MARKER__{int(time.time() * 1000)}__"
        wrapped_cmd = f"printf '\\n'; {args.cmd}; rc=$?; echo {marker_tag}$rc"

        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception:
            pass

        ser.write(b"\r\n")
        ser.flush()
        time.sleep(0.2)

        ser.write((wrapped_cmd + "\r\n").encode())
        ser.flush()

        idle_auto_enter = args.idle_seconds if args.auto_enter else None
        marker, text = _read_until(
            ser,
            [marker_tag],
            timeout=args.timeout,
            idle_auto_enter=idle_auto_enter,
        )

        if marker is None:
            text += _drain_briefly(ser, 0.5)
            print("❌ Timed out waiting for command to finish")
            print(text)
            return 1

        cleaned_text, marker_re = _strip_command_echo(text, args.cmd, marker_tag)
        print(cleaned_text)

        rc = 1
        m = marker_re.search(_normalize_output(text))
        if m:
            try:
                rc = int(m.group(1))
            except ValueError:
                rc = 1

        return rc
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return 1
    finally:
        ser.close()


def cmd_push(args):
    ser = open_serial(args.port, args.baud)
    try:
        ensure_shell(ser, login_timeout=args.login_timeout)

        with open(args.local_file, "rb") as f:
            data = f.read()

        if not data:
            print(f"❌ Local file is empty: {args.local_file}")
            return 1

        b64 = base64.b64encode(data).decode("ascii")
        remote_b64_path = args.remote_path + ".b64"
        push_marker = f"__PUSH_OK__{int(time.time() * 1000)}__"

        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception:
            pass

        ser.write((f"rm -f {remote_b64_path} {args.remote_path}\r\n").encode())
        ser.flush()
        time.sleep(0.2)
        _drain_briefly(ser, 0.2)

        chunk_size = 48
        for i in range(0, len(b64), chunk_size):
            chunk = b64[i:i + chunk_size]
            ser.write((f"printf '%s' '{chunk}' >> {remote_b64_path}\r\n").encode())
            ser.flush()
            time.sleep(0.12)
            _drain_briefly(ser, 0.08)

        verify_and_decode = (
            f"test -s {remote_b64_path} && "
            f"base64 -d {remote_b64_path} > {args.remote_path} && "
            f"chmod +x {args.remote_path} && "
            f"test -s {args.remote_path} && "
            f"echo {push_marker}"
        )

        ser.write((verify_and_decode + "\r\n").encode())
        ser.flush()

        marker, text = _read_until(ser, [push_marker], timeout=args.timeout)

        if marker is None:
            print(f"❌ File did not land correctly on {args.remote_path}")
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
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--serial", help="Unique board serial number (udev by-id)")
    common.add_argument("--port", help="Direct port path, e.g. /dev/ttyUSB0")
    common.add_argument("--baud", type=int, default=115200)
    common.add_argument("--timeout", type=int, default=30, help="Command/transfer completion timeout (s)")
    common.add_argument(
        "--login-timeout",
        type=int,
        default=LOGIN_TIMEOUT_DEFAULT,
        help=f"How long to wait for the board to boot and show a login/shell prompt (default: {LOGIN_TIMEOUT_DEFAULT}s).",
    )

    p = argparse.ArgumentParser(parents=[common])
    sub = p.add_subparsers(dest="command", required=True)

    sp_check = sub.add_parser("check", parents=[common])
    sp_check.set_defaults(func=cmd_check)

    sp_run = sub.add_parser("run", parents=[common])
    sp_run.add_argument("--cmd", required=True)
    sp_run.add_argument("--auto-enter", action="store_true", default=False)
    sp_run.add_argument("--idle-seconds", type=float, default=4.0)
    sp_run.set_defaults(func=cmd_run)

    sp_push = sub.add_parser("push", parents=[common])
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
