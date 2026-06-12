import numpy as np
from metrics import Metrics
from config import leds_indexes, NUMBER_OF_LEDS, leds_indexes_small, display_modes, display_modes_small
from utils import interpolate_color, get_random_color
import hid
import time
import datetime 
import json
import os
import sys


digit_to_segments = {
    0: ['a', 'b', 'c', 'd', 'e', 'f'],
    1: ['b', 'c'],
    2: ['a', 'b', 'g', 'e', 'd'],
    3: ['a', 'b', 'g', 'c', 'd'],
    4: ['f', 'g', 'b', 'c'],
    5: ['a', 'f', 'g', 'c', 'd'],
    6: ['a', 'f', 'g', 'e', 'c', 'd'],
    7: ['a', 'b', 'c'],
    8: ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
    9: ['a', 'b', 'g', 'f', 'c', 'd'],
}

# 7-segment encoding: order [f, a, b, g, e, d, c] matching layout.json segment map
# Segments:  f  a  b  g  e  d  c
digit_mask = np.array(
    [
        [1, 1, 1, 0, 1, 1, 1],  # 0 → a,b,c,d,e,f
        [0, 0, 1, 0, 0, 0, 1],  # 1 → b,c
        [0, 1, 1, 1, 1, 1, 0],  # 2 → a,b,d,e,g
        [0, 1, 1, 1, 0, 1, 1],  # 3 → a,b,c,d,g
        [1, 0, 1, 1, 0, 0, 1],  # 4 → b,c,f,g
        [1, 1, 0, 1, 0, 1, 1],  # 5 → a,c,d,f,g
        [1, 1, 0, 1, 1, 1, 1],  # 6 → a,c,d,e,f,g
        [0, 1, 1, 0, 0, 0, 1],  # 7 → a,b,c
        [1, 1, 1, 1, 1, 1, 1],  # 8 → all
        [1, 1, 1, 1, 0, 1, 1],  # 9 → a,b,c,d,f,g
        [0, 0, 0, 0, 0, 0, 0],  # blank (fill_value=-1)
    ]
)

letter_mask = {
    'H': [1, 0, 1, 1, 1, 0, 1],
}



def _number_to_array(number):
    if number>=10:
        return _number_to_array(int(number/10))+[number%10]
    else:
        return [number]

def get_number_array(temp, array_length=3, fill_value=-1):
    if temp<0:
        return [fill_value]*array_length
    else:
        narray = _number_to_array(temp)
        if (len(narray)!=array_length):
            if(len(narray)<array_length):
                narray = np.concatenate([[fill_value]*(array_length-len(narray)),narray])
            else:
                narray = narray[1:]
        return narray

class Controller:
    def __init__(self, config_path=None):
        self.temp_unit = {"cpu": "celsius", "gpu": "celsius"}
        self.metrics = Metrics()
        self.VENDOR_ID = 0x0416   
        self.PRODUCT_ID = 0x8001 
        self.dev = self.get_device()
        self.HEADER = 'dadbdcdd000000000000000000000000fc0000ff'
        self.leds = np.array([0] * NUMBER_OF_LEDS)
        self.leds_indexes = leds_indexes
        # Configurable config path
        if config_path is None:
            self.config_path = os.environ.get('DIGITAL_LCD_CONFIG', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json'))
        else:
            self.config_path = config_path
        self.cpt = 0  # For alternate_time cycling
        self.cycle_duration = 50
        self.display_mode = None
        self.colors = np.array(["ffe000"] * NUMBER_OF_LEDS)  # Will be set in update()
        self.layout = self.load_layout()
        self.update()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None

    def load_layout(self):
        try:
            layout_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'layout.json')
            with open(layout_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading layout: {e}")
            return None

    def get_device(self):
        try:
            dev = hid.device()
            dev.open(self.VENDOR_ID, self.PRODUCT_ID)
            return dev
        except Exception as e:
            print(f"Error initializing HID device: {e}")
            return None

    def set_leds(self, key, value):
        try:
            self.leds[self.leds_indexes[key]] = value
        except KeyError:
            print(f"Warning: Key {key} not found in leds_indexes.")

    def send_packets(self):
        message = "".join([self.colors[i] if self.leds[i] != 0 else "000000" for i in range(NUMBER_OF_LEDS)])
        packet0 = bytes.fromhex(self.HEADER+message[:128-len(self.HEADER)])
        self.dev.write(packet0)
        packets = message[88:]
        for i in range(0,4):
            packet = bytes.fromhex('00'+packets[i*128:(i+1)*128])
            self.dev.write(packet)

    def set_temp(self, temperature: int, device='cpu', unit="celsius"):        
        if temperature < 1000:
            self.set_leds(device + '_temp', digit_mask[get_number_array(temperature)].flatten())
            if unit == "celsius":
                self.set_leds(device + '_celsius', 1)
            elif unit == "fahrenheit":
                self.set_leds(device + '_fahrenheit', 1)
        else:
            raise Exception("The numbers displayed on the temperature LCD must be less than 1000")

    def set_usage(self, usage : int, device='cpu'):
        if usage<200:
            self.set_leds(device+'_usage', np.concatenate(([int(usage>=100)]*2,digit_mask[get_number_array(usage, array_length=2)].flatten())))
            self.set_leds(device+'_percent_led', 1)
        else:
            raise Exception("The numbers displayed on the usage LCD must be less than 200")

    def draw_number(self, number, num_digits, digits_mapping):
        number_str = f"{number:0{num_digits}d}"
        for i, digit_char in enumerate(number_str):
            digit = int(digit_char)
            segments_to_light = digit_to_segments[digit]
            digit_map = digits_mapping[i]['map']
            for segment_name in segments_to_light:
                segment_index = digit_map[segment_name]
                self.leds[segment_index] = 1

    def display_peerless_standard(self):
        """Merged display mode: dual_metrics + peerless_standard with color support"""
        if not self.layout:
            print("Warning: layout.json not loaded. Cannot display peerless standard.")
            return

        cpu_unit = self.config.get('cpu_temperature_unit', 'celsius')
        gpu_unit = self.config.get('gpu_temperature_unit', 'celsius')
        temp_unit = {'cpu': cpu_unit, 'gpu': gpu_unit}

        metrics = self.metrics.get_metrics(temp_unit=temp_unit)
        
        # Get colors based on current metrics
        self.colors = self.get_config_colors(self.config, key="metrics", metrics=metrics)

        cpu_temp = metrics.get("cpu_temp", 0)
        cpu_usage = metrics.get("cpu_usage", 0)
        gpu_temp = metrics.get("gpu_temp", 0)
        gpu_usage = metrics.get("gpu_usage", 0)

        # Draw CPU Temp
        self.draw_number(cpu_temp, 3, self.layout['cpu_temp_digits'])
        if cpu_unit == 'celsius':
            self.leds[self.layout['cpu_celsius']] = 1
        else:
            self.leds[self.layout['cpu_fahrenheit']] = 1

        # Draw CPU Usage
        self.draw_number(cpu_usage % 100, 2, self.layout['cpu_usage_digits'])
        if cpu_usage >= 100:
            self.leds[self.layout['cpu_usage_1']['top']] = 1
            self.leds[self.layout['cpu_usage_1']['bottom']] = 1
        self.leds[self.layout['cpu_percent']] = 1

        # Draw GPU Temp
        self.draw_number(gpu_temp, 3, self.layout['gpu_temp_digits'])
        if gpu_unit == 'celsius':
            self.leds[self.layout['gpu_celsius']] = 1
        else:
            self.leds[self.layout['gpu_fahrenheit']] = 1

        # Draw GPU Usage
        self.draw_number(gpu_usage % 100, 2, self.layout['gpu_usage_digits'][::-1])
        if gpu_usage >= 100:
            self.leds[self.layout['gpu_usage_1']['top']] = 1
            self.leds[self.layout['gpu_usage_1']['bottom']] = 1
        self.leds[self.layout['gpu_percent']] = 1
        
        # Set CPU and GPU LEDs
        for led in self.layout['cpu_led']:
            self.leds[led] = 1
        for led in self.layout['gpu_led']:
            self.leds[led] = 1

    def display_peerless_temp(self):
        if not self.layout:
            print("Warning: layout.json not loaded. Cannot display peerless temp.")
            return

        cpu_unit = self.config.get('cpu_temperature_unit', 'celsius')
        gpu_unit = self.config.get('gpu_temperature_unit', 'celsius')
        temp_unit = {'cpu': cpu_unit, 'gpu': gpu_unit}

        metrics = self.metrics.get_metrics(temp_unit=temp_unit)
        self.colors = self.get_config_colors(self.config, key="metrics", metrics=metrics)
        
        cpu_temp = metrics.get("cpu_temp", 0)
        gpu_temp = metrics.get("gpu_temp", 0)

        # Draw CPU Temp
        self.draw_number(cpu_temp, 3, self.layout['cpu_temp_digits'])
        if cpu_unit == 'celsius':
            self.leds[self.layout['cpu_celsius']] = 1
        else:
            self.leds[self.layout['cpu_fahrenheit']] = 1

        # Draw GPU Temp
        self.draw_number(gpu_temp, 3, self.layout['gpu_temp_digits'])
        if gpu_unit == 'celsius':
            self.leds[self.layout['gpu_celsius']] = 1
        else:
            self.leds[self.layout['gpu_fahrenheit']] = 1
        
        # Set CPU and GPU LEDs
        for led in self.layout['cpu_led']:
            self.leds[led] = 1
        for led in self.layout['gpu_led']:
            self.leds[led] = 1

    def display_peerless_usage(self):
        if not self.layout:
            print("Warning: layout.json not loaded. Cannot display peerless usage.")
            return

        cpu_unit = self.config.get('cpu_temperature_unit', 'celsius')
        gpu_unit = self.config.get('gpu_temperature_unit', 'celsius')
        temp_unit = {'cpu': cpu_unit, 'gpu': gpu_unit}

        metrics = self.metrics.get_metrics(temp_unit=temp_unit)
        self.colors = self.get_config_colors(self.config, key="metrics", metrics=metrics)
        
        cpu_usage = metrics.get("cpu_usage", 0)
        gpu_usage = metrics.get("gpu_usage", 0)

        # Draw CPU Usage
        self.draw_number(cpu_usage % 100, 2, self.layout['cpu_usage_digits'])
        if cpu_usage >= 100:
            self.leds[self.layout['cpu_usage_1']['top']] = 1
            self.leds[self.layout['cpu_usage_1']['bottom']] = 1
        self.leds[self.layout['cpu_percent']] = 1

        # Draw GPU Usage
        self.draw_number(gpu_usage % 100, 2, self.layout['gpu_usage_digits'])
        if gpu_usage >= 100:
            self.leds[self.layout['gpu_usage_1']['top']] = 1
            self.leds[self.layout['gpu_usage_1']['bottom']] = 1
        self.leds[self.layout['gpu_percent']] = 1
        
        # Set CPU and GPU LEDs
        for led in self.layout['cpu_led']:
            self.leds[led] = 1
        for led in self.layout['gpu_led']:
            self.leds[led] = 1

    def display_metrics(self, devices=["cpu","gpu"]):
        self.temp_unit = {device: self.config.get(f"{device}_temperature_unit", "celsius")for device in ["cpu","gpu"]}
        metrics = self.metrics.get_metrics(temp_unit=self.temp_unit)
        for device in devices:
            self.set_leds(device+"_led", 1)
            self.set_temp(metrics[device+"_temp"], device=device, unit=self.temp_unit[device])
            self.set_usage(metrics[device+"_usage"], device=device)
            self.colors[self.leds_indexes[device]] = self.metrics_colors[self.leds_indexes[device]]

    def display_time(self, device="cpu"):
        current_time = datetime.datetime.now()
        self.set_leds(device+'_temp', np.concatenate((digit_mask[get_number_array(current_time.hour, array_length=2, fill_value=0)].flatten(),letter_mask["H"])))
        self.set_leds(device+'_usage', np.concatenate(([0,0],digit_mask[get_number_array(current_time.minute, array_length=2, fill_value=0)].flatten())))
        self.colors[self.leds_indexes[device]] = self.time_colors[self.leds_indexes[device]]
    
    def display_time_with_seconds(self):
        current_time = datetime.datetime.now()
        self.set_leds('cpu_temp', np.concatenate((digit_mask[get_number_array(current_time.hour, array_length=2, fill_value=0)].flatten(),letter_mask["H"])))
        self.set_leds('gpu_usage', np.concatenate(([0,0],digit_mask[get_number_array(current_time.second, array_length=2, fill_value=0)].flatten())))
        self.set_leds('cpu_usage', np.concatenate(([0,0],digit_mask[get_number_array(current_time.minute, array_length=2, fill_value=0)].flatten())))
        self.colors = self.time_colors

    def display_temp_small(self, device='cpu'):
        unit = {device: self.config.get(f"{device}_temperature_unit", "celsius")for device in ["cpu","gpu"]}
        self.set_leds(unit[device], 1)
        self.set_leds(device+'_led', 1)
        current_temp = self.metrics.get_metrics(self.temp_unit)[f"{device}_temp"]
        self.colors = self.metrics_colors
        if current_temp is not None:
            self.set_leds('digit_frame', digit_mask[get_number_array(current_temp, array_length=3, fill_value=0)].flatten())
        else:
            print(f"Warning: {device} temperature not available.")
    
    def display_usage_small(self, device='cpu'):   
        current_usage = self.metrics.get_metrics(self.temp_unit)[f"{device}_usage"]
        self.set_leds('percent_led', 1)
        self.set_leds(device+'_led', 1)
        self.colors = self.metrics_colors
        if current_usage is not None:
            self.set_leds('digit_frame', digit_mask[get_number_array(current_usage, array_length=3, fill_value=0)].flatten())
        else:
            print(f"Warning: {device} usage not available.")

    def get_config_colors(self, config, key="metrics", metrics=None):
        conf_colors = config.get(key, {}).get('colors', ["ffe000"] * NUMBER_OF_LEDS)
        if len(conf_colors) != NUMBER_OF_LEDS:
            print(f"Warning: config {key} colors length mismatch, using default colors.")
            colors = ["ff0000"] * NUMBER_OF_LEDS
        else:
            if metrics is None:
                metrics = self.metrics.get_metrics(self.temp_unit)
            colors = []
            for i, color in enumerate(conf_colors):
                if color.lower() == "random":
                    colors.append(get_random_color())
                elif color.startswith("wave_"):
                    wave_type, gradient = color.split(";", 1)
                    colors_list = gradient.split('-')
                    num_colors = len(colors_list)
                    
                    if num_colors >= 2:
                        if colors_list[0] != colors_list[-1]:
                            colors_list.append(colors_list[0])
                        
                        num_segments = len(colors_list) - 1
                        total_duration = self.cycle_duration
                        
                        if wave_type == "wave_ltr":
                            phase_shift = (i / NUMBER_OF_LEDS) * total_duration
                        else: # wave_rtl
                            phase_shift = ((NUMBER_OF_LEDS - i) / NUMBER_OF_LEDS) * total_duration
                        
                        time_in_cycle = (self.cpt + phase_shift) % total_duration
                        
                        if num_segments > 0:
                            segment_duration = total_duration / num_segments
                            segment_index = min(int(time_in_cycle / segment_duration), num_segments - 1)
                            
                            start_color = colors_list[segment_index]
                            end_color = colors_list[segment_index + 1]
                            
                            time_in_segment = time_in_cycle - (segment_index * segment_duration)
                            if segment_duration > 0:
                                factor = time_in_segment / segment_duration
                            else:
                                factor = 0
                            colors.append(interpolate_color(start_color, end_color, factor))
                        else:
                            colors.append(colors_list[0])
                    else:
                        colors.append(colors_list[0])
                elif ";" in color:  # New multi-stop gradient format
                    parts = color.split(';')
                    metric = parts[0]
                    stops = []
                    for stop in parts[1:]:
                        stop_parts = stop.split(':')
                        stops.append({'color': stop_parts[0], 'value': int(stop_parts[1])})
                    
                    stops.sort(key=lambda x: x['value'])
                    
                    if metric not in metrics:
                        print(f"Warning: {metric} not found in metrics, using first color.")
                        colors.append(stops[0]['color'])
                        continue

                    metric_value = metrics[metric]

                    if metric_value <= stops[0]['value']:
                        colors.append(stops[0]['color'])
                        continue
                    
                    if metric_value >= stops[-1]['value']:
                        colors.append(stops[-1]['color'])
                        continue

                    for j in range(len(stops) - 1):
                        if stops[j]['value'] <= metric_value < stops[j+1]['value']:
                            start_stop = stops[j]
                            end_stop = stops[j+1]
                            factor = (metric_value - start_stop['value']) / (end_stop['value'] - start_stop['value'])
                            colors.append(interpolate_color(start_stop['color'], end_stop['color'], factor))
                            break
                elif "-" in color:
                    split_color = color.split("-")
                    if len(split_color) == 3:
                        start_color, end_color, metric = split_color
                        current_time = datetime.datetime.now()
                        if metric == "seconds":
                            factor = current_time.second / 59
                        elif metric == "minutes":
                            factor = current_time.minute / 59
                        elif metric == "hours":
                            factor = current_time.hour / 23
                        else:
                            if metric not in metrics:
                                print(f"Warning: {metric} not found in metrics, using start color.")
                                factor = 0
                            elif self.metrics_min_value[metric] == self.metrics_max_value[metric]:
                                print(f"Warning: {metric} min and max values are the same, using start color.")
                                factor = 0
                            else:
                                metric_value = metrics[metric]
                                min_val = self.metrics_min_value[metric]
                                max_val = self.metrics_max_value[metric]
                                factor = (metric_value - min_val) / (max_val - min_val)
                                factor = max(0, min(1, factor)) # Clamp factor between 0 and 1
                        colors.append(interpolate_color(start_color, end_color, factor))
                    else:
                        colors_list = split_color
                        num_colors = len(colors_list)
                        
                        if num_colors >= 2:
                            # Add first color to the end to make a loop
                            if colors_list[0] != colors_list[-1]:
                                colors_list.append(colors_list[0])
                            
                            num_segments = len(colors_list) - 1
                            total_duration = self.cycle_duration # number of steps
                            time_in_cycle = self.cpt % total_duration
                            
                            if num_segments > 0:
                                segment_duration = total_duration / num_segments
                                segment_index = min(int(time_in_cycle / segment_duration), num_segments - 1)
                                
                                start_color = colors_list[segment_index]
                                end_color = colors_list[segment_index + 1]
                                
                                time_in_segment = time_in_cycle - (segment_index * segment_duration)
                                if segment_duration > 0:
                                    factor = time_in_segment / segment_duration
                                else:
                                    factor = 0
                                colors.append(interpolate_color(start_color, end_color, factor))
                            else:
                                colors.append(colors_list[0])
                        else:
                            colors.append(colors_list[0])
                else:
                    colors.append(color)
        return np.array(colors)
    
    def update(self):
        self.leds = np.array([0] * NUMBER_OF_LEDS)
        self.config = self.load_config()
        if self.config:
            VENDOR_ID = int(self.config.get('vendor_id', "0x0416"),16)
            PRODUCT_ID = int(self.config.get('product_id', "0x8001"),16)
            self.metrics_max_value = {
                "cpu_temp": self.config.get('cpu_max_temp', 90),
                "gpu_temp": self.config.get('gpu_max_temp', 90),
                "cpu_usage": self.config.get('cpu_max_usage', 100),
                "gpu_usage": self.config.get('gpu_max_usage', 100),
            }
            self.metrics_min_value = {
                "cpu_temp": self.config.get('cpu_min_temp', 30),
                "gpu_temp": self.config.get('gpu_min_temp', 30),
                "cpu_usage": self.config.get('cpu_min_usage', 0),
                "gpu_usage": self.config.get('gpu_min_usage', 0),
            }
            self.display_mode = self.config.get('display_mode', 'metrics')
            
            # Handle legacy dual_metrics mode
            if self.display_mode == 'dual_metrics':
                self.display_mode = 'peerless_standard'
                
            self.temp_unit = {device: self.config.get(f"{device}_temperature_unit", "celsius") for device in ["cpu", "gpu"]}
            self.metrics_colors = self.get_config_colors(self.config, key="metrics")
            self.time_colors = self.get_config_colors(self.config, key="time")
            self.update_interval = self.config.get('update_interval', 0.1)
            self.cycle_duration = int(self.config.get('cycle_duration', 5)/self.update_interval)
            self.metrics.update_interval = self.config.get('metrics_update_interval', 0.5)
            if self.config.get('layout_mode', 'big')== 'small':
                self.leds_indexes = leds_indexes_small
                if self.display_mode not in display_modes_small:
                    print(f"Warning: Display mode {self.display_mode} not compatible with small layout, switching to alternate metrics.")
                    self.display_mode = "alternate_metrics"
            else:
                self.leds_indexes = leds_indexes
                if self.display_mode not in display_modes:
                    print(f"Warning: Display mode {self.display_mode} not compatible with big layout, switching to metrics.")
                    self.display_mode = "metrics"
        else:
            VENDOR_ID = 0x0416
            PRODUCT_ID = 0x8001
            self.metrics_max_value = {
                "cpu_temp": 90,
                "gpu_temp": 90,
                "cpu_usage": 100,
                "gpu_usage": 100,
            }
            self.metrics_min_value = {
                "cpu_temp": 30,
                "gpu_temp": 30,
                "cpu_usage": 0,
                "gpu_usage": 0,
            }
            self.display_mode = 'metrics'
            self.time_colors = np.array(["ffe000"] * NUMBER_OF_LEDS)
            self.metrics_colors = np.array(["ff0000"] * NUMBER_OF_LEDS)
            self.update_interval = 0.1
            self.cycle_duration = int(5/self.update_interval)
            self.metrics.update_interval = 0.5
            self.leds_indexes = leds_indexes
        

        if VENDOR_ID != self.VENDOR_ID or PRODUCT_ID != self.PRODUCT_ID:
            print(f"Warning: Config VENDOR_ID or PRODUCT_ID changed, reinitializing device.")
            self.VENDOR_ID = VENDOR_ID
            self.PRODUCT_ID = PRODUCT_ID
            self.dev = self.get_device()

    def display(self):
        while True:
            self.config = self.load_config()
            self.update()
            if self.dev is None:
                print("No device found, with VENDOR_ID: {}, PRODUCT_ID: {}".format(self.VENDOR_ID, self.PRODUCT_ID))
                time.sleep(5)
            else:
                if self.display_mode == "alternate_time":
                    if self.cpt < self.cycle_duration:
                        self.display_time()
                        self.display_metrics(devices=['gpu'])
                    else:
                        self.display_time(device="gpu")
                        self.display_metrics(devices=['cpu'])
                elif self.display_mode == "metrics":
                    self.display_metrics(devices=["cpu", "gpu"])
                elif self.display_mode == "time":
                    self.display_time_with_seconds()
                elif self.display_mode == "time_cpu":
                    self.display_time(device="gpu")
                    self.display_metrics(devices=['cpu'])
                elif self.display_mode == "time_gpu":
                    self.display_time()
                    self.display_metrics(devices=['gpu'])
                elif self.display_mode == "alternate_time_with_seconds":
                    if self.cpt < self.cycle_duration:
                        self.display_time_with_seconds()
                    else:
                        self.display_metrics()
                elif self.display_mode == "alternate_metrics":
                    if self.cpt < self.cycle_duration/2:
                        self.display_temp_small(device='cpu')
                    elif self.cpt < self.cycle_duration:
                        self.display_temp_small(device='gpu')
                    elif self.cpt < 3*self.cycle_duration/2:
                        self.display_usage_small(device='cpu')
                    else:
                        self.display_usage_small(device='gpu')
                elif self.display_mode == "cpu_temp":
                    self.display_temp_small(device='cpu')
                elif self.display_mode == "gpu_temp":
                    self.display_temp_small(device='gpu')
                elif self.display_mode == "cpu_usage":
                    self.display_usage_small(device='cpu')
                elif self.display_mode == "gpu_usage":
                    self.display_usage_small(device='gpu')
                elif self.display_mode == "peerless_standard":
                    self.display_peerless_standard()
                elif self.display_mode == "peerless_temp":
                    self.display_peerless_temp()
                elif self.display_mode == "peerless_usage":
                    self.display_peerless_usage()
                elif self.display_mode == "debug_ui":
                    self.colors = self.metrics_colors
                    self.leds[:] = 1
                else:
                    print(f"Unknown display mode: {self.display_mode}")
                
                self.cpt = (self.cpt + 1) % (self.cycle_duration*2)
                self.send_packets()
            time.sleep(self.update_interval)


def main(config_path):
    controller = Controller(config_path=config_path)
    controller.display()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        print(f"Using config path: {config_path}")
    else:
        print("No config path provided, using default.")
        config_path = None
    main(config_path)