# ctypes is a foreign function interface library for Python
# ctypes allows Python to call functions in shared libraries
# ctypes is used to call functions in the PicoScope API because the PicoScope API is written in C
# init_16 and init_32 are used to initialize 16-bit and 32-bit integers respectively in ctypes
import ctypes
import yaml
import numpy as np
from picosdk.ps2000 import ps2000 as ps
from picosdk.functions import adc2mV, assert_pico2000_ok

# Class to initialize the PicoScope device
class PicoScopeDevice:
    def __init__(self, config_file="config.yml"):
        self.chandle = None

        # Load configuration from file using PyYAML 
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)

        # Extract configuration parameters
        self.pre_trigger_samples = config['Extra']['pretriggersamples']
        self.post_trigger_samples = config['Extra']['posttriggersamples']
        # Range is the voltage range of the PicoScope device
        self.ch_a_range = config['ChannelA']['Range']
        self.ch_b_range = config['ChannelB']['Range']
        self.ch_a_coupling = config['ChannelA']['Coupling']
        self.ch_b_coupling = config['ChannelB']['Coupling']
        self.timebase = config['Extra']['timebase']


        self.max_samples = self.pre_trigger_samples + self.post_trigger_samples
        # Create buffers to store the data
        # The buffers are used to store the data collected from the PicoScope device
        # The data is stored as 16-bit integers
        # The buffers are then converted to mV
        # ctypes means that the data is stored in a format that can be used by the PicoScope API
        self.buffer_a = (ctypes.c_int16 * self.max_samples)()
        self.buffer_b = (ctypes.c_int16 * self.max_samples)()
        
        # Set the maximum ADC value
        # This is used to convert the ADC values to mV
        # The maximum ADC value is 32767 for a 16-bit ADC
        # ADC means Analog-to-Digital Converter
        self.max_adc = ctypes.c_int16(32767)
        self.time_interval = None

    def initialize(self):
        self.chandle = ps.ps2000_open_unit()
        assert_pico2000_ok(self.chandle)
        self.set_channel(channel=0, enabled=1, dc=self.ch_a_coupling, range_=self.ch_a_range)
        self.set_channel(channel=1, enabled=1, dc=self.ch_b_coupling, range_=self.ch_a_range)
        # Set the trigger to be 0 V with a threshold of 64 mV and a direction of 0 (rising edge)
        # The delay is set to 0 and the auto trigger is set to 1000 ms
        # Auto trigger is the time in milliseconds that the device waits before triggering
        self.set_trigger(0, 64, 0, 0, 1000)
        self.get_timebase_info()

    def set_channel(self, channel, enabled, dc, range_):
        status_set_channel = ps.ps2000_set_channel(self.chandle, channel, enabled, dc, range_)
        assert_pico2000_ok(status_set_channel)

    def set_trigger(self, source, threshold, direction, delay, auto_trigger_ms):
        status_trigger = ps.ps2000_set_trigger(self.chandle, source, threshold, direction, delay, auto_trigger_ms)
        assert_pico2000_ok(status_trigger)

    def get_timebase_info(self):
        # This function gets the timebase information from the PicoScope device
        # The timebase is used to set the sampling interval
        # self.timebase = 8
        time_interval = ctypes.c_int32()
        time_units = ctypes.c_int32()
        # Oversample is set to 1
        # This means that the data is not oversampled
        # Oversampling means that the data is sampled at a higher rate than the Nyquist rate
        oversample = ctypes.c_int16(1)
        max_samples_return = ctypes.c_int32()
        status_get_timebase = ps.ps2000_get_timebase(
            self.chandle, self.timebase, self.max_samples,
            ctypes.byref(time_interval), ctypes.byref(time_units),
            oversample, ctypes.byref(max_samples_return)
        )
        assert_pico2000_ok(status_get_timebase)
        self.time_interval = time_interval.value

    def run_block_capture(self):
        # Run block capture
        # This function will capture the number of samples specified by self.max_samples
        
        time_indisposed_ms = ctypes.c_int32()
        status_run_block = ps.ps2000_run_block(
            self.chandle, self.max_samples, self.timebase,
            ctypes.c_int16(1), ctypes.byref(time_indisposed_ms)
        )
        assert_pico2000_ok(status_run_block)
        # Wait until the device is ready
        # The device is ready when the data is collected
        
        ready = ctypes.c_int16(0)
        
        # The device is not ready when the data is being collected
        while not ready.value:
            ready = ctypes.c_int16(ps.ps2000_ready(self.chandle))

    def collect_data(self):
        # Collect data from the PicoScope device
        # The data is collected from the buffers and converted to mV
        # The data is then returned as numpy arrays
        # The time is calculated based on the time interval and the number of samples
        cmax_samples = ctypes.c_int32(self.max_samples)
        status_get_values = ps.ps2000_get_values(
            self.chandle, ctypes.byref(self.buffer_a), ctypes.byref(self.buffer_b),
            None, None, ctypes.byref(ctypes.c_int16(1)), cmax_samples
        )
        assert_pico2000_ok(status_get_values)
        data_a = np.array(adc2mV(self.buffer_a, self.ch_a_range, self.max_adc))
        data_b = np.array(adc2mV(self.buffer_b, self.ch_b_range, self.max_adc))
        return data_a, data_b

    def finalize(self):
        status_stop = ps.ps2000_stop(self.chandle)
        assert_pico2000_ok(status_stop)
        status_close = ps.ps2000_close_unit(self.chandle)
        assert_pico2000_ok(status_close)


