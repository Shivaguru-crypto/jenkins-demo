#!/usr/bin/env python3
"""
serial_helper.py v4.2
- END_MARKER = __DONE__ (short, avoids 80-col wrap)
- run_command: after sending cmd, drains ALL output until marker found
  with a generous inter-chunk idle wait to handle slow/bursty board output
- wake_shell: Ctrl+C + HEREDOC_EOF recovery, reads with in_waiting polling
"""
import argparse, re, subprocess, sys, time
try:
    import serial, serial.tools.list_ports
except ImportError:
    print("pip3 install pyserial --break-system-packages"); sys.exit(1)

END_MARKER  = "__DONE__"
PUSH_MARKER = "__PUSH__"
HEREDOC_EOF = "___JENKINS_EOF___"
BOARD_LOGIN_USER     = "root"
BOARD_LOGIN_PASSWORD = ""

def resolve_port(p):
    if p.startswith("/dev/"): return p
    for port in serial.tools.list_ports.comports():
        if port.serial_number == p: return port.device
    print(f"No device with serial number '{p}'"); sys.exit(1)

def open_port(port, baud, timeout=5):
    resolved = resolve_port(port)
    ser = serial.Serial()
    ser.port = resolved; ser.baudrate = int(baud); ser.timeout = timeout
    ser.dtr = False; ser.rts = False; ser.dsrdtr = False
    ser.open()
    try: subprocess.run(["stty","-F",resolved,"-hupcl"],check=False,capture_output=True)
    except: pass
    time.sleep(0.3)
    return ser

def read_until_any(ser, markers, timeout=5):
    """Non-blocking poll until any marker found or timeout."""
    buf = ""; start = time.time()
    while time.time()-start < timeout:
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
    Uses idle-gap detection: keeps reading as long as data keeps arriving,
    even if no data for up to 5s at a time (handles large dmesg output).
    """
    buf = ""
    start = time.time()
    last_data = time.time()
    idle_limit = 10.0  
    while time.time() - start < timeout:
        n = ser.in_waiting
        if n:
            chunk = ser.read(n).decode(errors="ignore")
            buf += chunk
            last_data = time.time()
            if marker in buf:
                break
        else:
            # No data right now — check idle gap
            if buf and (time.time() - last_data) > idle_limit:
                # Board has gone silent and we have some output — stop waiting
                break
            time.sleep(0.05)
    return buf

def send_line(ser, line):
    ser.write((line+"\n").encode())

def wake_shell(ser):
    print("   [wake_shell] sending recovery sequence")
    ser.write(b"\x03");                        time.sleep(0.2)
    ser.write(b"\r\n");                        time.sleep(0.1)
    ser.write((HEREDOC_EOF+"\n").encode());    time.sleep(0.2)
    ser.write(b"\r\n");                        time.sleep(0.1)

    buf, m = read_until_any(ser, ["login:", "#", "$"], timeout=4)
    print(f"   [wake_shell] buf={buf!r:.120} matched={m!r}")

    if m and "login:" in m:   _do_login(ser); return
    if m:                     print("   [wake_shell] shell confirmed"); return

    ser.write(b"\r\n")
    buf2, m2 = read_until_any(ser, ["login:", "#", "$"], timeout=4)
    print(f"   [wake_shell] nudge buf={buf2!r:.120} matched={m2!r}")
    if m2 and "login:" in m2: _do_login(ser); return
    if m2:                    print("   [wake_shell] shell confirmed after nudge"); return
    print("   [wake_shell] WARNING: no prompt — proceeding anyway")

def _do_login(ser):
    print(f"   [wake_shell] logging in as '{BOARD_LOGIN_USER}'")
    ser.write((BOARD_LOGIN_USER+"\n").encode()); time.sleep(1.0)
    resp, _ = read_until_any(ser, ["password:","assword","#","$"], timeout=3)
    if "assword" in resp.lower():
        ser.write((BOARD_LOGIN_PASSWORD+"\n").encode()); time.sleep(1.0)
        read_until_any(ser, ["#","$"], timeout=3)
    ser.write(b"\r\n")
    _, m = read_until_any(ser, ["#","$"], timeout=3)
    print("   [wake_shell] logged in" if m else "   [wake_shell] WARNING: no shell after login")

def run_command(ser, cmd, timeout=60):
    """
    Send cmd and capture output + exit code.
    Prepends 'stty cols 200' to prevent 80-col terminal wrap corrupting output.
    """
    # Set wide terminal first so board doesn't wrap our marker line
    ser.write(b"stty cols 200\n")
    time.sleep(0.3)
    ser.read(ser.in_waiting)  # drain the stty echo — we don't need it

    send_line(ser, f"{cmd}; echo {END_MARKER}$?")
    raw = read_until(ser, END_MARKER, timeout=timeout)

    exit_code = 1; body = []; echoed = False
    for line in raw.splitlines():
        m = re.search(rf"{re.escape(END_MARKER)}(\d+)", line)
        if m: exit_code = int(m.group(1)); continue
        if not echoed and cmd in line: echoed = True; continue
        if line.strip(): body.append(line)
    return "\n".join(body), exit_code

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
    if path.startswith("/tmp/"):
        alt = "/run/"+path[5:]
        print(f"   [push] /tmp→/run: {alt}"); return alt
    return path

def cmd_push(args):
    remote = _writable(args.remote_path)
    try: content = open(args.local_file).read()
    except OSError as e: print(f"❌ {e}"); sys.exit(1)
    try:
        ser = open_port(args.port, args.baud, timeout=args.timeout)
        wake_shell(ser)

        # Widen terminal before heredoc so lines don't wrap during transfer
        ser.write(b"stty cols 200\n"); time.sleep(0.3)
        ser.read(ser.in_waiting)

        send_line(ser, f"cat > {remote} << '{HEREDOC_EOF}'")
        buf, m = read_until_any(ser, [">"], timeout=5)
        if not m:
            print(f"❌ no heredoc prompt. buf={buf!r}"); ser.close(); sys.exit(1)
        for line in content.splitlines():
            send_line(ser, line); time.sleep(0.06)
        send_line(ser, HEREDOC_EOF)
        buf2, m2 = read_until_any(ser, ["#","$"], timeout=15)
        if not m2:
            print(f"❌ heredoc did not close. buf={buf2!r}"); ser.close(); sys.exit(1)
        send_line(ser, f"echo {PUSH_MARKER}")
        confirm = read_until(ser, PUSH_MARKER, timeout=10)
        if PUSH_MARKER not in confirm:
            print(f"❌ push marker missing. buf={confirm!r}"); ser.close(); sys.exit(1)
        out, rc = run_command(ser, f"chmod +x {remote} && ls -l {remote}", timeout=10)
        print(out); ser.close()
        if rc == 0 and "No such file" not in out:
            print(f"✅ pushed to {remote}"); sys.exit(0)
        print(f"❌ file missing. out={out!r}"); sys.exit(1)
    except Exception as e:
        print(f"❌ push failed: {e}"); sys.exit(1)

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    pc = sub.add_parser("check")
    pc.add_argument("--port", required=True); pc.add_argument("--baud", default="115200")
    pc.set_defaults(func=cmd_check)
    pr = sub.add_parser("run")
    pr.add_argument("--port", required=True); pr.add_argument("--baud", default="115200")
    pr.add_argument("--cmd", required=True); pr.add_argument("--timeout", type=int, default=60)
    pr.set_defaults(func=cmd_run)
    pp = sub.add_parser("push")
    pp.add_argument("--port", required=True); pp.add_argument("--baud", default="115200")
    pp.add_argument("--local-file", required=True); pp.add_argument("--remote-path", required=True)
    pp.add_argument("--timeout", type=int, default=60)
    pp.set_defaults(func=cmd_push)
    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
