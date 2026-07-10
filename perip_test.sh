#!/bin/bash
#
# perip_test.sh — SAME script used to test BOTH boards.
# Jenkins pushes this one file to each board (over its own serial/USB
# console, e.g. ttyUSB0 -> Board1, ttyUSB1 -> Board2) and runs:
#   ./perip_test.sh board1
#   ./perip_test.sh board2
# Only change vs the instructor's original: BOARD_ID picks a per-board
# report file so Board1 and Board2 results never overwrite each other.
# All test functions, order, and pin mappings below are unchanged.

BOARD_ID="${1:-board1}"

# /tmp is tmpfs and writable on essentially every embedded Linux image,
# even when the rootfs itself is read-only. Use it directly instead of
# probing directories (busybox `test -w` can misreport on some rootfs
# setups, which is what silently broke the previous auto-detect version).
REPORT_DIR=/tmp
mkdir -p "$REPORT_DIR" 2>/dev/null
REPORT_FILE="$REPORT_DIR/testreport_${BOARD_ID}.txt"

echo "DEBUG: BOARD_ID=$BOARD_ID"
echo "DEBUG: REPORT_FILE=$REPORT_FILE"
if ! : > "$REPORT_FILE" 2>/tmp/perip_write_err.txt; then
    echo "FATAL: cannot write to $REPORT_FILE"
    cat /tmp/perip_write_err.txt 2>/dev/null
    echo "DEBUG: mount table:"
    cat /proc/mounts 2>/dev/null
    exit 1
fi

# Define the function gpio_led_switch_test
gpio_led_switch_test() {
    user_gpio_pin=$1
    user_gpio_sw=$2
    type=$3
    gpio_test=pass

    if [ "$type" == "gpio" ]; then    
        read -p "Please connect an LED to GPIO pin and press Enter to continue..." dummy
    elif [ "$type" == "DIN" ]; then
        read -p "Please feed 5V to DIN pin and press Enter to continue..." dummy
    elif [ "$type" == "switch" ]; then
        read -p "Please press and hold the switch now..." dummy
    fi

    echo "Exporting GPIO $user_gpio_pin" >> "$REPORT_FILE"
    echo "$user_gpio_pin" > /sys/class/gpio/export 2>/dev/null

    if [ "$type" == "gpio" ] || [ "$type" == "led" ] || [ "$type" == "DOUT" ]; then
        echo "Setting direction to out" >> "$REPORT_FILE"
        echo "out" > /sys/class/gpio/$user_gpio_sw/direction 2>/dev/null
    else
        echo "Setting direction to in" >> "$REPORT_FILE"
        echo "in" > /sys/class/gpio/$user_gpio_sw/direction 2>/dev/null
    fi

    if [ "$type" == "gpio" ] || [ "$type" == "DOUT" ]; then
        echo "Turning ON GPIO" >> "$REPORT_FILE"
        echo 1 > /sys/class/gpio/$user_gpio_sw/value 2>/dev/null
        sleep 1
        echo "Turning OFF GPIO" >> "$REPORT_FILE"
        echo 0 > /sys/class/gpio/$user_gpio_sw/value 2>/dev/null
    elif [ "$type" == "led" ]; then
        echo "Turning ON LED" >> "$REPORT_FILE"
        echo 0 > /sys/class/gpio/$user_gpio_sw/value 2>/dev/null
        sleep 1
        echo "Turning OFF LED" >> "$REPORT_FILE"
        echo 1 > /sys/class/gpio/$user_gpio_sw/value 2>/dev/null
        
    elif [ "$type" == "DIN" ] || [ "$type" == "gpio" ]; then
        val=$(cat /sys/class/gpio/$user_gpio_sw/value)
        echo "Read value: $val" >> "$REPORT_FILE"
        if [ "$val" -eq 1 ]; then
            echo "HIGH input detected" >> "$REPORT_FILE"
        else
            echo "LOW input or no signal" >> "$REPORT_FILE"
            gpio_test=fail
        fi
    fi

    echo "Unexporting GPIO $user_gpio_pin" >> "$REPORT_FILE"
    echo "$user_gpio_pin" > /sys/class/gpio/unexport 2>/dev/null

    if [ "$gpio_test" == "pass" ]; then
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
        echo " GPIO $user_gpio_sw : TEST SUCCESS" >> "$REPORT_FILE"
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
    else
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
        echo " GPIO $user_gpio_sw : TEST FAILED" >> "$REPORT_FILE"
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
    fi
    echo "==================================================================================================" >> "$REPORT_FILE"
    echo >> "$REPORT_FILE"
}

# Define the function gpio_switch_test
gpio_switch_test() {
    user_gpio_pin=$1
    user_gpio_sw=$2
    type=$3
    gpio_test=fail  # Default to fail unless switch is pressed

    echo "Exporting GPIO $user_gpio_pin" >> "$REPORT_FILE"
    echo "$user_gpio_pin" > /sys/class/gpio/export 2>/dev/null

    echo "Setting direction to in" >> "$REPORT_FILE"
    echo "in" > /sys/class/gpio/$user_gpio_sw/direction 2>/dev/null

    if [ "$type" == "switch" ]; then
        echo "Please press and hold the switch now..."
        echo
        echo "Wait 10 seconds to press the switch.. Don't press Enter Button "
        sleep 10  # Wait 3 seconds for user to press the switch
        val=$(cat /sys/class/gpio/$user_gpio_sw/value)
        echo "Read value: $val" >> "$REPORT_FILE"

        if [ "$val" -eq 0 ]; then
            echo "Switch press detected (value: $val)" >> "$REPORT_FILE"
            gpio_test=pass
        else
            echo "No switch press detected (value: $val)" >> "$REPORT_FILE"
        fi
    fi

    echo "Unexporting GPIO $user_gpio_pin" >> "$REPORT_FILE"
    echo "$user_gpio_pin" > /sys/class/gpio/unexport 2>/dev/null

    if [ "$gpio_test" == "pass" ]; then
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
        echo " GPIO $user_gpio_sw : TEST SUCCESS" >> "$REPORT_FILE"
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
    else
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
        echo " GPIO $user_gpio_sw : TEST FAILED" >> "$REPORT_FILE"
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
    fi
    echo "==================================================================================================" >> "$REPORT_FILE"
    echo >> "$REPORT_FILE"
}

eeprom_test() {

    # Set the I2C bus and device addresses
    I2C_BUS=$1
    EEPROM_ADDR=$2
    test_eeprom=pass

    # Define the test data to write to the EEPROM
    TEST_DATA="Welcome to phytec india.!"

    # Write the test data to the EEPROM
    echo "Writing $TEST_DATA  to EEPROM" >> "$REPORT_FILE"
    echo -n "$TEST_DATA" | tee /sys/class/i2c-dev/i2c-$I2C_BUS/device/0-0050/eeprom >/dev/null

    # Read the test data back from the EEPROM
    echo "Reading test data from EEPROM" >> "$REPORT_FILE"
    READ_DATA=$(dd if=/sys/class/i2c-dev/i2c-$I2C_BUS/device/0-0050/eeprom bs=1 count=${#TEST_DATA} 2>/dev/null)
    if [ $? -ne 0 ]; then
        echo "Error: Failed to read data from EEPROM" >> "$REPORT_FILE"
        test_eeprom=fail
    else
        echo " EEPROM read : $READ_DATA " >> "$REPORT_FILE"
    fi

    # Verify the read data matches the test data
    if [ "$TEST_DATA" == "$READ_DATA" ]; then
        echo "EEPROM test passed" >> "$REPORT_FILE"
    else
        echo "EEPROM test failed" >> "$REPORT_FILE"
        test_eeprom=fail
    fi

        # Check the test status
    if [ "$test_eeprom" != "fail" ]; then
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
        echo " EEPROM I2C$I2C_BUS : TEST SUCCESS" >> "$REPORT_FILE"
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
    else
       echo "----------------------------------------------------------" >> "$REPORT_FILE"
       echo " EEPROM I2C$I2C_BUS : TEST FAILED" >> "$REPORT_FILE"
       echo "----------------------------------------------------------" >> "$REPORT_FILE"

    fi


}


usb_sdcard_test() {
 
    stoarge_type=$1
    if [ "$stoarge_type" == "usb" ]; then
        # Prompt the user to connect usb device
        read -p "Connect usb mass storage pendrive to usb host port and then press enter to proceed : " usb_dummy
        read -p "Please enter attached usb device name (eg. /dev/sda1) : " STORAGE_PATH
    else
        # Prompt the user to connect usb device
        read -p "Insert sdcard into sdcard slot and then press enter to proceed : " usb_dummy
        STORAGE_PATH=/dev/mmcblk1p1
    fi

    # Mount the USB device
    mount $STORAGE_PATH /mnt

    # Check if the mount was successful
    if [ $? -eq 0 ]; then
        echo "STORAGE device mounted successfully." >> "$REPORT_FILE"
    else
        echo "Mount failed." >> "$REPORT_FILE"
        test_usb=fail
    fi

    # Create a test file on the USB device
    echo "Test file on STORAGE device" > /mnt/test_file.txt

    # Check if the test file was created successfully
    if [ $? -eq 0 ]; then
        echo "Test file created successfully." >> "$REPORT_FILE"
    else
        echo "Test file creation failed." >> "$REPORT_FILE"
        test_usb=fail
    fi

    # Unmount the USB device
    umount $STORAGE_PATH

    # Check if the unmount was successful
    if [ $? -eq 0 ]; then
        echo "STORAGE device unmounted successfully." >> "$REPORT_FILE"
    else
        echo "Unmount failed." >> "$REPORT_FILE"
        test_usb=fail
    fi

    # Confirm that the USB device is no longer mounted
    if grep -qs '/mnt' /proc/mounts; then
        echo "Error: STORAGE device still mounted." >> "$REPORT_FILE"
        test_usb=fail
    fi

    # Check the test status
    if [ "$test_usb" != "fail" ]; then
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
        echo " STORAGE $STORAGE_PATH : TEST SUCCESS" >> "$REPORT_FILE"
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
    else
       echo "----------------------------------------------------------" >> "$REPORT_FILE"
       echo " STORAGE $STORAGE_PATH : TEST FAILED" >> "$REPORT_FILE"
       echo "----------------------------------------------------------" >> "$REPORT_FILE"
    fi
}



Ethernet_test() {

    # Set the device name and IP address of the board
    device_name=$1
    test_eth=pass

    # Prompt the user to connect ethernet cable
    read -p "Please connect ethernet cable whose other end is connected to router and then press enter to proceed : " eth_dummy

    # Check if the device exists
    if ! ifconfig -a | grep $device_name > /dev/null; then
      echo "Error: device $device_name does not exist" >> "$REPORT_FILE"
      test_eth=fail
    fi

    # Check if an IP address has been assigned
    if ! ifconfig $device_name | grep "inet addr" > /dev/null; then
        echo "No IP address assigned to device $device_name, attempting to acquire one using udhcpc" >> "$REPORT_FILE"
        udhcpc -i $device_name -t 5 -T 1 -A 10 -q -n
    fi

    # Check if udhcpc was successful in acquiring an IP address
    if ! ifconfig $device_name | grep "inet addr" > /dev/null; then
        echo "Error: failed to acquire IP address using udhcpc" >> "$REPORT_FILE"
        test_eth=fail
    fi

    # Ping the default gateway
    ping -c 5 8.8.8.8 >> "$REPORT_FILE"

    if [ $? -eq 0 ]; then
        echo "Ethernet connection is up" >> "$REPORT_FILE"
    else
        test_eth=fail
        echo "Ethernet connection is down" >> "$REPORT_FILE"
    fi
 
    # Check the test status
    if [ "$test_eth" != "fail" ]; then
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
        echo " ethernet $device_name : TEST SUCCESS" >> "$REPORT_FILE"
        echo "----------------------------------------------------------" >> "$REPORT_FILE"
    else
       echo "----------------------------------------------------------" >> "$REPORT_FILE"
       echo " ethernet $device_name : : TEST FAILED" >> "$REPORT_FILE"
       echo "----------------------------------------------------------" >> "$REPORT_FILE"
    fi
}

uart_test() {
    UART_DEVICE=$1
    uart_type=$2
    BAUD_RATE="115200"
    RESPONSE_FILE="/data/uart_response.txt"
    test_uart=pass

    if [ "$uart_type" = "ttl" ]; then
        echo " Please connect uart3(TTL) port to your Linux pc with the help of USB-TTL converter"
        echo " connect M2(14) pin to RX of TTL converter and M2(15) pin to TX of TTL and gnd to gnd"
        read -p "Now open the serial port in LINUX PC with microcom and then press enter to proceed : " uart_dummy
        echo "If 'Testing UART device' message received in microcom then send back 'Testing UART Ok' within 10 sec "
    elif [ "$uart_type" = "RS232" ]; then
        echo " Please connect uart2(RS232) port to another A5D2X or rbimx6ul rs232 port"
        read -p "Now open the serial port in LINUX PC with microcom and then press enter to proceed : " uart_dummy
        echo "If 'Testing UART device' message received in microcom then send back 'Testing UART Ok' within 10 sec."
    else
        echo " Please connect uart6(RS485) port to  A5D2X or another rbimx6ul rs485 port"
        read -p "Now open the serial port in RS485 device with microcom and then press enter to proceed : " uart_dummy
        echo "If 'Testing UART device' message received in microcom then send back 'Testing UART Ok' within 10 sec"
    fi

    # Check if UART device file exists
    if [ ! -e "$UART_DEVICE" ]; then
        echo "UART device $UART_DEVICE not found" >> "$REPORT_FILE"
        echo "Verify that $UART_DEVICE is present" >> "$REPORT_FILE"
        test_uart=fail
        return
    fi

    # Configure UART port
    stty -F "$UART_DEVICE" $BAUD_RATE cs8 -cstopb -parity -icanon

    # Clear previous response file
    rm -f "$RESPONSE_FILE"

    # Start background receiver
    cat "$UART_DEVICE" > "$RESPONSE_FILE" &
    cat_pid=$!

    # Transmit test message
    echo -ne "Testing UART device\r\n" > "$UART_DEVICE"

    # Wait up to 10 seconds for response
    for i in $(seq 1 30); do
        if grep -q "Testing UART Ok" "$RESPONSE_FILE" 2>/dev/null; then
            break
        fi
        sleep 1
    done

    # Kill background reader
    kill "$cat_pid" 2>/dev/null

    # Verify response
    if grep -q "Testing UART Ok" "$RESPONSE_FILE" 2>/dev/null; then
        echo "UART device test passed" >> "$REPORT_FILE"
    else
        echo "UART device test failed" >> "$REPORT_FILE"
        test_uart=fail
    fi

    # Report results
    echo "----------------------------------------------------------" >> "$REPORT_FILE"
    if [ "$test_uart" = "pass" ]; then
        echo " UART $UART_DEVICE : TEST SUCCESS" >> "$REPORT_FILE"
    else
        echo " UART $UART_DEVICE : TEST FAILED" >> "$REPORT_FILE"
    fi
    echo "----------------------------------------------------------" >> "$REPORT_FILE"
}


adc_test() {
    adc_pin=$1
    test_adc=pass
    adc_resolution=4095

    echo "Please connecte the  potentiometer to ADC pin to any position and press Enter to proceed"
    read -p "Press Enter to start the ADC test... " adc_dummy

    adc_value1=$(cat /sys/bus/iio/devices/iio:device0/in_voltage6_raw 2>/dev/null)

    if [ -z "$adc_value1" ]; then
        echo "Error: Failed to read initial ADC value" >> "$REPORT_FILE"
        test_adc=fail
    elif [ "$adc_value1" -lt 0 ] || [ "$adc_value1" -gt $adc_resolution ]; then
        echo "Error: Initial ADC value out of valid range (0–4095)" >> "$REPORT_FILE"
        test_adc=fail
    else
        echo "Initial ADC value: $adc_value1" >> "$REPORT_FILE"
        echo "Now change the potentiometer position. Waiting for 10 seconds..."
        sleep 10

        adc_value2=$(cat /sys/bus/iio/devices/iio:device0/in_voltage6_raw 2>/dev/null)

        if [ -z "$adc_value2" ]; then
            echo "Error: Failed to read final ADC value" >> "$REPORT_FILE"
            test_adc=fail
        elif [ "$adc_value2" -lt 0 ] || [ "$adc_value2" -gt $adc_resolution ]; then
            echo "Error: Final ADC value out of valid range (0–4095)" >> "$REPORT_FILE"
            test_adc=fail
        else
            echo "Final ADC value: $adc_value2" >> "$REPORT_FILE"

            diff=$((adc_value1 - adc_value2))
            [ "$diff" -lt 0 ] && diff=$(( -1 * diff ))

            if [ "$diff" -ge 100 ]; then
                echo "ADC value changed by $diff (>= 100)" >> "$REPORT_FILE"
                echo "----------------------------------------------------------" >> "$REPORT_FILE"
                echo " adc iio:device0 : TEST SUCCESS" >> "$REPORT_FILE"
                echo "----------------------------------------------------------" >> "$REPORT_FILE"
            else
                echo "ADC value changed by $diff (< 100)" >> "$REPORT_FILE"
                echo "----------------------------------------------------------" >> "$REPORT_FILE"
                echo " adc iio:device0 : TEST FAILED" >> "$REPORT_FILE"
                echo "----------------------------------------------------------" >> "$REPORT_FILE"
                test_adc=fail
            fi
        fi
    fi

    echo "Testing ADC GPIO1_IO03 ends" >> "$REPORT_FILE"
    echo "====================================================================================================" >> "$REPORT_FILE"
    echo >> "$REPORT_FILE"
}


pwm_test() {
    test_pwm=pass

    echo  "Start the test and suppress output, run in background "
    ./PWM 100 1 > /dev/null 2>&1 &
    pwm_pid=$!

    # Wait for 10 seconds
    sleep 10

    # Kill the background process
    kill $pwm_pid 2>/dev/null

    # Add result hints to report
    echo >> "$REPORT_FILE"
    echo "-----------------------------------------------------------------" >> "$REPORT_FILE"
    echo " wathc the PWM LED if britness incress PWM SUCCESS or PWM FAILED " >> "$REPORT_FILE"
    echo "-----------------------------------------------------------------" >> "$REPORT_FILE"
}

#================================================== script init =======================================


# removing report file if already exists otherwise it concates 
if test -f "$REPORT_FILE"; then
    rm "$REPORT_FILE"
fi

# capturing boot log
dmesg >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo Peripherals tests >> "$REPORT_FILE"
echo ----------------- >> "$REPORT_FILE"
echo >> "$REPORT_FILE"

echo "Onboard USER LED Tests"
echo "---------------------"
echo
echo "Testing userled1 PC13"
echo "=========================== Testing userled1 PC13 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 77 PC13 led
echo

echo "Testing userled2 PC17"
echo "=========================== Testing userled2 PC17 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 81 PC17 led
echo

echo "Testing userled3 PC19"
echo "=========================== Testing userled3 PC19 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 83 PC19 led
echo

echo "Onboard USER SWITCH TEST"
echo "--------------------------"
echo
echo "Testing userswitch PC12"
echo "======================================== Testing userswitch PC12 ====================================" >> "$REPORT_FILE"
gpio_switch_test 76 PC12 switch
echo "Testing USER SWITCH ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo

echo "DIN Tests"
echo "-----------------"
echo "Testing DIN1 PC20"
echo "=========================== Testing DIN1 PC20 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 84 PC20 DIN
echo

echo "Testing DIN2 PC24"
echo "=========================== Testing DIN2 PC24 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 88 PC24 DIN
echo

echo "Testing DIN3 PC15"
echo "=========================== Testing DIN3 PC15 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 79 PC15 DIN
echo

echo "Testing DIN4 PC22"
echo "=========================== Testing DIN4 PC22 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 86 PC22 DIN
echo

echo "DOUT Tests"
echo "------------------"
echo "Testing DOUT1 PA17"
echo "=========================== Testing DOUT1  PA17 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 17 PA17 DOUT
echo

echo "Testing DOUT2 PA14"
echo "=========================== Testing DOUT2 PA14 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 14 PA14 DOUT
echo

echo "Testing DOUT3 PA16"
echo "=========================== Testing DOUT3 PA16 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 16 PA16 DOUT
echo

echo "Testing DOUT4 PD1"
echo "=========================== Testing DOUT4 PD1 ===========================" >> "$REPORT_FILE"
gpio_led_switch_test 97 PD1 DOUT
echo

# Ethernet test case
echo "ETHERNET Test"
echo "-------------"
echo
echo "Testing Ethernet 0 " 
echo -n "======================================== Testing Ethernet 0  ====================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
Ethernet_test eth0 
echo "Testing Ethernet 0 ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo "Testing Ethernet 0 ends"
echo


# usb test case
echo "USB Test"
echo "-------------"
echo
echo "Testing usb 0 " 
echo -n "======================================== Testing USB 0  ====================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
usb_sdcard_test usb
echo "Testing USB 0 ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo "Testing USB 0 ends"
echo

# sdcard test case
echo "sdcard Test"
echo "-----------"
echo
echo "Testing sdcard " 
echo -n "======================================== Testing sdcard  ====================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
usb_sdcard_test sdcard
echo "Testing sdcard ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo "Testing sdcard ends"
echo


# EEPROM test case
echo "EEPROM Test"
echo "-----------"
echo
echo "Testing EEPROM I2C0" 
echo -n "======================================== Testing EEPROM I2C0 ====================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
eeprom_test 0 0x50
echo "Testing EEPROM ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo "Testing EEPROM ends"
echo

# TTL UART3 Test
echo " TTL UART3Test"
echo "---------------"
echo
echo "======================================== Testing UART3(TTL)  ====================================" >> "$REPORT_FILE"
uart_test /dev/ttyS3 ttl
echo "Testing UART3(TTL) ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo

# RS232 UART2 Test
echo " RS232 UART2 Test"
echo "-----------------"
echo
echo "======================================== Testing UART2(RS232)  ====================================" >> "$REPORT_FILE"
uart_test /dev/ttyS4 RS232
echo "Testing UART2(RS232) ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo


# RS232 UART4 Test
echo " RS232 UART4 Test"
echo "------------------"
echo
echo "======================================== Testing UART4(RS232)  ====================================" >> "$REPORT_FILE"
uart_test /dev/ttyS1 RS232
echo "Testing UART4(RS232) ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo
echo

# RS485 UART6 Test
echo " RS485 UART6 Test"
echo "-----------------"
echo
echo "======================================== Testing UART6(RS485)  ====================================" >> "$REPORT_FILE"
uart_test /dev/ttyS2 RS485
echo "Testing UART6(RS485) ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo
echo

# PWM test case
echo "PWM Test"
echo "----------"
echo
echo "Testing PWM"
echo "======================================== Testing PWM  ====================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
pwm_test
echo "Testing PWM ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo "Testing PWM ends"
echo
echo

# ADC test case
echo "ADC test"
echo "-----------------"
echo
echo "======================================== Testing ADC GPIO1_IO03 ====================================" >> "$REPORT_FILE"
adc_test 3
echo "Testing ADC GPIO1_IO03 ends" >> "$REPORT_FILE"
echo "====================================================================================================" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"
echo
echo
