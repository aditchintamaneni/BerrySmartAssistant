import threading
import time
import json
import re
from datetime import datetime, timedelta
from collections import deque
from typing import Optional, Dict, Any, Tuple

class Functions:
    def __init__(self, models):
        self.models = models
        self.active_timers = []
        self.active_alarms = []
        self.monitor_thread = None
        self.monitoring = False
        self.check_interval = 1.0 # monitoring thread wakes up and checks time every second
        self.lock = threading.Lock()

        self.start_monitoring()
    
    def parse(self, prompt):
        """
        parse prompt and return a response to speak if it's a function call.
        returns a tuple (is_function, response)
        """
        prompt = prompt.lower().strip()
        if self.is_time_query(prompt):
            return (True, self.get_current_time())

        timer_result = self.parse_timer(prompt)
        if timer_result:
            return (True, self.set_timer(timer_result))

        alarm_result = self.parse_alarm(prompt)
        if alarm_result:
            return (True, self.set_alarm(alarm_result))
        
        # these are for status queries
        if "timer" in prompt or "alarm" in prompt:
            if any(word in prompt for word in ["left", "remaining", "status", "check"]):
                return True, self.get_status()
            if any(word in prompt for word in ["cancel", "stop", "clear"]):
                return True, self.cancel_timers()
        
        return False, ""
    
    def is_time_query(self, prompt):
        """check if prompt is asking for current time."""
        time_patterns = [
            "what time is it",
            "what's the time",
            "current time",
            "tell me the time",
            "what is the time",
            "what the time is"
        ]
        return any(pattern in prompt for pattern in time_patterns)
    
    def get_current_time(self):
        """return the current time in a speakable format for TTS"""
        curr_time = datetime.now()
        curr_hour = curr_time.hour
        curr_min = curr_time.minute
        
        period = "AM" if curr_hour < 12 else "PM"
        if curr_hour == 0:
            curr_hour = 12
        elif curr_hour > 12:
            curr_hour -= 12
        
        if curr_min == 0:
            return f"It's {curr_hour} {period}"
        else:
            minute_str = f"0{curr_min}" if curr_min < 10 else str(curr_min)
            return f"It's {curr_hour}:{minute_str} {period}"
    
    def parse_timer(self, prompt):
        """
        parses the timer duration to set.
        returns duration in seconds or None.
        handles combined units (eg "1 hour and 30 minutes").
        """
        if "timer" not in prompt:
            return None
        word_to_num = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'}
        for word, num in word_to_num.items():
            prompt = prompt.replace(word, num)
        total_seconds = 0
        
        # pairs each pattern w/corresponding multiplier in seconds
        patterns = [
            (r"(\d+)\s*(?:hour|hr)(?:s)?", 3600),
            (r"(\d+)\s*(?:minute|min)(?:s)?", 60),
            (r"(\d+)\s*(?:second|sec)(?:s)?", 1),
        ]
        for pattern, multiplier in patterns:
            matches = re.findall(pattern, prompt)
            for match in matches:
                total_seconds += int(match) * multiplier
        if "half" in prompt:
            if "hour" in prompt:
                total_seconds += 1800 
            elif "minute" in prompt:
                total_seconds += 30  
        return total_seconds if total_seconds > 0 else None
    
    def parse_alarm(self, prompt):
        """
        parse alarm time from prompt, accounting for whisper quirks
        return datetime object or None
        """
        # normalize
        prompt = prompt.replace('p.m.', 'pm').replace('a.m.', 'am')
        prompt = prompt.replace('p.m', 'pm').replace('a.m', 'am')
        # look for 3 or 4 digits followed by 'am' or 'pm' and inserts a colon (handles 1030am case)
        prompt = re.sub(r'\b(\d{3,4})\s*(am|pm)', lambda m: f"{m.group(1)[:-2]}:{m.group(1)[-2:]} {m.group(2)}", prompt) 
        # handle other separators (-, ., etc)
        prompt = re.sub(r'\b(\d{1,2})[-.\s](\d{2})\s*(am|pm)', r'\1:\2 \3', prompt)

        match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)', prompt) 
        if not match:
            match = re.search(r'(\d{1,2})\s*(am|pm)', prompt) # just the hour
            if match:
                hour, period = int(match.group(1)), match.group(2)
                minute = 0
            else:
                return None
        else:
            hour, minute, period = int(match.group(1)), int(match.group(2)), match.group(3)
        
        # convert to 24hr format
        if hour > 12 or minute > 59:
            return None
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        curr_time = datetime.now()

        try:
            alarm_time = curr_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if alarm_time <= curr_time:
                alarm_time += timedelta(days=1)
            return alarm_time
        except ValueError:
            return None
    
    def set_timer(self, duration_seconds):
        """set timer and return confirmation message"""
        expiry_time = datetime.now() + timedelta(seconds=duration_seconds)
        
        # lock to prevent race condition between main and monitoring threads
        with self.lock: 
            self.active_timers.append((expiry_time, duration_seconds))
        
        hours, remainder = divmod(duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
        if seconds > 0 or not parts: 
            parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")

        if len(parts) > 1:
            duration_str = ", ".join(parts[:-1]) + " and " + parts[-1]
        elif len(parts) == 1:
            duration_str = parts[0]
        else:
            duration_str = "0 seconds"

        return f"Setting a timer for {duration_str}."

    
    def set_alarm(self, alarm_time):
        """set alarm and return confirmation message."""
        with self.lock:
            self.active_alarms.append(alarm_time)
        
        time_str = alarm_time.strftime("%-I:%M %p")
        if alarm_time.date() > datetime.now().date():
            return f"Setting an alarm for {time_str} tomorrow"
        else:
            return f"Setting an alarm for {time_str}"
    
    def get_status(self):
        """get status of active timers and alarms."""
        messages = []
        curr_time = datetime.now()
        
        with self.lock:
            for expiry, duration in self.active_timers:
                remaining = (expiry - curr_time).total_seconds()
                if remaining > 0:
                    if remaining >= 60:
                        minutes = int(remaining // 60)
                        seconds = int(remaining % 60)
                        if seconds > 0:
                            messages.append(f"Timer: {minutes} minutes and {seconds} seconds left")
                        else:
                            messages.append(f"Timer: {minutes} minutes left")
                    else:
                        messages.append(f"Timer: {int(remaining)} seconds left")
            
            # Check alarms
            for alarm_time in self.active_alarms:
                time_str = alarm_time.strftime("%-I:%M %p")
                if alarm_time.date() > curr_time.date():
                    messages.append(f"Alarm set for {time_str} tomorrow")
                else:
                    messages.append(f"Alarm set for {time_str}")
        if messages:
            return ". ".join(messages)
        else:
            return "No active timers or alarms"
    
    def cancel_timers(self):
        """cancel all timers and alarms."""
        with self.lock:
            had_timers = len(self.active_timers) > 0
            had_alarms = len(self.active_alarms) > 0
            self.active_timers.clear()
            self.active_alarms.clear()
        
        if had_timers or had_alarms:
            return "Cancelled all timers and alarms"
        else:
            return "No timers or alarms to cancel"
    
    def start_monitoring(self):
        """start background thread to monitor timers and alarms."""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
    
    def monitor_loop(self):
        """background loop checking for expired timers/alarms."""
        while self.monitoring:
            curr_time = datetime.now()
            expired = []
            with self.lock:
                new_timers = []
                for expiry, duration in self.active_timers:
                    if curr_time >= expiry:
                        expired.append(("timer", duration))
                    else:
                        new_timers.append((expiry, duration))
                self.active_timers = new_timers

                new_alarms = []
                for alarm_time in self.active_alarms:
                    if curr_time >= alarm_time:
                        expired.append(("alarm", alarm_time))
                    else:
                        new_alarms.append(alarm_time)
                self.active_alarms = new_alarms

            # handle expired items outside lock
            for item_type, item_data in expired:
                self.handle_expiry(item_type, item_data)
            
            time.sleep(self.check_interval)
    
    def handle_expiry(self, item_type, item_data):
        """handle expired timer or alarm by interrupting current activity."""
        if item_type == "timer":
            duration = item_data
            if duration >= 60:
                minutes = duration // 60
                message = f"Your {minutes} minute timer is done!"
            else:
                message = f"Your {duration} second timer is done!"
        else: 
            alarm_time = item_data
            time_str = alarm_time.strftime("%-I:%M %p")
            message = f"Your {time_str} alarm is going off!"
        
        # interrupt any current activity to announce alarm/timer
        if self.models:
            self.models.stop_speaking()
            time.sleep(0.1)
            self.models.speak(message, wait=False)
    
    def shutdown(self):
        """shutdown the monitoring thread."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
