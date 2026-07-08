import os
import glob

def get_port_by_serial(serial_number):
    """Dynamically find the port path for a given serial number."""
    # Common path for USB-serial devices by ID
    path = f"/dev/serial/by-id/*{serial_number}*"
    devices = glob.glob(path)
    if not devices:
        raise Exception(f"Device with serial {serial_number} not found in /dev/serial/by-id/")
    
    # Resolve the symlink to the actual /dev/ttyUSBx path
    return os.path.realpath(devices[0])

# Update your main() function:
def main():
    p = argparse.ArgumentParser()
    # Add an optional serial argument
    p.add_argument("--serial", help="Unique board serial number")
    p.add_argument("--port", help="Direct port path")
    
    # ... (rest of your existing subcommands) ...
    
    args = p.parse_args()
    
    # Logic to resolve port if serial is provided
    if args.serial:
        args.port = get_port_by_serial(args.serial)
    elif not args.port:
        print("❌ Error: Must provide either --serial or --port")
        sys.exit(1)
        
    args.func(args)
