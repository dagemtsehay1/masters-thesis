import time
import threading
from collections import deque
import tkinter as tk

import cv2
import numpy as np
import sounddevice as sd
from PIL import Image, ImageTk

from src.gesture.detector import GestureDetector
from src.robot.coppelia_client import CoppeliaClient
from src.robot.controller import RobotController
from src.voice.detector import VoiceCommandDetector


class GestureGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Controller")
        self.root.geometry("1000x700")
        self.root.configure(bg="white")

        self.running = True
        self.lock = threading.Lock()

        self.detector = GestureDetector()
        self.detector.start()

        self.voice = VoiceCommandDetector(model_path="model")

        self.client = CoppeliaClient()
        self.controller = RobotController(self.client)

        self.last_logged_message = None
        self.last_sent_command = None
        self.last_command_time = 0.0
        self.command_cooldown = 0.3

        self.current_gesture = "-"
        self.current_voice = "-"
        self.voice_error = None

        self.latest_gesture_command = None
        self.latest_gesture_time = 0.0

        self.latest_voice_command = None
        self.latest_voice_time = 0.0

        self.audio_buffer = deque([0.0] * 1024, maxlen=1024)
        self.audio_stream = None
        self.voice_thread = None

        self.voice_priority = tk.DoubleVar(value=0.7)

        # ===== MAIN CONTAINER =====
        self.main = tk.Frame(self.root, bg="white")
        self.main.pack(fill="both", expand=True, padx=20, pady=20)

        # ===== 2x2 layout =====
        for row in range(2):
            self.main.grid_rowconfigure(row, weight=1, uniform="half")
        for col in range(2):
            self.main.grid_columnconfigure(col, weight=1, uniform="half")

        # ===== CAMERA =====
        self.camera_frame = tk.Frame(self.main, bg="white")
        self.camera_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.camera_frame.grid_propagate(False)

        self.camera_label = tk.Label(self.camera_frame, bg="white")
        self.camera_label.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)

        # ===== TOP RIGHT: VOICE WAVE =====
        self.top_right = tk.Frame(self.main, bg="white")
        self.top_right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.voice_title = tk.Label(
            self.top_right,
            text="Voice Wave",
            font=("Times New Roman", 13, "bold"),
            bg="white",
            fg="black",
        )
        self.voice_title.pack(anchor="nw", padx=20, pady=(20, 8))

        self.voice_status_label = tk.Label(
            self.top_right,
            text="Current Voice Command: -",
            font=("Times New Roman", 12),
            bg="white",
            fg="black",
        )
        self.voice_status_label.pack(anchor="nw", padx=20, pady=(0, 10))

        self.wave_outer_frame = tk.Frame(
            self.top_right,
            bg="#d9d9d9",
            padx=1,
            pady=1,
        )
        self.wave_outer_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.wave_inner_frame = tk.Frame(
            self.wave_outer_frame,
            bg="#f3f3f3",
            relief="sunken",
            bd=2,
            padx=10,
            pady=10,
        )
        self.wave_inner_frame.pack(fill="both", expand=True)

        self.wave_canvas = tk.Canvas(
            self.wave_inner_frame,
            bg="#f3f3f3",
            highlightthickness=0,
            bd=0,
        )
        self.wave_canvas.pack(fill="both", expand=True)

        # ===== BOTTOM LEFT: LOGS =====
        self.bottom_left = tk.Frame(self.main, bg="white")
        self.bottom_left.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        self.log_title = tk.Label(
            self.bottom_left,
            text="Command Logs",
            font=("Times New Roman", 13, "bold"),
            bg="white",
            fg="black",
        )
        self.log_title.pack(anchor="nw", padx=20, pady=(20, 8))

        self.log_outer_frame = tk.Frame(
            self.bottom_left,
            bg="#d9d9d9",
            padx=1,
            pady=1,
        )
        self.log_outer_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.log_box_frame = tk.Frame(
            self.log_outer_frame,
            bg="#f3f3f3",
            relief="sunken",
            bd=2,
            padx=10,
            pady=10,
        )
        self.log_box_frame.pack(fill="both", expand=True)

        self.log_content_frame = tk.Frame(self.log_box_frame, bg="#f3f3f3")
        self.log_content_frame.pack(fill="both", expand=True)

        self.scrollbar = tk.Scrollbar(self.log_content_frame)
        self.scrollbar.pack(side="right", fill="y")

        self.log_text = tk.Text(
            self.log_content_frame,
            bg="#f3f3f3",
            fg="black",
            bd=0,
            highlightthickness=0,
            font=("Times New Roman", 12),
            wrap="word",
            yscrollcommand=self.scrollbar.set,
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        self.scrollbar.config(command=self.log_text.yview)

        self.log_text.tag_config("prefix", foreground="gray")
        self.log_text.insert("end", "No commands detected yet.\n")
        self.log_text.config(state="disabled")

        # ===== BOTTOM RIGHT: STATUS + PRIORITY =====
        self.bottom_right = tk.Frame(self.main, bg="white")
        self.bottom_right.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

        self.status_title = tk.Label(
            self.bottom_right,
            text="System Status",
            font=("Times New Roman", 13, "bold"),
            bg="white",
            fg="black",
        )
        self.status_title.pack(anchor="nw", padx=20, pady=(20, 8))

        self.gesture_status_label = tk.Label(
            self.bottom_right,
            text="Current Gesture Command: -",
            font=("Times New Roman", 12),
            bg="white",
            fg="black",
        )
        self.gesture_status_label.pack(anchor="nw", padx=20, pady=(0, 8))

        self.robot_status_label = tk.Label(
            self.bottom_right,
            text="Last Robot Command: -",
            font=("Times New Roman", 12),
            bg="white",
            fg="black",
        )
        self.robot_status_label.pack(anchor="nw", padx=20, pady=(0, 16))

        self.priority_title = tk.Label(
            self.bottom_right,
            text="Priority Control",
            font=("Times New Roman", 13, "bold"),
            bg="white",
            fg="black",
        )
        self.priority_title.pack(anchor="nw", padx=20, pady=(0, 8))

        self.priority_value_label = tk.Label(
            self.bottom_right,
            text="Voice 70% | Gesture 30%",
            font=("Times New Roman", 12),
            bg="white",
            fg="black",
        )
        self.priority_value_label.pack(anchor="nw", padx=20, pady=(0, 8))

        self.priority_slider = tk.Scale(
            self.bottom_right,
            from_=0,
            to=100,
            orient="horizontal",
            bg="white",
            fg="black",
            highlightthickness=0,
            command=self.on_priority_change,
        )
        self.priority_slider.pack(fill="x", padx=20, pady=(0, 8))
        self.priority_slider.set(70)

        self.priority_note_label = tk.Label(
            self.bottom_right,
            text="If both commands appear together, weighted priority is used.\nStop always wins.",
            font=("Times New Roman", 11),
            bg="white",
            fg="gray",
            justify="left",
        )
        self.priority_note_label.pack(anchor="nw", padx=20, pady=(0, 8))

        # ===== START BACKGROUND TASKS =====
        self.start_audio_wave_stream()
        self.start_voice_thread()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_priority_label()
        self.update_frame()

    def on_priority_change(self, value):
        try:
            percent = float(value) / 100.0
        except ValueError:
            percent = 0.7
        self.voice_priority.set(percent)
        self.update_priority_label()

    def update_priority_label(self):
        voice_percent = int(self.voice_priority.get() * 100)
        gesture_percent = 100 - voice_percent
        self.priority_value_label.config(
            text=f"Voice {voice_percent}% | Gesture {gesture_percent}%"
        )

    def start_audio_wave_stream(self):
        def audio_callback(indata, frames, time_info, status):
            if status:
                return
            samples = indata[:, 0]
            with self.lock:
                self.audio_buffer.extend(samples.tolist())

        try:
            self.audio_stream = sd.InputStream(
                channels=1,
                samplerate=16000,
                blocksize=256,
                callback=audio_callback,
            )
            self.audio_stream.start()
        except Exception as exc:
            self.voice_error = f"Wave stream error: {exc}"

    def start_voice_thread(self):
        self.voice_thread = threading.Thread(
            target=self.voice_loop,
            daemon=True,
        )
        self.voice_thread.start()

    def voice_loop(self):
        try:
            with self.voice.start_stream():
                while self.running:
                    try:
                        voice_cmd = self.voice.listen()
                        if voice_cmd:
                            now = time.time()
                            with self.lock:
                                self.current_voice = voice_cmd
                                self.latest_voice_command = voice_cmd
                                self.latest_voice_time = now
                            self.append_log("Voice Command", voice_cmd)
                    except Exception as exc:
                        with self.lock:
                            self.voice_error = str(exc)
                        time.sleep(0.1)
        except Exception as exc:
            with self.lock:
                self.voice_error = str(exc)

    def append_log(self, source, command):
        message_key = f"{source}:{command}"
        if not command or message_key == self.last_logged_message:
            return

        self.last_logged_message = message_key

        self.log_text.config(state="normal")

        current = self.log_text.get("1.0", "end").strip()
        if current == "No commands detected yet.":
            self.log_text.delete("1.0", "end")

        self.log_text.insert("end", f"[{source}] ", "prefix")
        self.log_text.insert("end", f"{command}\n")

        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def get_active_command_score(self, command_time, weight, now, active_window):
        age = now - command_time
        if age > active_window:
            return None

        freshness = 1.0 - (age / active_window)
        return (weight * 0.7) + (freshness * 0.3)

    def resolve_final_command(self):
        now = time.time()
        active_window = 0.4

        with self.lock:
            voice_cmd = self.latest_voice_command
            voice_time = self.latest_voice_time
            gesture_cmd = self.latest_gesture_command
            gesture_time = self.latest_gesture_time

        active_voice = voice_cmd if (now - voice_time) <= active_window else None
        active_gesture = (
            gesture_cmd if (now - gesture_time) <= active_window else None
        )

        if active_voice == "stop" or active_gesture == "stop":
            return "stop"

        if active_voice and active_gesture:
            voice_weight = self.voice_priority.get()
            gesture_weight = 1.0 - voice_weight

            voice_score = self.get_active_command_score(
                voice_time,
                voice_weight,
                now,
                active_window,
            )
            gesture_score = self.get_active_command_score(
                gesture_time,
                gesture_weight,
                now,
                active_window,
            )

            if voice_score is None and gesture_score is None:
                return None
            if voice_score is None:
                return active_gesture
            if gesture_score is None:
                return active_voice

            return active_voice if voice_score >= gesture_score else active_gesture

        if active_voice:
            return active_voice

        if active_gesture:
            return active_gesture

        return None

    def send_robot_command(self, command):
        if not command:
            return

        now = time.time()

        if command == self.last_sent_command and (
            now - self.last_command_time < self.command_cooldown
        ):
            return

        self.controller.handle_command(command)
        self.last_sent_command = command
        self.last_command_time = now

    def draw_waveform(self):
        self.wave_canvas.delete("all")

        canvas_w = self.wave_canvas.winfo_width()
        canvas_h = self.wave_canvas.winfo_height()

        if canvas_w <= 1 or canvas_h <= 1:
            return

        with self.lock:
            samples = np.array(self.audio_buffer, dtype=np.float32)

        if samples.size < 2:
            return

        center_y = canvas_h / 2
        scale = canvas_h * 0.35

        step = max(1, len(samples) // canvas_w)
        reduced = samples[::step]

        if len(reduced) < 2:
            return

        x_positions = np.linspace(0, canvas_w, num=len(reduced))
        y_positions = center_y - (reduced * scale)

        points = []
        for x, y in zip(x_positions, y_positions):
            points.extend([x, y])

        self.wave_canvas.create_line(points, fill="#666666", width=2)
        self.wave_canvas.create_line(
            0,
            center_y,
            canvas_w,
            center_y,
            fill="#cccccc",
            width=1,
        )

    def update_frame(self):
        command, frame = self.detector.detect()

        if frame is not None:
            w = self.camera_frame.winfo_width()
            h = self.camera_frame.winfo_height()

            if w > 1 and h > 1:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame_rgb)
                image = image.resize((w, h), Image.Resampling.LANCZOS)

                photo = ImageTk.PhotoImage(image=image)
                self.camera_label.configure(image=photo)
                self.camera_label.image = photo

        if command:
            now = time.time()
            self.current_gesture = command
            with self.lock:
                self.latest_gesture_command = command
                self.latest_gesture_time = now
            self.append_log("Gesture Command", command)
        else:
            with self.lock:
                if time.time() - self.latest_gesture_time > 0.4:
                    self.current_gesture = "-"

        final_command = self.resolve_final_command()
        if final_command:
            self.send_robot_command(final_command)

        self.gesture_status_label.config(
            text=f"Current Gesture Command: {self.current_gesture}"
        )

        with self.lock:
            current_voice = self.current_voice
            voice_error = self.voice_error
            latest_voice_time = self.latest_voice_time

        if time.time() - latest_voice_time > 0.4:
            current_voice = "-"

        if voice_error:
            self.voice_status_label.config(
                text=f"Current Voice Command: error ({voice_error})"
            )
        else:
            self.voice_status_label.config(
                text=f"Current Voice Command: {current_voice}"
            )

        self.robot_status_label.config(
            text=f"Last Robot Command: {self.last_sent_command or '-'}"
        )

        self.draw_waveform()
        self.controller.step()
        self.root.after(30, self.update_frame)

    def on_close(self):
        self.running = False

        try:
            self.controller._stop_robot()
        except Exception:
            pass

        try:
            if self.audio_stream is not None:
                self.audio_stream.stop()
                self.audio_stream.close()
        except Exception:
            pass

        try:
            self.detector.stop()
        except Exception:
            pass

        self.root.destroy()


def main():
    root = tk.Tk()
    GestureGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()