#!/usr/bin/env python3
"""
serial_helper.py — talk to a board over its FTDI USB-serial console instead of
SSH/ngrok, since the boards have no network stack (no IP, no SSH port).

Subcommands:
  check  --port /dev/ttyUSB0 --baud 115200
      Confirms the serial console is present and gives back a live shell prompt.

  run    --port /dev/ttyUSB0 --baud 115200 --cmd "some shell command" [--timeout 60]
      Sends one command, captures stdout and the real exit code (via `; echo
      MARKER$?`), prints stdout, and exits with that same code so Jenkins'
      returnStatus: true keeps working exactly like it did with ssh.

  push   --port /dev/ttyUSB0 --baud 115200 --local-file perip_test.sh \
         --remote-path /tmp/perip_test.sh [--timeout 60]
      Streams a text file to the board line-by-line as a `cat > file << EOF`
      heredoc over the serial link (no scp/zmodem needed for a plain script),
      then chmod +x's it and confirms it landed.

Exit codes mirror what the Jenkinsfile expects: 0 = PASS, non-zero = FAIL.
"""
import argparse
import re
import sys
import time

try:
    import serial
except ImportError:
    print("❌ pyserial not installed. Run: pip3 install pyserial --break-system-packages")
    sys.exit(1)

END_MARKER = "___CMD_DONE___"
HEREDOC_MARKER = "___JENKINS_EOF___"


def open_port(port, baud, timeout=5):
    ser = serial.Serial(port, baudrate=int(baud), timeout=timeout)
    time.sleep(0.5)
    ser.reset_input_buffer()
    return ser


def wake_shell(ser):
    # Nudge the console so we're talking to a live shell, not a stale buffer.
    ser.write(b"\r\n")
    time.sleep(0.3)
    ser.read(ser.in_waiting or 1)


def send_line(ser, line):
    ser.write((line + "\n").encode())


def read_until(ser, marker, timeout=30):
    buf = ""
    start = time.time()
    while time.time() - start < timeout:
        chunk = ser.read(ser.in_waiting or 1).decode(errors="ignore")
        if chunk:
            buf += chunk
            if marker in buf:
                break
        else:
            time.sleep(0.05)
    return buf


def run_command(ser, cmd, timeout=60):
    send_line(ser, f"{cmd}; echo {END_MARKER}$?")
    raw = read_until(ser, END_MARKER, timeout=timeout)

    exit_code = 1
    body_lines = []
    for line in raw.splitlines():
        m = re.search(rf"{END_MARKER}(\d+)", line)
        if m:
            exit_code = int(m.group(1))
        elif line.strip() and cmd not in line:  # drop the echoed command line
            body_lines.append(line)

    return "\n".join(body_lines), exit_code


def cmd_check(args):
    try:
        ser = open_port(args.port, args.baud, timeout=3)
        wake_shell(ser)
        out, rc = run_command(ser, "echo PING_OK", timeout=8)
        ser.close()
        if "PING_OK" in out:
            print(f"✅ Serial console reachable on {args.port} @ {args.baud} baud")
            sys.exit(0)
        print(f"❌ Port opened but no shell response on {args.port}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Could not open serial port {args.port}: {e}")
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


def cmd_push(args):
    try:
        with open(args.local_file, "r") as f:
            content = f.read()

        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser)

        send_line(ser, f"cat > {args.remote_path} << '{HEREDOC_MARKER}'")
        time.sleep(0.2)
        for line in content.splitlines():
            send_line(ser, line)
            time.sleep(0.02)  # small gate so the board's UART buffer keeps up
        send_line(ser, HEREDOC_MARKER)
        time.sleep(0.5)
        ser.read(ser.in_waiting or 1)  # drain the heredoc echo

        out, rc = run_command(
            ser, f"chmod +x {args.remote_path} && ls -l {args.remote_path}"
        )
        print(out)
        ser.close()

        if rc == 0 and "No such file" not in out:
            sys.exit(0)
        print(f"❌ File did not land correctly on {args.remote_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Serial push failed on {args.port}: {e}")
        sys.exit(1)


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
