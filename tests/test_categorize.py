"""Categorization: finer purposes, part-number fallback, and auto-created tabs."""

import db
import bom


# --- offline keyword rules: finer purposes win over broad families ---------- #

def test_regulator_description_is_voltage_regulator():
    assert bom.guess_category("AMS1117-3.3 LDO linear regulator") == "voltage regulator"


def test_mosfet_description_is_mosfet_not_transistor():
    assert bom.guess_category("MOSFET P-Channel 30V 4.2A") == "mosfet"


def test_voltage_reference_keyword():
    assert bom.guess_category("2.5V shunt voltage reference") == "voltage reference"


def test_optocoupler_keyword():
    assert bom.guess_category("Optocoupler, phototransistor output") == "optocoupler"


def test_existing_broad_families_still_work():
    assert bom.guess_category("100nF MLCC capacitor") == "capacitor"
    assert bom.guess_category("10kΩ resistor 0805") == "resistor"


# --- part-number fallback: bare part numbers with no description ------------ #

def test_ao3407_bare_part_number_is_mosfet():
    # The motivating case: a P-channel MOSFET given only by part number.
    assert bom.guess_category("", "", "AO3407") == "mosfet"


def test_lm1117_part_number_is_regulator():
    assert bom.guess_category("", "", "LM1117-3.3") == "voltage regulator"


def test_pc817_part_number_is_optocoupler():
    assert bom.guess_category("", "", "PC817") == "optocoupler"


def test_unknown_part_number_still_uncategorized():
    assert bom.guess_category("", "", "ZZQ-9999-X") == "uncategorized"


def test_description_beats_part_number_prefix():
    # A real connector that happens to start like a transistor prefix: the
    # descriptive word should win over the part-number guess.
    assert bom.guess_category("USB Type-C connector", "", "2N-USB") == "connector"


# --- auto-created tabs: a new purpose shows up on its own tab ---------------- #

def test_new_category_gets_its_own_tab(client):
    db.add_component({"category": "voltage regulator", "value": "LM1117",
                      "quantity": 4})
    r = client.get("/")
    assert r.status_code == 200
    # The auto-created tab is title-cased in the UI.
    assert b"Voltage Regulator" in r.data


def test_uncategorized_filter(client):
    db.add_component({"category": "uncategorized", "value": "mystery", "quantity": 1})
    db.add_component({"category": "resistor", "value": "1k", "quantity": 1})
    only = db.list_components(category="uncategorized")
    assert len(only) == 1
    assert only[0]["value"] == "mystery"


# --- new fine categories ---------------------------------------------------- #

def test_dac_keyword():
    assert bom.guess_category("12-bit DAC, I2C interface") == "dac"
    assert bom.guess_category("Digital to Analog Converter") == "dac"


def test_dac_part_number():
    assert bom.guess_category("", "", "MCP4725") == "dac"
    assert bom.guess_category("", "", "DAC8551") == "dac"
    assert bom.guess_category("", "", "AD5662") == "dac"
    assert bom.guess_category("", "", "PT8211") == "dac"


def test_adc_keyword():
    assert bom.guess_category("16-bit ADC, 860 SPS") == "adc"
    assert bom.guess_category("analog-to-digital converter") == "adc"


def test_adc_part_number():
    assert bom.guess_category("", "", "ADS1115") == "adc"
    assert bom.guess_category("", "", "MCP3008") == "adc"
    assert bom.guess_category("", "", "HX711") == "adc"


def test_opamp_keyword():
    assert bom.guess_category("Precision rail-to-rail op-amp") == "op-amp"
    assert bom.guess_category("Operational amplifier") == "op-amp"


def test_opamp_part_number():
    assert bom.guess_category("", "", "OPA2134") == "op-amp"
    assert bom.guess_category("", "", "MCP6002") == "op-amp"
    assert bom.guess_category("", "", "AD8605") == "op-amp"
    assert bom.guess_category("", "", "INA219") == "op-amp"


def test_sensor_keyword():
    assert bom.guess_category("Temperature sensor, I2C") == "sensor"
    assert bom.guess_category("3-axis accelerometer") == "sensor"
    assert bom.guess_category("Hall effect sensor") == "sensor"


def test_sensor_part_number():
    assert bom.guess_category("", "", "BME280") == "sensor"
    assert bom.guess_category("", "", "MPU6050") == "sensor"
    assert bom.guess_category("", "", "DHT22") == "sensor"
    assert bom.guess_category("", "", "DS18B20") == "sensor"


def test_memory_keyword():
    assert bom.guess_category("256Kb serial EEPROM") == "memory"
    assert bom.guess_category("64Mbit SPI NOR Flash") == "memory"
    assert bom.guess_category("32KB SRAM") == "memory"


def test_memory_part_number():
    assert bom.guess_category("", "", "AT24C256") == "memory"
    assert bom.guess_category("", "", "W25Q128") == "memory"
    assert bom.guess_category("", "", "24LC256") == "memory"


def test_led_driver_keyword():
    assert bom.guess_category("16-channel LED driver") == "led driver"
    assert bom.guess_category("constant current LED controller") == "led driver"


def test_led_driver_part_number():
    assert bom.guess_category("", "", "TLC5940") == "led driver"
    assert bom.guess_category("", "", "PCA9685") == "led driver"
    assert bom.guess_category("", "", "WS2812B") == "led driver"


def test_motor_driver_keyword():
    assert bom.guess_category("Dual H-bridge motor driver") == "motor driver"
    assert bom.guess_category("Stepper driver, 1/16 step") == "motor driver"
    assert bom.guess_category("Low-side gate driver") == "motor driver"


def test_motor_driver_part_number():
    assert bom.guess_category("", "", "DRV8833") == "motor driver"
    assert bom.guess_category("", "", "A4988") == "motor driver"
    assert bom.guess_category("", "", "TMC2209") == "motor driver"
    assert bom.guess_category("", "", "L298N") == "motor driver"


# --- expanded MOSFET detection --------------------------------------------- #

def test_mosfet_nmos_pmos_keywords():
    assert bom.guess_category("30V NMOS transistor") == "mosfet"
    assert bom.guess_category("PMOS -20V enhancement mode") == "mosfet"


def test_mosfet_expanded_part_numbers():
    assert bom.guess_category("", "", "IRLML6402") == "mosfet"
    assert bom.guess_category("", "", "DMN3150L") == "mosfet"
    assert bom.guess_category("", "", "DMP3099L") == "mosfet"
    assert bom.guess_category("", "", "BSS138") == "mosfet"
    assert bom.guess_category("", "", "STP55NF06") == "mosfet"
    assert bom.guess_category("", "", "CJ2301") == "mosfet"
    assert bom.guess_category("", "", "NTR4003N") == "mosfet"
    assert bom.guess_category("", "", "PSMN022") == "mosfet"
    assert bom.guess_category("", "", "IPD060N03") == "mosfet"


# --- expanded microcontroller detection ------------------------------------ #

def test_mcu_expanded_part_numbers():
    assert bom.guess_category("", "", "RP2040") == "microcontroller"
    assert bom.guess_category("", "", "RP2350") == "microcontroller"
    assert bom.guess_category("", "", "NRF52840") == "microcontroller"
    assert bom.guess_category("", "", "MSP430G2553") == "microcontroller"
    assert bom.guess_category("", "", "CH552G") == "microcontroller"


# --- keyword vs part-number priority --------------------------------------- #

def test_dac_keyword_beats_generic_ic():
    assert bom.guess_category("DAC output 12-bit IC") == "dac"


def test_opamp_stays_opamp_not_ic():
    assert bom.guess_category("Low noise op-amp amplifier") == "op-amp"


def test_sensor_keyword_beats_ic():
    assert bom.guess_category("Temperature sensor IC") == "sensor"
