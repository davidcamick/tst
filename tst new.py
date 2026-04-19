import os
import time
import datetime
import threading
import pyautogui
import pygame
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import comtypes
import tkinter as tk
from tkinter import ttk, messagebox

# --- Core Logic from the original script ---

ALARM_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tst_alarm")

def get_alarm_sounds():
    """Scans the alarm folder for .mp3 files."""
    if not os.path.exists(ALARM_FOLDER):
        os.makedirs(ALARM_FOLDER)
        return []
    return [f for f in os.listdir(ALARM_FOLDER) if f.endswith('.mp3')]

def set_volume_to_max():
    """Set the system volume to 100%."""
    comtypes.CoInitialize()
    try:
        speakers = AudioUtilities.GetSpeakers()
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(1.0, None)
    finally:
        comtypes.CoUninitialize()

def fade_volume(duration, status_label=None):
    """Gradually fade the system volume to 0 over the given duration (in seconds)."""
    comtypes.CoInitialize()
    try:
        speakers = AudioUtilities.GetSpeakers()
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        original_scalar = volume.GetMasterVolumeLevelScalar()
        if duration <= 0:
            volume.SetMasterVolumeLevelScalar(0.0, None)
            return
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                break
            progress = elapsed / duration
            new_scalar = original_scalar * (1 - progress)
            volume.SetMasterVolumeLevelScalar(new_scalar, None)
            remaining = int(duration - elapsed)
            if status_label:
                status_label.config(text=f"Fading: {remaining}s")
            time.sleep(0.05)
        volume.SetMasterVolumeLevelScalar(0.0, None)
    finally:
        comtypes.CoUninitialize()

def fade_in_system_volume(duration):
    """Gradually increase the system volume from 0 to 100% over the given duration."""
    comtypes.CoInitialize()
    try:
        speakers = AudioUtilities.GetSpeakers()
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(0.0, None)
        if duration <= 0:
            volume.SetMasterVolumeLevelScalar(1.0, None)
            return
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                break
            progress = elapsed / duration
            volume.SetMasterVolumeLevelScalar(progress, None)
            time.sleep(0.5)
        volume.SetMasterVolumeLevelScalar(1.0, None)
    finally:
        comtypes.CoUninitialize()

def pause_media():
    """Pause any active media."""
    pyautogui.press('playpause')

def minimize_all_windows():
    """Minimize all windows."""
    pyautogui.hotkey('win', 'd')

def countdown_timer(minutes, fade_duration, status_label):
    """Runs the countdown and executes end-of-countdown actions."""
    try:
        total_seconds = minutes * 60
        for remaining in range(total_seconds, 0, -1):
            mins = (remaining - 1) // 60
            secs = (remaining - 1) % 60 + 1
            status_label.config(text=f"{mins:02d}:{secs:02d}")
            time.sleep(1)
        status_label.config(text="Fading volume...")
        fade_volume(fade_duration, status_label)
        status_label.config(text="Pausing media...")
        pause_media()
        time.sleep(1)
        status_label.config(text="Minimizing windows...")
        minimize_all_windows()
        status_label.config(text="Countdown finished.")
    except Exception as e:
        messagebox.showerror("Error in Countdown", f"An error occurred: {e}")


def alarm_trigger(alarm_time, fade_in_duration, alarm_sound_path, status_label, auto_shutoff_enabled=True):
    """Monitors for alarm time and triggers the alarm."""
    comtypes.CoInitialize()
    try:
        status_label.config(text=f"Alarm set for {alarm_time.strftime('%I:%M %p')}")
        while True:
            now = datetime.datetime.now()
            if now >= alarm_time:
                status_label.config(text="Alarm triggered! Waking up...")
                
                speakers = AudioUtilities.GetSpeakers()
                interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(0.0, None)
                
                pygame.mixer.init()
                try:
                    pygame.mixer.music.load(alarm_sound_path)
                    pygame.mixer.music.set_volume(1.0)
                    pygame.mixer.music.play(loops=-1)
                except pygame.error as e:
                    messagebox.showerror("Alarm Error", f"Could not play alarm sound: {e}")
                    return

                fade_in_system_volume(fade_in_duration)

                # Auto-shutoff after 10 minutes (if enabled)
                if auto_shutoff_enabled:
                    alarm_start_time = time.time()
                    auto_shutoff_seconds = 10 * 60  # 10 minutes
                    
                    def check_auto_shutoff():
                        while True:
                            if time.time() - alarm_start_time >= auto_shutoff_seconds:
                                pygame.mixer.music.stop()
                                status_label.config(text="Alarm auto-stopped after 10 minutes.")
                                return
                            time.sleep(1)
                    
                    shutoff_thread = threading.Thread(target=check_auto_shutoff, daemon=True)
                    shutoff_thread.start()

                user_choice = messagebox.askquestion("Alarm!", "Stop the alarm?", icon='warning')
                
                pygame.mixer.music.stop()
                if user_choice == 'yes':
                    status_label.config(text="Alarm stopped.")
                    return
                return
            time.sleep(1)
    finally:
        comtypes.CoUninitialize()

# --- GUI Application ---

class SleepTimerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Sleep Timer")
        self.geometry("450x600")

        pygame.mixer.init()

        self.alarm_sounds = get_alarm_sounds()
        if not self.alarm_sounds:
            dummy_path = os.path.join(ALARM_FOLDER, "default.mp3")
            if not os.path.exists(dummy_path):
                with open(dummy_path, "w") as f:
                    pass
            self.alarm_sounds = ["default.mp3"]

        self.selected_alarm = tk.StringVar(self)
        self.selected_alarm.set(self.alarm_sounds[0])
        
        self.auto_shutoff_enabled = tk.BooleanVar(value=True)  # Default to ON

        self.countdown_frame = None
        self.create_widgets()
        self.update_sleep_duration_label() # Initial calculation

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Countdown Slider
        countdown_frame = ttk.Frame(main_frame)
        countdown_frame.pack(pady=5, fill="x")
        self.minutes_var = tk.IntVar(value=30)
        ttk.Label(countdown_frame, text="Countdown Time:").pack(side="left")
        self.minutes_label = ttk.Label(countdown_frame, text="30 min")
        self.minutes_label.pack(side="right")
        self.minutes_slider = ttk.Scale(main_frame, from_=1, to=120, orient="horizontal", variable=self.minutes_var, command=lambda s: self.minutes_label.config(text=f"{int(float(s))} min"))
        self.minutes_slider.pack(pady=5, fill="x")

        # Fade Duration Slider
        fade_frame = ttk.Frame(main_frame)
        fade_frame.pack(pady=5, fill="x")
        self.fade_duration_var = tk.IntVar(value=240)
        ttk.Label(fade_frame, text="Fade Duration:").pack(side="left")
        self.fade_label = ttk.Label(fade_frame, text="240 sec")
        self.fade_label.pack(side="right")
        self.fade_slider = ttk.Scale(main_frame, from_=1, to=600, orient="horizontal", variable=self.fade_duration_var, command=lambda s: self.fade_label.config(text=f"{int(float(s))} sec"))
        self.fade_slider.pack(pady=5, fill="x")

        # Alarm Time Sliders
        ttk.Label(main_frame, text="Alarm Time:").pack(pady=10)
        
        hour_frame = ttk.Frame(main_frame)
        hour_frame.pack(pady=5, fill="x")
        self.hour_var = tk.IntVar(value=7)
        ttk.Label(hour_frame, text="Hour:").pack(side="left")
        self.hour_label = ttk.Label(hour_frame, text="7")
        self.hour_label.pack(side="right")
        self.hour_slider = ttk.Scale(main_frame, from_=1, to=12, orient="horizontal", variable=self.hour_var, command=self.on_time_change)
        self.hour_slider.pack(pady=5, fill="x")

        minute_frame = ttk.Frame(main_frame)
        minute_frame.pack(pady=5, fill="x")
        self.minute_var = tk.IntVar(value=0)
        ttk.Label(minute_frame, text="Minute:").pack(side="left")
        self.minute_label = ttk.Label(minute_frame, text="00")
        self.minute_label.pack(side="right")
        self.minute_slider = ttk.Scale(main_frame, from_=0, to=59, orient="horizontal", variable=self.minute_var, command=self.on_time_change)
        self.minute_slider.pack(pady=5, fill="x")

        am_pm_frame = ttk.Frame(main_frame)
        am_pm_frame.pack(pady=5)
        self.am_pm_var = tk.StringVar(value="AM")
        self.am_pm_combo = ttk.Combobox(am_pm_frame, textvariable=self.am_pm_var, values=["AM", "PM"], width=4, state="readonly")
        self.am_pm_combo.pack(side="left")
        self.am_pm_combo.bind("<<ComboboxSelected>>", self.on_time_change)

        self.sleep_duration_label = ttk.Label(main_frame, text="You will sleep for: X hours")
        self.sleep_duration_label.pack(pady=10)

        # Alarm Sound
        alarm_sound_frame = ttk.Frame(main_frame)
        alarm_sound_frame.pack(pady=5)
        ttk.Label(alarm_sound_frame, text="Alarm Sound:").pack(side="left", padx=5)
        self.alarm_menu = ttk.OptionMenu(alarm_sound_frame, self.selected_alarm, self.alarm_sounds[0], *self.alarm_sounds)
        self.alarm_menu.pack(side="left", padx=5)
        self.preview_button = ttk.Button(alarm_sound_frame, text="Preview", command=self.preview_alarm)
        self.preview_button.pack(side="left", padx=5)
        self.stop_preview_button = ttk.Button(alarm_sound_frame, text="Stop", command=self.stop_preview)
        self.stop_preview_button.pack(side="left", padx=5)
        self.stop_preview_button.pack_forget()

        # Alarm Fade-in
        ttk.Label(main_frame, text="Alarm Fade-in (seconds):").pack(pady=5)
        self.fade_in_entry = ttk.Entry(main_frame)
        self.fade_in_entry.pack(pady=5)
        self.fade_in_entry.insert(0, "600")
        
        # Auto-shutoff checkbox
        self.auto_shutoff_check = ttk.Checkbutton(main_frame, text="Auto-stop alarm after 10 minutes", variable=self.auto_shutoff_enabled)
        self.auto_shutoff_check.pack(pady=10)

        # Start Button
        self.start_button = ttk.Button(main_frame, text="Start Timer", command=self.start_timer)
        self.start_button.pack(pady=20)

        # Status Label
        self.status_label = ttk.Label(main_frame, text="Ready to start.")
        self.status_label.pack(pady=5)

    def on_time_change(self, event=None):
        self.hour_label.config(text=f"{self.hour_var.get()}")
        self.minute_label.config(text=f"{self.minute_var.get():02d}")
        self.update_sleep_duration_label()

    def get_alarm_time(self):
        now = datetime.datetime.now()
        alarm_hour = self.hour_var.get()
        alarm_minute = self.minute_var.get()
        am_pm = self.am_pm_var.get()

        alarm_h_24 = alarm_hour
        if am_pm.upper() == "PM" and alarm_hour != 12:
            alarm_h_24 += 12
        elif am_pm.upper() == "AM" and alarm_hour == 12:
            alarm_h_24 = 0
        
        alarm_time = now.replace(hour=alarm_h_24, minute=alarm_minute, second=0, microsecond=0)
        if alarm_time <= now:
            alarm_time += datetime.timedelta(days=1)
        return alarm_time

    def update_sleep_duration_label(self):
        try:
            alarm_time = self.get_alarm_time()
            countdown_minutes = self.minutes_var.get()
            
            bed_time = datetime.datetime.now() + datetime.timedelta(minutes=countdown_minutes)
            sleep_duration = alarm_time - bed_time
            
            total_seconds = sleep_duration.total_seconds()
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            
            self.sleep_duration_label.config(text=f"You will sleep for: {int(hours)} hours and {int(minutes)} minutes")
        except Exception:
            self.sleep_duration_label.config(text="Calculating sleep time...")

    def preview_alarm(self):
        selected_sound = self.selected_alarm.get()
        alarm_sound_path = os.path.join(ALARM_FOLDER, selected_sound)
        if not os.path.exists(alarm_sound_path):
            messagebox.showerror("Error", f"Alarm file not found: {selected_sound}")
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(alarm_sound_path)
            pygame.mixer.music.play()
            self.stop_preview_button.pack(side="left", padx=5)
        except pygame.error as e:
            messagebox.showerror("Playback Error", f"Could not play sound: {e}")

    def stop_preview(self):
        pygame.mixer.music.stop()
        self.stop_preview_button.pack_forget()

    def show_countdown_screen(self):
        """Hide main UI and show black countdown screen."""
        for widget in self.winfo_children():
            widget.pack_forget()
        
        self.countdown_frame = ttk.Frame(self, style="Black.TFrame")
        self.countdown_frame.pack(fill="both", expand=True)
        
        style = ttk.Style()
        style.configure("Black.TFrame", background="black")
        style.configure("Countdown.TLabel", background="black", foreground="white", font=("Arial", 48, "bold"))
        style.configure("Cancel.TButton", font=("Arial", 12))
        
        self.countdown_label = ttk.Label(self.countdown_frame, text="00:00", style="Countdown.TLabel")
        self.countdown_label.pack(expand=True)
        
        cancel_button = ttk.Button(self.countdown_frame, text="Cancel Countdown", command=self.cancel_countdown, style="Cancel.TButton")
        cancel_button.pack(pady=20)

    def cancel_countdown(self):
        """Cancel the countdown and reset the app."""
        pygame.mixer.music.stop()
        self.destroy()
        import sys
        os.execl(sys.executable, sys.executable, *sys.argv)

    def start_timer(self):
        try:
            minutes = self.minutes_var.get()
            fade_duration = self.fade_duration_var.get()
            alarm_time = self.get_alarm_time()
            fade_in_duration = int(self.fade_in_entry.get())
            selected_sound = self.selected_alarm.get()
            alarm_sound_path = os.path.join(ALARM_FOLDER, selected_sound)

            if not os.path.exists(alarm_sound_path):
                messagebox.showerror("Error", f"Alarm file not found: {selected_sound}")
                return

            self.show_countdown_screen()

            countdown_thread = threading.Thread(target=countdown_timer, args=(minutes, fade_duration, self.countdown_label), daemon=True)
            countdown_thread.start()

            alarm_thread = threading.Thread(target=alarm_trigger, args=(alarm_time, fade_in_duration, alarm_sound_path, self.countdown_label, self.auto_shutoff_enabled.get()), daemon=True)
            alarm_thread.start()

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for alarm fade-in.")
        except Exception as e:
            messagebox.showerror("An Error Occurred", str(e))


if __name__ == "__main__":
    app = SleepTimerApp()
    app.mainloop()
