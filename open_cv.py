import datetime
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import traceback

DEPENDENCY_ERROR = None
TK_ERROR = None
DEFAULT_BASE_DIR = Path(r"C:\Users\user\Desktop\open_cv")
CONFIG_FILE_NAME = "open_cv.txt"
CONFIG_FILE = DEFAULT_BASE_DIR / CONFIG_FILE_NAME
APP_BASE_DIR = DEFAULT_BASE_DIR
PICTURE_DIR = APP_BASE_DIR / "picture"
LOG_DIR = APP_BASE_DIR / "log"
OPERATION_DIR = APP_BASE_DIR / "operation"
CPU_COUNT = os.cpu_count() or 1
INITIAL_PASSWORD = "1234"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 47631
BACKEND_COMMAND_SHOW = b"SHOW"

os.environ["OMP_NUM_THREADS"] = str(CPU_COUNT)
os.environ["OPENBLAS_NUM_THREADS"] = str(CPU_COUNT)
os.environ["MKL_NUM_THREADS"] = str(CPU_COUNT)


def append_runtime_log(message):
    log_dirs = [
        OPERATION_DIR,
        Path(sys.executable).resolve().parent,
    ]

    for log_dir in log_dirs:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "open_cv_runtime.log"
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(f"[{now}] {message}\n")
            return
        except OSError:
            continue


def notify_existing_backend():
    try:
        with socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=0.2) as client:
            client.sendall(BACKEND_COMMAND_SHOW)
        return True
    except OSError:
        return False


def is_frozen_app():
    return getattr(sys, "frozen", False) or "__compiled__" in globals()


def get_app_dir():
    if is_frozen_app():
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def configure_tcl_tk_paths():
    candidate_dirs = [
        get_app_dir() / "tcl",
        Path(__file__).resolve().parent / "tcl",
        Path(sys.base_prefix) / "tcl",
        Path(sys.prefix) / "tcl",
        Path(r"C:\Users\user\AppData\Local\Programs\Python\Python312\tcl"),
    ]

    for app_tcl_dir in candidate_dirs:
        tcl_library = app_tcl_dir / "tcl8.6"
        tk_library = app_tcl_dir / "tk8.6"
        if tcl_library.exists() and tk_library.exists():
            os.environ["TCL_LIBRARY"] = str(tcl_library)
            os.environ["TK_LIBRARY"] = str(tk_library)
            append_runtime_log(f"TCL_LIBRARY={tcl_library}")
            append_runtime_log(f"TK_LIBRARY={tk_library}")
            return

    append_runtime_log("Tcl/Tk library paths not found")


def configure_parallel_runtime():
    try:
        cv2.setNumThreads(CPU_COUNT)
    except Exception:
        pass


def parse_config_file():
    values = {}
    if not CONFIG_FILE.exists():
        return values

    for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.strip()

    return values


def write_config_file(base_path, password):
    base_path = Path(base_path).expanduser()
    base_path.mkdir(parents=True, exist_ok=True)
    content = f"path = {base_path}\npassword = {password}\n"
    target_config_file = base_path / CONFIG_FILE_NAME
    target_config_file.write_text(content, encoding="utf-8")

    if target_config_file != CONFIG_FILE:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(content, encoding="utf-8")


def show_initial_settings_window():
    settings_root = tk.Tk()
    settings_root.title("OpenCV Settings")
    settings_root.geometry("420x150")
    settings_root.resizable(False, False)

    tk.Label(settings_root, text="path").grid(row=0, column=0, padx=8, pady=12, sticky="e")
    tk.Label(settings_root, text="password").grid(row=1, column=0, padx=8, pady=8, sticky="e")

    path_var = tk.StringVar(value=str(DEFAULT_BASE_DIR))
    password_var = tk.StringVar(value=INITIAL_PASSWORD)
    path_entry = tk.Entry(settings_root, textvariable=path_var, width=46)
    password_entry = tk.Entry(settings_root, textvariable=password_var, show="*", width=46)
    path_entry.grid(row=0, column=1, padx=8, pady=12, sticky="ew")
    password_entry.grid(row=1, column=1, padx=8, pady=8, sticky="ew")
    settings_root.columnconfigure(1, weight=1)

    settings = {"confirmed": False}

    def confirm_settings():
        base_path = path_var.get().strip()
        password = password_var.get().strip()
        if not base_path:
            messagebox.showwarning("Settings", "Path cannot be empty.")
            return
        if not password:
            messagebox.showwarning("Settings", "Password cannot be empty.")
            return

        try:
            write_config_file(base_path, password)
        except OSError as error:
            messagebox.showerror("Settings", f"Could not save settings:\n{error}")
            return

        settings["confirmed"] = True
        settings_root.destroy()

    def block_close():
        messagebox.showwarning("Settings", "Please confirm settings first.")

    tk.Button(settings_root, text="confirm", command=confirm_settings).grid(
        row=2, column=0, columnspan=2, pady=10
    )
    settings_root.protocol("WM_DELETE_WINDOW", block_close)
    path_entry.focus_set()
    settings_root.mainloop()
    return settings["confirmed"]


def initialize_settings():
    global APP_BASE_DIR, PICTURE_DIR, LOG_DIR, OPERATION_DIR, INITIAL_PASSWORD

    if not CONFIG_FILE.exists():
        show_initial_settings_window()

    config = parse_config_file()
    APP_BASE_DIR = Path(config.get("path", str(DEFAULT_BASE_DIR))).expanduser()
    INITIAL_PASSWORD = config.get("password", INITIAL_PASSWORD)
    PICTURE_DIR = APP_BASE_DIR / "picture"
    LOG_DIR = APP_BASE_DIR / "log"
    OPERATION_DIR = APP_BASE_DIR / "operation"

    for folder in (APP_BASE_DIR, PICTURE_DIR, LOG_DIR, OPERATION_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def load_dependencies():
    global cv2, Image, ImageTk, DEPENDENCY_ERROR

    try:
        import cv2
        from PIL import Image, ImageTk
        DEPENDENCY_ERROR = None
        configure_parallel_runtime()
        append_runtime_log("dependencies import ok")
    except ModuleNotFoundError:
        if is_frozen_app():
            cv2 = None
            Image = None
            ImageTk = None
            DEPENDENCY_ERROR = "Required modules were not included in the exe build."
            append_runtime_log(f"dependencies import failed: {DEPENDENCY_ERROR}")
            return

        try:
            append_runtime_log("installing dependencies")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "opencv-python", "pillow"]
            )
            import cv2
            from PIL import Image, ImageTk
            DEPENDENCY_ERROR = None
            configure_parallel_runtime()
            append_runtime_log("dependencies installed and imported ok")
        except Exception as error:
            cv2 = None
            Image = None
            ImageTk = None
            DEPENDENCY_ERROR = error
            append_runtime_log(f"dependencies import failed: {error}")


if notify_existing_backend():
    sys.exit(0)

load_dependencies()
configure_tcl_tk_paths()

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog
    append_runtime_log("tkinter import ok")
except Exception as error:
    tk = None
    messagebox = None
    simpledialog = None
    TK_ERROR = error
    append_runtime_log(f"tkinter import failed: {error}")


def use_confirm_messagebox_buttons():
    def show_message(title=None, message=None, **options):
        parent = options.get("parent")
        temporary_root = None

        if parent is None:
            parent = tk._default_root

        if parent is None:
            temporary_root = tk.Tk()
            temporary_root.withdraw()
            parent = temporary_root

        popup = tk.Toplevel(parent)
        popup.title(title or "Message")
        popup.resizable(False, False)
        popup.transient(parent)
        popup.grab_set()

        tk.Label(
            popup,
            text=str(message or ""),
            justify=tk.LEFT,
            anchor="w",
            padx=18,
            pady=18,
            wraplength=420,
        ).pack(fill=tk.BOTH, expand=True)

        tk.Button(popup, text="confirm", width=12, command=popup.destroy).pack(
            pady=(0, 14)
        )

        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        popup.geometry(f"+{x}+{y}")
        popup.protocol("WM_DELETE_WINDOW", popup.destroy)
        popup.wait_window()

        if temporary_root is not None:
            temporary_root.destroy()

        return "ok"

    messagebox.showinfo = show_message
    messagebox.showwarning = show_message
    messagebox.showerror = show_message


if TK_ERROR is None:
    use_confirm_messagebox_buttons()
    initialize_settings()
    append_runtime_log("program startup")

def write_error_log(error):
    message = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    log_dirs = [
        OPERATION_DIR,
        get_app_dir(),
    ]

    for log_dir in log_dirs:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "open_cv_error.log"
            with log_path.open("a", encoding="utf-8") as log_file:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_file.write(f"\n[{now}]\n{message}\n")
            return log_path
        except OSError:
            continue

    return None


def get_face_cascade_path():
    local_path = get_app_dir() / "haarcascade_frontalface_default.xml"
    append_runtime_log(f"cascade local path: {local_path}")
    if local_path.exists():
        append_runtime_log("cascade found at local path")
        return str(local_path)

    cascade_name = "haarcascade_frontalface_default.xml"
    candidate_paths = [
        Path(cv2.data.haarcascades) / cascade_name,
        Path(r"C:\venvs\py312_nuitka\Lib\site-packages\cv2\data") / cascade_name,
        Path(r"C:\Users\user\AppData\Local\Programs\Python\Python312\Lib\site-packages\cv2\data") / cascade_name,
        Path(r"C:\Users\user\Desktop\open_cv") / cascade_name,
    ]

    for cv2_path in candidate_paths:
        append_runtime_log(f"cascade candidate path: {cv2_path}")
        if not cv2_path.exists():
            continue

        try:
            shutil.copy2(cv2_path, local_path)
            append_runtime_log("cascade copied to app dir")
            return str(local_path)
        except OSError:
            append_runtime_log("cascade copy failed, using candidate path")
            return str(cv2_path)

    append_runtime_log("cascade not found")
    return str(local_path)


WINDOW_WIDTH = 900
WINDOW_HEIGHT = 600
VIDEO_HEIGHT = 520

SAVE_FPS = 24
SAVE_SECONDS = 27
GUIDE_SECONDS_PER_POSITION = 3
SAVE_FRAME_COUNT = SAVE_FPS * SAVE_SECONDS
GUIDE_FRAMES_PER_POSITION = SAVE_FPS * GUIDE_SECONDS_PER_POSITION
FACE_MATCH_THRESHOLD = 520
MATCH_TOP_SCORE_COUNT = 12
MAX_TEST_IMAGES_PER_FOLDER = 50  # 낮추면 검사 속도 up 정확도는 하락 / 높이면 검사 속도 down 정확도는 상승
GUIDE_POSITIONS = (
    (0.25, 0.25),
    (0.50, 0.25),
    (0.75, 0.25),
    (0.25, 0.50),
    (0.50, 0.50),
    (0.75, 0.50),
    (0.25, 0.75),
    (0.50, 0.75),
    (0.75, 0.75),
)


class FaceCameraApp:
    def __init__(self, root, on_close=None):
        append_runtime_log("FaceCameraApp init started")
        self.root = root
        self.on_close = on_close
        self.closed = False
        self.video_after_id = None
        self.startup_failed = False
        self.root.title("OpenCV Face Camera")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.center_window()

        self.password = INITIAL_PASSWORD
        self.camera_index = self.find_available_camera()
        append_runtime_log(f"selected camera index: {self.camera_index}")
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            write_error_log(Exception("No camera could be opened."))
            append_runtime_log("camera open failed")
            messagebox.showerror("Camera Error", "No camera could be opened.")
            self.startup_failed = True
            self.root.withdraw()
            return

        append_runtime_log("camera opened")
        self.face_cascade = cv2.CascadeClassifier(get_face_cascade_path())
        if self.face_cascade.empty():
            write_error_log(Exception("Could not load haarcascade_frontalface_default.xml."))
            append_runtime_log("cascade load failed")
            messagebox.showerror(
                "OpenCV Error",
                "Could not load haarcascade_frontalface_default.xml.",
            )
            self.startup_failed = True
            self.root.withdraw()
            return
        append_runtime_log("cascade loaded")

        self.current_frame = None
        self.preview_image = None
        self.result_var = tk.StringVar(value="Ready")
        self.is_saving = False
        self.guide_position_index = 0
        self.saved_face_groups = None
        self.auto_test_started = False

        self.video_label = tk.Label(self.root, bg="black")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        button_frame = tk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=6, pady=6)

        tk.Button(button_frame, text="save", command=self.save_shot).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=2
        )
        tk.Button(button_frame, text="test", command=self.test_face).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=2
        )
        tk.Button(button_frame, text="delete", command=self.delete_folder).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=2
        )
        tk.Button(button_frame, text="path_change", command=self.open_path_change).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=2
        )
        tk.Button(
            button_frame, text="password_change", command=self.open_password_change
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        tk.Label(self.root, textvariable=self.result_var, anchor="center").pack(
            fill=tk.X, padx=6, pady=(0, 6)
        )

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        append_runtime_log("FaceCameraApp init completed")
        self.update_video()

    @staticmethod
    def find_available_camera(max_index=5):
        for index in range(1, max_index + 1):
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                cap.release()
                return index
            cap.release()
        return 1

    def center_window(self):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - WINDOW_WIDTH) // 2
        y = (screen_height - WINDOW_HEIGHT) // 2
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def update_video(self):
        if self.closed:
            return

        ok, frame = self.cap.read()
        if ok:
            self.current_frame = frame.copy()
            if not self.auto_test_started:
                self.auto_test_started = True
                self.root.after(500, self.test_face)
            display_frame = self.draw_face_boxes(frame)
            if self.is_saving:
                display_frame = self.draw_guidance(display_frame)
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            display_frame = cv2.resize(display_frame, (WINDOW_WIDTH, VIDEO_HEIGHT))

            image = Image.fromarray(display_frame)
            self.preview_image = ImageTk.PhotoImage(image=image)
            self.video_label.configure(image=self.preview_image)

        self.video_after_id = self.root.after(15, self.update_video)

    def draw_face_boxes(self, frame):
        result = frame.copy()
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
        )

        for x, y, width, height in faces:
            cv2.rectangle(result, (x, y), (x + width, y + height), (0, 255, 0), 2)

        return result

    def draw_guidance(self, frame):
        result = frame.copy()
        height, width = result.shape[:2]
        x_ratio, y_ratio = GUIDE_POSITIONS[self.guide_position_index]
        center = (int(width * x_ratio), int(height * y_ratio))
        radius = min(width, height) // 10
        text = "Pleas see the circle"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(width / 900, 0.8)
        thickness = 2
        text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
        text_x = (width - text_size[0]) // 2
        text_y = 45

        cv2.putText(result, text, (text_x, text_y), font, font_scale, (0, 0, 0), 5)
        cv2.putText(
            result, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness
        )
        cv2.circle(result, center, radius, (0, 255, 255), 3)
        return result

    def save_shot(self):
        if self.current_frame is None:
            messagebox.showwarning("Save", "No camera frame is available yet.")
            return

        entered_password = simpledialog.askstring(
            "Password", "Enter password:", show="*", parent=self.root
        )

        if entered_password is None:
            return

        if entered_password != self.password:
            messagebox.showerror("Save", "Wrong password.")
            return

        if self.is_saving:
            messagebox.showwarning("Save", "Already saving photos.")
            return

        folder_name = self.ask_folder_name()
        if folder_name is None:
            return

        PICTURE_DIR.mkdir(parents=True, exist_ok=True)
        save_folder = PICTURE_DIR / folder_name
        save_folder.mkdir(parents=True, exist_ok=True)

        self.is_saving = True
        self.guide_position_index = 0
        self.result_var.set("Saving...")
        self.save_frames(save_folder, self.get_next_frame_index(save_folder), 1)

    def ask_folder_name(self):
        popup = tk.Toplevel(self.root)
        popup.title("Save Folder Name")
        popup.geometry("300x120")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="folder name").grid(
            row=0, column=0, padx=8, pady=12, sticky="e"
        )

        name_var = tk.StringVar(value=self.get_default_folder_name())
        name_entry = tk.Entry(popup, textvariable=name_var)
        name_entry.grid(row=0, column=1, padx=8, pady=12, sticky="ew")
        popup.columnconfigure(1, weight=1)

        confirmed_name = {"value": None}

        def confirm_name():
            folder_name = self.clean_file_name(name_var.get())
            if not folder_name:
                messagebox.showwarning("Save", "Folder name cannot be empty.")
                return

            confirmed_name["value"] = folder_name
            popup.destroy()

        tk.Button(popup, text="confirm", command=confirm_name).grid(
            row=1, column=0, columnspan=2, pady=8
        )
        name_entry.focus_set()
        name_entry.select_range(0, tk.END)
        self.root.wait_window(popup)
        return confirmed_name["value"]

    def save_frames(self, save_folder, frame_index, saved_count):
        if self.current_frame is None:
            self.is_saving = False
            self.result_var.set("Ready")
            messagebox.showerror("Save", "Camera frame was lost while saving.")
            return

        save_path = save_folder / f"{save_folder.name}_{frame_index}.jpg"
        ok = cv2.imwrite(str(save_path), self.current_frame)
        if not ok:
            self.is_saving = False
            self.result_var.set("Ready")
            messagebox.showerror("Save", "Could not save the photo.")
            return

        self.guide_position_index = min(
            (saved_count - 1) // GUIDE_FRAMES_PER_POSITION,
            len(GUIDE_POSITIONS) - 1,
        )
        self.result_var.set(f"Saving... {saved_count}/{SAVE_FRAME_COUNT}")
        if saved_count >= SAVE_FRAME_COUNT:
            self.is_saving = False
            self.guide_position_index = 0
            self.saved_face_groups = None
            self.result_var.set("Ready")
            messagebox.showinfo("Save", "save complete")
            return

        delay_ms = round(1000 / SAVE_FPS)
        self.root.after(
            delay_ms, self.save_frames, save_folder, frame_index + 1, saved_count + 1
        )

    def delete_folder(self):
        if self.is_saving:
            messagebox.showwarning("Delete", "Cannot delete while saving photos.")
            return

        entered_password = simpledialog.askstring(
            "Password", "Enter password:", show="*", parent=self.root
        )

        if entered_password is None:
            return

        if entered_password != self.password:
            messagebox.showerror("Delete", "Wrong password.")
            return

        if not PICTURE_DIR.exists():
            messagebox.showwarning("Delete", "No picture folder was found.")
            return

        folders = sorted(path for path in PICTURE_DIR.iterdir() if path.is_dir())
        if not folders:
            messagebox.showwarning("Delete", "No saved folders were found.")
            return

        popup = tk.Toplevel(self.root)
        popup.title("Delete Folder")
        popup.geometry("320x260")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="folder list").pack(anchor="w", padx=8, pady=(8, 4))

        folder_list = tk.Listbox(popup, height=9, exportselection=False)
        folder_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        for folder in folders:
            folder_list.insert(tk.END, folder.name)

        def confirm_delete():
            selection = folder_list.curselection()
            if not selection:
                messagebox.showwarning("Delete", "Select a folder first.")
                return

            folder_name = folder_list.get(selection[0])
            target_folder = (PICTURE_DIR / folder_name).resolve()
            picture_root = PICTURE_DIR.resolve()
            if picture_root not in target_folder.parents:
                messagebox.showerror("Delete", "Invalid folder path.")
                return

            shutil.rmtree(target_folder)
            self.saved_face_groups = None
            popup.destroy()
            messagebox.showinfo("Delete", "delete complete")

        tk.Button(popup, text="confirm", command=confirm_delete).pack(
            fill=tk.X, padx=8, pady=8
        )

    def open_path_change(self):
        entered_password = simpledialog.askstring(
            "Password", "Enter password:", show="*", parent=self.root
        )

        if entered_password is None:
            return

        if entered_password != self.password:
            messagebox.showerror("Path", "Wrong password.")
            return

        popup = tk.Toplevel(self.root)
        popup.title("path_change")
        popup.geometry("420x120")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="new path").grid(
            row=0, column=0, padx=8, pady=12, sticky="e"
        )

        path_var = tk.StringVar(value=str(APP_BASE_DIR))
        path_entry = tk.Entry(popup, textvariable=path_var, width=46)
        path_entry.grid(row=0, column=1, padx=8, pady=12, sticky="ew")
        popup.columnconfigure(1, weight=1)

        def confirm_path_change():
            global APP_BASE_DIR, PICTURE_DIR, LOG_DIR, OPERATION_DIR

            new_path = path_var.get().strip()
            if not new_path:
                messagebox.showwarning("Path", "New path cannot be empty.")
                return

            APP_BASE_DIR = Path(new_path).expanduser()
            PICTURE_DIR = APP_BASE_DIR / "picture"
            LOG_DIR = APP_BASE_DIR / "log"
            OPERATION_DIR = APP_BASE_DIR / "operation"

            for folder in (APP_BASE_DIR, PICTURE_DIR, LOG_DIR, OPERATION_DIR):
                folder.mkdir(parents=True, exist_ok=True)

            write_config_file(APP_BASE_DIR, self.password)
            self.saved_face_groups = None
            messagebox.showinfo("Path", "path change complete")
            popup.destroy()

        tk.Button(popup, text="confirm", command=confirm_path_change).grid(
            row=1, column=0, columnspan=2, pady=8
        )
        path_entry.focus_set()
        path_entry.select_range(0, tk.END)

    @staticmethod
    def clean_file_name(file_name):
        return re.sub(r'[<>:"/\\|?*]', "_", file_name.strip())

    @staticmethod
    def get_next_frame_index(save_folder):
        max_index = 0
        pattern = re.compile(rf"^{re.escape(save_folder.name)}_(\d+)\.jpg$")
        for file_path in save_folder.glob("*.jpg"):
            match = pattern.match(file_path.name)
            if match:
                max_index = max(max_index, int(match.group(1)))

        return max_index + 1

    @staticmethod
    def get_default_folder_name():
        if not PICTURE_DIR.exists():
            return "face_shot"

        folders = sorted(
            [path for path in PICTURE_DIR.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not folders:
            return "face_shot"

        return folders[0].name

    def test_face(self):
        if self.current_frame is None:
            messagebox.showwarning("Test", "No camera frame is available yet.")
            return

        current_face = self.extract_largest_face(self.current_frame)
        if current_face is None:
            messagebox.showwarning("Test", "No face was found in the camera frame.")
            return

        saved_face_groups = self.get_saved_face_groups()
        if not saved_face_groups:
            messagebox.showwarning("Test", "No saved photos were found.")
            return

        matched_folder = None
        best_score = None
        for folder_name, saved_faces in saved_face_groups.items():
            folder_score = self.get_folder_match_score(current_face, saved_faces)
            if best_score is None or folder_score < best_score:
                best_score = folder_score
                matched_folder = folder_name

        if best_score is not None and best_score <= FACE_MATCH_THRESHOLD:
            result = f"{matched_folder}_PASS"
        else:
            result = "FAIL"

        self.result_var.set(result)
        self.write_log(result)
        if result.endswith("_PASS"):
            self.root.after(300, self.close)

    def get_saved_face_groups(self):
        if self.saved_face_groups is None:
            self.result_var.set("Loading saved faces...")
            self.root.update_idletasks()
            self.saved_face_groups = self.load_saved_face_groups()

        return self.saved_face_groups

    def load_saved_face_groups(self):
        if not PICTURE_DIR.exists():
            return {}

        saved_face_groups = {}
        for folder_path in sorted(path for path in PICTURE_DIR.iterdir() if path.is_dir()):
            image_files = sorted(folder_path.glob("*.jpg"))
            image_files = self.pick_evenly_spaced_files(
                image_files, MAX_TEST_IMAGES_PER_FOLDER
            )

            for file_path in image_files:
                image = cv2.imread(str(file_path))
                if image is None:
                    continue

                face = self.extract_largest_face(image)
                if face is not None:
                    saved_face_groups.setdefault(folder_path.name, []).append(face)

        return saved_face_groups

    @staticmethod
    def pick_evenly_spaced_files(file_paths, max_count):
        if len(file_paths) <= max_count:
            return file_paths

        step = len(file_paths) / max_count
        return [file_paths[int(index * step)] for index in range(max_count)]

    def extract_largest_face(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
        )
        if len(faces) == 0:
            return None

        x, y, width, height = max(faces, key=lambda face: face[2] * face[3])
        face = gray[y : y + height, x : x + width]
        face = cv2.resize(face, (120, 120))
        face = cv2.equalizeHist(face)
        return cv2.GaussianBlur(face, (3, 3), 0)

    def get_folder_match_score(self, current_face, saved_faces):
        scores = []
        for saved_face in saved_faces:
            score = self.compare_faces(current_face, saved_face)
            scores.append(score)
            if len(scores) >= MATCH_TOP_SCORE_COUNT and min(scores) <= FACE_MATCH_THRESHOLD:
                break

        scores.sort()
        top_scores = scores[:MATCH_TOP_SCORE_COUNT]
        return sum(top_scores) / len(top_scores)

    @staticmethod
    def compare_faces(first_face, second_face):
        first_float = first_face.astype("float32")
        second_float = second_face.astype("float32")
        diff_score = cv2.absdiff(first_float, second_float).mean()
        correlation = cv2.matchTemplate(first_face, second_face, cv2.TM_CCOEFF_NORMED)[0][0]
        correlation_score = (1 - correlation) * 1000
        return diff_score + correlation_score

    @staticmethod
    def write_log(result):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now()
        log_path = LOG_DIR / f"{now.strftime('%Y-%m-%d')}.txt"
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{now.strftime('%H:%M:%S')}]_{result}\n")

    def open_password_change(self):
        popup = tk.Toplevel(self.root)
        popup.title("password_change")
        popup.geometry("260x130")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="exist").grid(row=0, column=0, padx=8, pady=8, sticky="e")
        tk.Label(popup, text="new").grid(row=1, column=0, padx=8, pady=8, sticky="e")

        exist_entry = tk.Entry(popup, show="*")
        new_entry = tk.Entry(popup, show="*")
        exist_entry.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        new_entry.grid(row=1, column=1, padx=8, pady=8, sticky="ew")

        popup.columnconfigure(1, weight=1)

        def confirm_change():
            if exist_entry.get() != self.password:
                messagebox.showerror("Password", "Existing password is incorrect.")
                return

            new_password = new_entry.get()
            if not new_password:
                messagebox.showwarning("Password", "New password cannot be empty.")
                return

            self.password = new_password
            write_config_file(APP_BASE_DIR, self.password)
            messagebox.showinfo("Password", "Password changed.")
            popup.destroy()

        tk.Button(popup, text="confirm", command=confirm_change).grid(
            row=2, column=0, columnspan=2, pady=8
        )
        exist_entry.focus_set()

    def close(self):
        if self.closed:
            return

        self.closed = True
        if self.video_after_id is not None:
            try:
                self.root.after_cancel(self.video_after_id)
            except tk.TclError:
                pass
            self.video_after_id = None

        if hasattr(self, "cap") and self.cap.isOpened():
            self.cap.release()

        for child in self.root.winfo_children():
            child.destroy()
        self.root.withdraw()

        if self.on_close is not None:
            self.on_close()


class AppBackend:
    def __init__(self, root):
        self.root = root
        self.app = None

    def show_window(self):
        append_runtime_log("show window requested")
        if self.app is not None:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            return

        self.root.deiconify()
        self.app = FaceCameraApp(self.root, on_close=self.clear_app)
        if self.app.startup_failed:
            self.app = None
            self.root.withdraw()
            return

        self.root.lift()
        self.root.focus_force()

    def clear_app(self):
        self.app = None


def start_backend_server(root, controller):
    def server_loop():
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((BACKEND_HOST, BACKEND_PORT))
            server.listen()
            append_runtime_log("backend server started")
        except OSError as error:
            append_runtime_log(f"backend server failed: {error}")
            return

        with server:
            while True:
                try:
                    client, _ = server.accept()
                except OSError:
                    break

                with client:
                    command = client.recv(32)
                if command == BACKEND_COMMAND_SHOW:
                    root.after(0, controller.show_window)

    thread = threading.Thread(target=server_loop, daemon=True)
    thread.start()


def main():
    append_runtime_log("main entered")
    if TK_ERROR is not None:
        raise TK_ERROR

    append_runtime_log("creating Tk root")
    app_root = tk.Tk()
    app_root.withdraw()
    append_runtime_log("Tk root created")
    if DEPENDENCY_ERROR is not None:
        write_error_log(Exception(str(DEPENDENCY_ERROR)))
        messagebox.showerror(
            "Missing Package",
            "Required package is missing:\n"
            f"{DEPENDENCY_ERROR}\n\n"
            "Install packages with:\n"
            "pip install opencv-python pillow",
        )
        app_root.destroy()
    else:
        controller = AppBackend(app_root)
        start_backend_server(app_root, controller)
        app_root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        log_path = write_error_log(error)
        try:
            if tk is None:
                raise RuntimeError("tkinter is not available")
            root = tk.Tk()
            root.withdraw()
            if log_path is None:
                messagebox.showerror("OpenCV Error", str(error))
            else:
                messagebox.showerror(
                    "OpenCV Error",
                    f"{error}\n\nError log:\n{log_path}",
                )
            root.destroy()
        except Exception:
            pass
        raise
