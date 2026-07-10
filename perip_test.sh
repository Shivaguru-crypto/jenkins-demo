#!/bin/sh
# perip_test.sh — Option A: automated peripheral presence/accessibility checks.
# No manual input required (no LED/switch presses) — safe for unattended CI.

echo "=== Peripheral Test (Automated, Option A) ==="

echo ""
echo "--- GPIO ---"
if [ -d /sys/class/gpio ]; then
    echo "PASS: /sys/class/gpio exists"
    ls /sys/class/gpio
else
    echo "INFO: /sys/class/gpio not present on this kernel/image"
fi

if ls /dev/gpiochip* >/dev/null 2>&1; then
    echo "PASS: gpiochip device(s) found:"
    ls /dev/gpiochip*
else
    echo "INFO: no /dev/gpiochip* devices found"
fi

echo ""
echo "--- UART / Serial Ports ---"
if ls /dev/ttyS* >/dev/null 2>&1; then
    echo "PASS: UART devices found:"
    ls /dev/ttyS*
else
    echo "FAIL: no /dev/ttyS* devices found"
fi

echo ""
echo "--- Storage (eMMC/SD) ---"
if ls /dev/mmcblk* >/dev/null 2>&1; then
    echo "PASS: mmcblk storage device(s) found:"
    ls /dev/mmcblk*
    echo "--- Partition info ---"
    cat /proc/partitions 2>/dev/null | grep mmcblk
else
    echo "FAIL: no /dev/mmcblk* devices found"
fi

echo ""
echo "--- Recent kernel messages (last 30 lines) ---"
dmesg 2>/dev/null | tail -5 || echo "INFO: dmesg not accessible (permissions or not present)"

echo ""
echo "=== Peripheral Test Completed (Option A) ==="
