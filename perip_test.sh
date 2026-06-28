#!/bin/bash

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

    echo "Exporting GPIO $user_gpio_pin" >> testreport.txt
    echo "$user_gpio_pin" > /sys/class/gpio/export 2>/dev/null

    if [ "$type" == "gpio" ] || [ "$type" == "led" ] || [ "$type" == "DOUT" ]; then
        echo "Setting direction to out" >> testreport.txt
        echo "out" > /sys/class/gpio/$user_gpio_sw/direction 2>/dev/null
    else
        echo "Setting direction to in" >> testreport.txt
        echo "in" > /sys/class/gpio/$user_gpio_sw/direction 2>/dev/null
    fi

    if [ "$type" == "gpio" ] || [ "$type" == "DOUT" ]; then
        echo "Turning ON GPIO" >> testreport.txt
        echo 1 > /sys/class/gpio/$user_gpio_sw/value 2>/dev/null
        sleep 1
        echo "Turning OFF GPIO" >> testreport.txt
        echo 0 > /sys/class/gpio/$user_gpio_sw/value 2>/dev/null
    elif [ "$type" == "led" ]; then
        echo "Turning ON LED" >> testreport.txt
        echo 0 > /sys/class/gpio/$user_gpio_sw/value 2>/dev/null
        sleep 1
        echo "Turning OFF LED" >> testreport.txt
        echo 1 > /sys/class/gpio/$user_gpio_sw/value 2>/dev/null
        
    elif [ "$type" == "DIN" ] || [ "$type" == "gpio" ]; then
        val=$(cat /sys/class/gpio/$user_gpio_sw/value)
        echo "Read value: $val" >> testreport.txt
        if [ "$val" -eq 1 ]; then
            echo "HIGH input detected" >> testreport.txt
        else
            echo "LOW input or no signal" >> testreport.txt
            gpio_test=fail
        fi
    fi

    echo "Unexporting GPIO $user_gpio_pin" >> testreport.txt
    echo "$user_gpio_pin" > /sys/class/gpio/unexport 2>/dev/null

    if [ "$gpio_test" == "pass" ]; then
        echo "----------------------------------------------------------" >> testreport.txt
        echo " GPIO $user_gpio_sw : TEST SUCCESS" >> testreport.txt
        echo "----------------------------------------------------------" >> testreport.txt
    else
        echo "----------------------------------------------------------" >> testreport.txt
        echo " GPIO $user_gpio_sw : TEST FAILED" >> testreport.txt
        echo "----------------------------------------------------------" >> testreport.txt
    fi
    echo "==================================================================================================" >> testreport.txt
    echo >> testreport.txt
}

# Define the function gpio_switch_test
gpio_switch_test() {
    user_gpio_pin=$1
    user_gpio_sw=$2
    type=$3
    gpio_test=fail  # Default to fail unless switch is pressed

    echo "Exporting GPIO $user_gpio_pin" >> testreport.txt
    echo "$user_gpio_pin" > /sys/class/gpio/export 2>/dev/null

    echo "Setting direction to in" >> testreport.txt
    echo "in" > /sys/class/gpio/$user_gpio_sw/direction 2>/dev/null

    if [ "$type" == "switch" ]; then
        echo "Please press and hold the switch now..."
        echo
        echo "Wait 10 seconds to press the switch.. Don't press Enter Button "
        sleep 10  # Wait 3 seconds for user to press the switch
        val=$(cat /sys/class/gpio/$user_gpio_sw/value)
        echo "Read value: $val" >> testreport.txt

        if [ "$val" -eq 0 ]; then
            echo "Switch press detected (value: $val)" >> testreport.txt
            gpio_test=pass
        else
            echo "No switch press detected (value: $val)" >> testreport.txt
        fi
    fi

    echo "Unexporting GPIO $user_gpio_pin" >> testreport.txt
    echo "$user_gpio_pin" > /sys/class/gpio/unexport 2>/dev/null

    if [ "$gpio_test" == "pass" ]; then
        echo "----------------------------------------------------------" >> testreport.txt
        echo " GPIO $user_gpio_sw : TEST SUCCESS" >> testreport.txt
        echo "----------------------------------------------------------" >> testreport.txt
    else
        echo "----------------------------------------------------------" >> testreport.txt
        echo " GPIO $user_gpio_sw : TEST FAILED" >> testreport.txt
        echo "----------------------------------------------------------" >> testreport.txt
    fi
    echo "==================================================================================================" >> testreport.txt
    echo >> testreport.txt
}

eeprom_test() {

    # Set the I2C bus and device addresses
    I2C_BUS=$1
    EEPROM_ADDR=$2
    test_eeprom=pass

    # Define the test data to write to the EEPROM
    TEST_DATA="Welcome to phytec india.!"

    # Write the test data to the EEPROM
    echo "Writing $TEST_DATA  to EEPROM" >> testreport.txt
    echo -n "$TEST_DATA" | tee /sys/class/i2c-dev/i2c-$I2C_BUS/device/0-0050/eeprom >/dev/null

    # Read the test data back from the EEPROM
    echo "Reading test data from EEPROM" >> testreport.txt
    READ_DATA=$(dd if=/sys/class/i2c-dev/i2c-$I2C_BUS/device/0-0050/eeprom bs=1 count=${#TEST_DATA} 2>/dev/null)
    if [ $? -ne 0 ]; then
        echo "Error: Failed to read data from EEPROM" >> testreport.txt
        test_eeprom=fail
    else
        echo " EEPROM read : $READ_DATA " >> testreport.txt
    fi

    # Verify the read data matches the test data
    if [ "$TEST_DATA" == "$READ_DATA" ]; then
        echo "EEPROM test passed" >> testreport.txt
    else
        echo "EEPROM test failed" >> testreport.txt
        test_eeprom=fail
    fi

        # Check the test status
    if [ "$test_eeprom" != "fail" ]; then
        echo "----------------------------------------------------------" >> testreport.txt
        echo " EEPROM I2C$I2C_BUS : TEST SUCCESS" >> testreport.txt
        echo "----------------------------------------------------------" >> testreport.txt
    else
       echo "----------------------------------------------------------" >> testreport.txt
       echo " EEPROM I2C$I2C_BUS : TEST FAILED" >> testreport.txt
       echo "----------------------------------------------------------" >> testreport.txt

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
        echo "STORAGE device mounted successfully." >> testreport.txt
    else
        echo "Mount failed." >> testreport.txt
        test_usb=fail
    fi

    # Create a test file on the USB device
    echo "Test file on STORAGE device" > /mnt/test_file.txt

    # Check if the test file was created successfully
    if [ $? -eq 0 ]; then
        echo "Test file created successfully." >> testreport.txt
    else
        echo "Test file creation failed." >> testreport.txt
        test_usb=fail
    fi

    # Unmount the USB device
    umount $STORAGE_PATH

    # Check if the unmount was successful
    if [ $? -eq 0 ]; then
        echo "STORAGE device unmounted successfully." >> testreport.txt
    else
        echo "Unmount failed." >> testreport.txt
        test_usb=fail
    fi

    # Confirm that the USB device is no longer mounted
    if grep -qs '/mnt' /proc/mounts; then
        echo "Error: STORAGE device still mounted." >> testreport.txt
        test_usb=fail
    fi

    # Check the test status
    if [ "$test_usb" != "fail" ]; then
        echo "----------------------------------------------------------" >> testreport.txt
        echo " STORAGE $STORAGE_PATH : TEST SUCCESS" >> testreport.txt
        echo "----------------------------------------------------------" >> testreport.txt
    else
       echo "----------------------------------------------------------" >> testreport.txt
       echo " STORAGE $STORAGE_PATH : TEST FAILED" >> testreport.txt
       echo "----------------------------------------------------------" >> testreport.txt
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
      echo "Error: device $device_name does not exist" >> testreport.txt
      test_eth=fail
    fi

    # Check if an IP address has been assigned
    if ! ifconfig $device_name | grep "inet addr" > /dev/null; then
        echo "No IP address assigned to device $device_name, attempting to acquire one using udhcpc" >> testreport.txt
        udhcpc -i $device_name -t 5 -T 1 -A 10 -q -n
    fi

    # Check if udhcpc was successful in acquiring an IP address
    if ! ifconfig $device_name | grep "inet addr" > /dev/null; then
        echo "Error: failed to acquire IP address using udhcpc" >> testreport.txt
        test_eth=fail
    fi

    # Ping the default gateway
    ping -c 5 8.8.8.8 >> testreport.txt

    if [ $? -eq 0 ]; then
        echo "Ethernet connection is up" >> testreport.txt
    else
        test_eth=fail
        echo "Ethernet connection is down" >> testreport.txt
    fi
 
    # Check the test status
    if [ "$test_eth" != "fail" ]; then
        echo "----------------------------------------------------------" >> testreport.txt
        echo " ethernet $device_name : TEST SUCCESS" >> testreport.txt
        echo "----------------------------------------------------------" >> testreport.txt
    else
       echo "----------------------------------------------------------" >> testreport.txt
       echo " ethernet $device_name : : TEST FAILED" >> testreport.txt
       echo "----------------------------------------------------------" >> testreport.txt
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
        echo "UART device $UART_DEVICE not found" >> testreport.txt
        echo "Verify that $UART_DEVICE is present" >> testreport.txt
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
        echo "UART device test passed" >> testreport.txt
    else
        echo "UART device test failed" >> testreport.txt
        test_uart=fail
    fi

    # Report results
    echo "----------------------------------------------------------" >> testreport.txt
    if [ "$test_uart" = "pass" ]; then
        echo " UART $UART_DEVICE : TEST SUCCESS" >> testreport.txt
    else
        echo " UART $UART_DEVICE : TEST FAILED" >> testreport.txt
    fi
    echo "----------------------------------------------------------" >> testreport.txt
}


adc_test() {
    adc_pin=$1
    test_adc=pass
    adc_resolution=4095

    echo "Please connecte the  potentiometer to ADC pin to any position and press Enter to proceed"
    read -p "Press Enter to start the ADC test... " adc_dummy

    adc_value1=$(cat /sys/bus/iio/devices/iio:device0/in_voltage6_raw 2>/dev/null)

    if [ -z "$adc_value1" ]; then
        echo "Error: Failed to read initial ADC value" >> testreport.txt
        test_adc=fail
    elif [ "$adc_value1" -lt 0 ] || [ "$adc_value1" -gt $adc_resolution ]; then
        echo "Error: Initial ADC value out of valid range (0–4095)" >> testreport.txt
        test_adc=fail
    else
        echo "Initial ADC value: $adc_value1" >> testreport.txt
        echo "Now change the potentiometer position. Waiting for 10 seconds..."
        sleep 10

        adc_value2=$(cat /sys/bus/iio/devices/iio:device0/in_voltage6_raw 2>/dev/null)

        if [ -z "$adc_value2" ]; then
            echo "Error: Failed to read final ADC value" >> testreport.txt
            test_adc=fail
        elif [ "$adc_value2" -lt 0 ] || [ "$adc_value2" -gt $adc_resolution ]; then
            echo "Error: Final ADC value out of valid range (0–4095)" >> testreport.txt
            test_adc=fail
        else
            echo "Final ADC value: $adc_value2" >> testreport.txt

            diff=$((adc_value1 - adc_value2))
            [ "$diff" -lt 0 ] && diff=$(( -1 * diff ))

            if [ "$diff" -ge 100 ]; then
                echo "ADC value changed by $diff (>= 100)" >> testreport.txt
                echo "----------------------------------------------------------" >> testreport.txt
                echo " adc iio:device0 : TEST SUCCESS" >> testreport.txt
                echo "----------------------------------------------------------" >> testreport.txt
            else
                echo "ADC value changed by $diff (< 100)" >> testreport.txt
                echo "----------------------------------------------------------" >> testreport.txt
                echo " adc iio:device0 : TEST FAILED" >> testreport.txt
                echo "----------------------------------------------------------" >> testreport.txt
                test_adc=fail
            fi
        fi
    fi

    echo "Testing ADC GPIO1_IO03 ends" >> testreport.txt
    echo "====================================================================================================" >> testreport.txt
    echo >> testreport.txt
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
    echo >> testreport.txt
    echo "-----------------------------------------------------------------" >> testreport.txt
    echo " wathc the PWM LED if britness incress PWM SUCCESS or PWM FAILED " >> testreport.txt
    echo "-----------------------------------------------------------------" >> testreport.txt
}

#================================================== script init =======================================


# removing report file if already exists otherwise it concates 
if test -f "/data/testreport.txt"; then
    rm testreport.txt
fi

# capturing boot log
dmesg >> testreport.txt
echo >> testreport.txt
echo >> testreport.txt
echo Peripherals tests >> testreport.txt
echo ----------------- >> testreport.txt
echo >> testreport.txt

echo "Onboard USER LED Tests"
echo "---------------------"
echo
echo "Testing userled1 PC13"
echo "=========================== Testing userled1 PC13 ===========================" >> testreport.txt
gpio_led_switch_test 77 PC13 led
echo

echo "Testing userled2 PC17"
echo "=========================== Testing userled2 PC17 ===========================" >> testreport.txt
gpio_led_switch_test 81 PC17 led
echo

echo "Testing userled3 PC19"
echo "=========================== Testing userled3 PC19 ===========================" >> testreport.txt
gpio_led_switch_test 83 PC19 led
echo

echo "Onboard USER SWITCH TEST"
echo "--------------------------"
echo
echo "Testing userswitch PC12"
echo "======================================== Testing userswitch PC12 ====================================" >> testreport.txt
gpio_switch_test 76 PC12 switch
echo "Testing USER SWITCH ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo

echo "DIN Tests"
echo "-----------------"
echo "Testing DIN1 PC20"
echo "=========================== Testing DIN1 PC20 ===========================" >> testreport.txt
gpio_led_switch_test 84 PC20 DIN
echo

echo "Testing DIN2 PC24"
echo "=========================== Testing DIN2 PC24 ===========================" >> testreport.txt
gpio_led_switch_test 88 PC24 DIN
echo

echo "Testing DIN3 PC15"
echo "=========================== Testing DIN3 PC15 ===========================" >> testreport.txt
gpio_led_switch_test 79 PC15 DIN
echo

echo "Testing DIN4 PC22"
echo "=========================== Testing DIN4 PC22 ===========================" >> testreport.txt
gpio_led_switch_test 86 PC22 DIN
echo

echo "DOUT Tests"
echo "------------------"
echo "Testing DOUT1 PA17"
echo "=========================== Testing DOUT1  PA17 ===========================" >> testreport.txt
gpio_led_switch_test 17 PA17 DOUT
echo

echo "Testing DOUT2 PA14"
echo "=========================== Testing DOUT2 PA14 ===========================" >> testreport.txt
gpio_led_switch_test 14 PA14 DOUT
echo

echo "Testing DOUT3 PA16"
echo "=========================== Testing DOUT3 PA16 ===========================" >> testreport.txt
gpio_led_switch_test 16 PA16 DOUT
echo

echo "Testing DOUT4 PD1"
echo "=========================== Testing DOUT4 PD1 ===========================" >> testreport.txt
gpio_led_switch_test 97 PD1 DOUT
echo

# Ethernet test case
echo "ETHERNET Test"
echo "-------------"
echo
echo "Testing Ethernet 0 " 
echo -n "======================================== Testing Ethernet 0  ====================================" >> testreport.txt
echo >> testreport.txt
Ethernet_test eth0 
echo "Testing Ethernet 0 ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo "Testing Ethernet 0 ends"
echo


# usb test case
echo "USB Test"
echo "-------------"
echo
echo "Testing usb 0 " 
echo -n "======================================== Testing USB 0  ====================================" >> testreport.txt
echo >> testreport.txt
usb_sdcard_test usb
echo "Testing USB 0 ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo "Testing USB 0 ends"
echo

# sdcard test case
echo "sdcard Test"
echo "-----------"
echo
echo "Testing sdcard " 
echo -n "======================================== Testing sdcard  ====================================" >> testreport.txt
echo >> testreport.txt
usb_sdcard_test sdcard
echo "Testing sdcard ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo "Testing sdcard ends"
echo


# EEPROM test case
echo "EEPROM Test"
echo "-----------"
echo
echo "Testing EEPROM I2C0" 
echo -n "======================================== Testing EEPROM I2C0 ====================================" >> testreport.txt
echo >> testreport.txt
eeprom_test 0 0x50
echo "Testing EEPROM ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo "Testing EEPROM ends"
echo

# TTL UART3 Test
echo " TTL UART3Test"
echo "---------------"
echo
echo "======================================== Testing UART3(TTL)  ====================================" >> testreport.txt
uart_test /dev/ttyS3 ttl
echo "Testing UART3(TTL) ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo

# RS232 UART2 Test
echo " RS232 UART2 Test"
echo "-----------------"
echo
echo "======================================== Testing UART2(RS232)  ====================================" >> testreport.txt
uart_test /dev/ttyS4 RS232
echo "Testing UART2(RS232) ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo


# RS232 UART4 Test
echo " RS232 UART4 Test"
echo "------------------"
echo
echo "======================================== Testing UART4(RS232)  ====================================" >> testreport.txt
uart_test /dev/ttyS1 RS232
echo "Testing UART4(RS232) ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo
echo

# RS485 UART6 Test
echo " RS485 UART6 Test"
echo "-----------------"
echo
echo "======================================== Testing UART6(RS485)  ====================================" >> testreport.txt
uart_test /dev/ttyS2 RS485
echo "Testing UART6(RS485) ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo
echo

# PWM test case
echo "PWM Test"
echo "----------"
echo
echo "Testing PWM"
echo "======================================== Testing PWM  ====================================" >> testreport.txt
echo >> testreport.txt
pwm_test
echo "Testing PWM ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo "Testing PWM ends"
echo
echo

# ADC test case
echo "ADC test"
echo "-----------------"
echo
echo "======================================== Testing ADC GPIO1_IO03 ====================================" >> testreport.txt
adc_test 3
echo "Testing ADC GPIO1_IO03 ends" >> testreport.txt
echo "====================================================================================================" >> testreport.txt
echo >> testreport.txt
echo
echo


