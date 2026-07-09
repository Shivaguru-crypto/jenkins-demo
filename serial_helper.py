"""
serial_helper.py — Lightweight serial console helper for embedded board testing.

Provides:
  - SerialHelper(port, baud, timeout) — initialize connection
  - send_command(cmd, timeout) — send command, capture response
  - close() — cleanup

Usage:
    sh = SerialHelper('/dev/ttyUSB0', 115200, 10)
    resp = sh.send_command("uname -a", timeout=2)
    print(resp)
    sh.close()
"""

import serial
import time
import sys


class SerialHelper:
    """Manage serial console interaction with embedded boards."""

    def __init__(self, port, baud, timeout=10):
        """
        Initialize serial connection.

        Args:
            port (str): Serial device path (e.g., '/dev/ttyUSB0')
            baud (int): Baud rate (e.g., 115200)
            timeout (int): Read timeout in seconds
        """
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None

        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baud,
                timeout=timeout,
                write_timeout=timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"[serial_helper] Connected to {port} @ {baud}", file=sys.stderr)
        except Exception as e:
            print(f"[serial_helper] Failed to open {port}: {e}", file=sys.stderr)
            raise

    def send_command(self, cmd, timeout=None):
        """
        Send a command and capture response.

        Args:
            cmd (str): Command to send (e.g., 'uname -a')
            timeout (int): Override timeout for this command (seconds)

        Returns:
            str: Response text (stdout captured from serial console)
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")

        actual_timeout = timeout if timeout is not None else self.timeout

        try:
            # Send command + newline
            self.ser.write((cmd + "\n").encode("utf-8", errors="replace"))
            self.ser.flush()

            # Capture response
            response = b""
            start_time = time.time()

            while time.time() - start_time < actual_timeout:
                try:
                    chunk = self.ser.read(256)
                    if chunk:
                        response += chunk
                except serial.SerialTimeoutException:
                    # Read timeout is expected; check wall-clock time
                    continue

                # Simple heuristic: if we got data and now see silence, assume done
                # (adjust threshold if needed)
                if response and len(chunk) == 0:
                    time.sleep(0.1)
                    # One more check for stragglers
                    chunk = self.ser.read(256)
                    if not chunk:
                        break

            result = response.decode("utf-8", errors="replace").strip()
            return result

        except Exception as e:
            print(f"[serial_helper] send_command failed: {e}", file=sys.stderr)
            raise

    def close(self):
        """Close serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"[serial_helper] Closed {self.port}", file=sys.stderr)


if __name__ == "__main__":
    """Quick test: python3 serial_helper.py /dev/ttyUSB0"""
    if len(sys.argv) < 2:
        print("Usage: python3 serial_helper.py <port> [baud]")
        sys.exit(1)

    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

    try:
        sh = SerialHelper(port, baud, timeout=5)
        
        # Send a carriage return to get a prompt
        print("Sending CR to get prompt...")
        resp = sh.send_command("", timeout=2)
        print(f"Response:\n{resp}\n")

        # Test: uname
        print("Sending: uname -a")
        resp = sh.send_command("uname -a", timeout=2)
        print(f"Response:\n{resp}\n")

        # Test: ls /sys/class/gpio
        print("Sending: ls /sys/class/gpio")
        resp = sh.send_command("ls -la /sys/class/gpio 2>/dev/null || echo 'not found'", timeout=2)
        print(f"Response:\n{resp}\n")

        sh.close()
        print("✅ Test complete")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
