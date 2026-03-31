# Interactive Feedback MCP UI
# Developed by Fábio Ferreira (https://x.com/fabiomlferreira)
# Inspired by/related to dotcursorrules.com (https://dotcursorrules.com/)
import os
import sys
import json
import psutil
import argparse
import subprocess
import threading
import hashlib
from typing import Optional, TypedDict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSettings
from PySide6.QtGui import QTextCursor, QIcon, QKeyEvent, QFont, QFontDatabase, QPalette, QColor

class FeedbackResult(TypedDict):
    command_logs: str
    interactive_feedback: str

class FeedbackConfig(TypedDict):
    run_command: str
    execute_automatically: bool

def set_dark_title_bar(widget: QWidget, dark_title_bar: bool) -> None:
    # Ensure we're on Windows
    if sys.platform != "win32":
        return

    from ctypes import windll, c_uint32, byref

    # Get Windows build number
    build_number = sys.getwindowsversion().build
    if build_number < 17763:  # Windows 10 1809 minimum
        return

    # Check if the widget's property already matches the setting
    dark_prop = widget.property("DarkTitleBar")
    if dark_prop is not None and dark_prop == dark_title_bar:
        return

    # Set the property (True if dark_title_bar != 0, False otherwise)
    widget.setProperty("DarkTitleBar", dark_title_bar)

    # Load dwmapi.dll and call DwmSetWindowAttribute
    dwmapi = windll.dwmapi
    hwnd = widget.winId()  # Get the window handle
    attribute = 20 if build_number >= 18985 else 19  # Use newer attribute for newer builds
    c_dark_title_bar = c_uint32(dark_title_bar)  # Convert to C-compatible uint32
    dwmapi.DwmSetWindowAttribute(hwnd, attribute, byref(c_dark_title_bar), 4)

    # HACK: Create a 1x1 pixel frameless window to force redraw
    temp_widget = QWidget(None, Qt.FramelessWindowHint)
    temp_widget.resize(1, 1)
    temp_widget.move(widget.pos())
    temp_widget.show()
    temp_widget.deleteLater()  # Safe deletion in Qt event loop

DARK_STYLESHEET = """
QMainWindow {
    background-color: #1e1e2e;
}

QWidget {
    color: #cdd6f4;
    font-size: 13px;
}

QGroupBox {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    font-size: 13px;
    color: #cdd6f4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #89b4fa;
    font-weight: bold;
}

QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 18px;
    color: #cdd6f4;
    font-weight: 500;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton#primaryButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background-color: #74c7ec;
}

QPushButton#primaryButton:pressed {
    background-color: #b4befe;
}

QPushButton#dangerButton {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: none;
    font-weight: bold;
}

QPushButton#dangerButton:hover {
    background-color: #eba0ac;
}

QLineEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 10px;
    color: #cdd6f4;
    font-size: 13px;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QLineEdit:focus {
    border-color: #89b4fa;
}

QTextEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px;
    color: #cdd6f4;
    font-size: 13px;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QTextEdit:focus {
    border-color: #89b4fa;
}

QCheckBox {
    spacing: 8px;
    color: #cdd6f4;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #45475a;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QCheckBox::indicator:hover {
    border-color: #89b4fa;
}

QLabel {
    color: #cdd6f4;
    font-size: 13px;
}

QLabel#subtleLabel {
    color: #6c7086;
    font-size: 11px;
}

QLabel#pathLabel {
    color: #a6adc8;
    font-size: 12px;
    font-family: monospace;
}

QLabel#promptLabel {
    color: #cdd6f4;
    font-size: 14px;
    font-weight: 500;
    padding: 4px 0;
}

QScrollBar:vertical {
    background: #1e1e2e;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #45475a;
    min-height: 30px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
"""


def get_dark_mode_palette(app: QApplication):
    darkPalette = app.palette()
    darkPalette.setColor(QPalette.Window, QColor(30, 30, 46))
    darkPalette.setColor(QPalette.WindowText, QColor(205, 214, 244))
    darkPalette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(108, 112, 134))
    darkPalette.setColor(QPalette.Base, QColor(49, 50, 68))
    darkPalette.setColor(QPalette.AlternateBase, QColor(69, 71, 90))
    darkPalette.setColor(QPalette.ToolTipBase, QColor(49, 50, 68))
    darkPalette.setColor(QPalette.ToolTipText, QColor(205, 214, 244))
    darkPalette.setColor(QPalette.Text, QColor(205, 214, 244))
    darkPalette.setColor(QPalette.Disabled, QPalette.Text, QColor(108, 112, 134))
    darkPalette.setColor(QPalette.Dark, QColor(24, 24, 37))
    darkPalette.setColor(QPalette.Shadow, QColor(17, 17, 27))
    darkPalette.setColor(QPalette.Button, QColor(49, 50, 68))
    darkPalette.setColor(QPalette.ButtonText, QColor(205, 214, 244))
    darkPalette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(108, 112, 134))
    darkPalette.setColor(QPalette.BrightText, QColor(243, 139, 168))
    darkPalette.setColor(QPalette.Link, QColor(137, 180, 250))
    darkPalette.setColor(QPalette.Highlight, QColor(137, 180, 250))
    darkPalette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(69, 71, 90))
    darkPalette.setColor(QPalette.HighlightedText, QColor(30, 30, 46))
    darkPalette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(108, 112, 134))
    darkPalette.setColor(QPalette.PlaceholderText, QColor(108, 112, 134))
    return darkPalette

def kill_tree(process: subprocess.Popen):
    killed: list[psutil.Process] = []
    parent = psutil.Process(process.pid)
    for proc in parent.children(recursive=True):
        try:
            proc.kill()
            killed.append(proc)
        except psutil.Error:
            pass
    try:
        parent.kill()
    except psutil.Error:
        pass
    killed.append(parent)

    # Terminate any remaining processes
    for proc in killed:
        try:
            if proc.is_running():
                proc.terminate()
        except psutil.Error:
            pass

def get_user_environment() -> dict[str, str]:
    if sys.platform != "win32":
        return os.environ.copy()

    import ctypes
    from ctypes import wintypes

    # Load required DLLs
    advapi32 = ctypes.WinDLL("advapi32")
    userenv = ctypes.WinDLL("userenv")
    kernel32 = ctypes.WinDLL("kernel32")

    # Constants
    TOKEN_QUERY = 0x0008

    # Function prototypes
    OpenProcessToken = advapi32.OpenProcessToken
    OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    OpenProcessToken.restype = wintypes.BOOL

    CreateEnvironmentBlock = userenv.CreateEnvironmentBlock
    CreateEnvironmentBlock.argtypes = [ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.BOOL]
    CreateEnvironmentBlock.restype = wintypes.BOOL

    DestroyEnvironmentBlock = userenv.DestroyEnvironmentBlock
    DestroyEnvironmentBlock.argtypes = [wintypes.LPVOID]
    DestroyEnvironmentBlock.restype = wintypes.BOOL

    GetCurrentProcess = kernel32.GetCurrentProcess
    GetCurrentProcess.argtypes = []
    GetCurrentProcess.restype = wintypes.HANDLE

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL

    # Get process token
    token = wintypes.HANDLE()
    if not OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise RuntimeError("Failed to open process token")

    try:
        # Create environment block
        environment = ctypes.c_void_p()
        if not CreateEnvironmentBlock(ctypes.byref(environment), token, False):
            raise RuntimeError("Failed to create environment block")

        try:
            # Convert environment block to list of strings
            result = {}
            env_ptr = ctypes.cast(environment, ctypes.POINTER(ctypes.c_wchar))
            offset = 0

            while True:
                # Get string at current offset
                current_string = ""
                while env_ptr[offset] != "\0":
                    current_string += env_ptr[offset]
                    offset += 1

                # Skip null terminator
                offset += 1

                # Break if we hit double null terminator
                if not current_string:
                    break

                equal_index = current_string.index("=")
                if equal_index == -1:
                    continue

                key = current_string[:equal_index]
                value = current_string[equal_index + 1:]
                result[key] = value

            return result

        finally:
            DestroyEnvironmentBlock(environment)

    finally:
        CloseHandle(token)

class FeedbackTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            # Find the parent FeedbackUI instance and call submit
            parent = self.parent()
            while parent and not isinstance(parent, FeedbackUI):
                parent = parent.parent()
            if parent:
                parent._submit_feedback()
        else:
            super().keyPressEvent(event)

class LogSignals(QObject):
    append_log = Signal(str)

class FeedbackUI(QMainWindow):
    def __init__(self, project_directory: str, prompt: str):
        super().__init__()
        self.project_directory = project_directory
        self.prompt = prompt

        self.process: Optional[subprocess.Popen] = None
        self.log_buffer = []
        self.feedback_result = None
        self.log_signals = LogSignals()
        self.log_signals.append_log.connect(self._append_log)

        self.setWindowTitle("Interactive Feedback MCP")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "images", "feedback.png")
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        self.settings = QSettings("InteractiveFeedbackMCP", "InteractiveFeedbackMCP")
        
        # Load general UI settings for the main window (geometry, state)
        self.settings.beginGroup("MainWindow_General")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(800, 600)
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - 800) // 2
            y = (screen.height() - 600) // 2
            self.move(x, y)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
        self.settings.endGroup() # End "MainWindow_General" group
        
        # Load project-specific settings (command, auto-execute, command section visibility)
        self.project_group_name = get_project_settings_group(self.project_directory)
        self.settings.beginGroup(self.project_group_name)
        loaded_run_command = self.settings.value("run_command", "", type=str)
        loaded_execute_auto = self.settings.value("execute_automatically", False, type=bool)
        command_section_visible = self.settings.value("commandSectionVisible", False, type=bool)
        self.settings.endGroup() # End project-specific group
        
        self.config: FeedbackConfig = {
            "run_command": loaded_run_command,
            "execute_automatically": loaded_execute_auto
        }

        self._create_ui() # self.config is used here to set initial values

        # Set command section visibility AFTER _create_ui has created relevant widgets
        self.command_group.setVisible(command_section_visible)
        if command_section_visible:
            self.toggle_command_button.setText("Hide Command Section")
        else:
            self.toggle_command_button.setText("Show Command Section")

        set_dark_title_bar(self, True)

        if self.config.get("execute_automatically", False):
            self._run_command()

    def _format_windows_path(self, path: str) -> str:
        if sys.platform == "win32":
            # Convert forward slashes to backslashes
            path = path.replace("/", "\\")
            # Capitalize drive letter if path starts with x:\
            if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
                path = path[0].upper() + path[1:]
        return path

    def _create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)

        self.toggle_command_button = QPushButton("Show Command Section")
        self.toggle_command_button.clicked.connect(self._toggle_command_section)
        layout.addWidget(self.toggle_command_button)

        # --- Command section ---
        self.command_group = QGroupBox("Command")
        command_layout = QVBoxLayout(self.command_group)
        command_layout.setSpacing(10)

        formatted_path = self._format_windows_path(self.project_directory)
        working_dir_label = QLabel(f"Working directory: {formatted_path}")
        working_dir_label.setObjectName("pathLabel")
        command_layout.addWidget(working_dir_label)

        command_input_layout = QHBoxLayout()
        command_input_layout.setSpacing(8)
        self.command_entry = QLineEdit()
        self.command_entry.setText(self.config["run_command"])
        self.command_entry.setPlaceholderText("Enter command to run...")
        self.command_entry.returnPressed.connect(self._run_command)
        self.command_entry.textChanged.connect(self._update_config)
        self.run_button = QPushButton("&Run")
        self.run_button.setObjectName("primaryButton")
        self.run_button.setMinimumWidth(80)
        self.run_button.clicked.connect(self._run_command)

        command_input_layout.addWidget(self.command_entry)
        command_input_layout.addWidget(self.run_button)
        command_layout.addLayout(command_input_layout)

        auto_layout = QHBoxLayout()
        self.auto_check = QCheckBox("Execute automatically on next run")
        self.auto_check.setChecked(self.config.get("execute_automatically", False))
        self.auto_check.stateChanged.connect(self._update_config)

        save_button = QPushButton("&Save Configuration")
        save_button.clicked.connect(self._save_config)

        auto_layout.addWidget(self.auto_check)
        auto_layout.addStretch()
        auto_layout.addWidget(save_button)
        command_layout.addLayout(auto_layout)

        console_group = QGroupBox("Console")
        console_layout_internal = QVBoxLayout(console_group)
        console_layout_internal.setSpacing(8)
        console_group.setMinimumHeight(200)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        mono_font = QFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        mono_font.setPointSize(11)
        self.log_text.setFont(mono_font)
        console_layout_internal.addWidget(self.log_text)

        button_layout = QHBoxLayout()
        self.clear_button = QPushButton("&Clear")
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_button)
        console_layout_internal.addLayout(button_layout)

        command_layout.addWidget(console_group)

        self.command_group.setVisible(False)
        layout.addWidget(self.command_group)

        # --- Feedback section ---
        self.feedback_group = QGroupBox("Feedback")
        feedback_layout = QVBoxLayout(self.feedback_group)
        feedback_layout.setSpacing(10)

        self.description_label = QLabel(self.prompt)
        self.description_label.setObjectName("promptLabel")
        self.description_label.setWordWrap(True)
        feedback_layout.addWidget(self.description_label)

        self.feedback_text = FeedbackTextEdit()
        font_metrics = self.feedback_text.fontMetrics()
        row_height = font_metrics.height()
        padding = self.feedback_text.contentsMargins().top() + self.feedback_text.contentsMargins().bottom() + 10
        self.feedback_text.setMinimumHeight(5 * row_height + padding)

        self.feedback_text.setPlaceholderText("Enter your feedback here (Ctrl+Enter to submit)")
        self.submit_button = QPushButton("&Send Feedback (Ctrl+Enter)")
        self.submit_button.setObjectName("primaryButton")
        self.submit_button.clicked.connect(self._submit_feedback)

        feedback_layout.addWidget(self.feedback_text)
        feedback_layout.addWidget(self.submit_button)

        self.feedback_group.setMinimumHeight(
            self.description_label.sizeHint().height()
            + self.feedback_text.minimumHeight()
            + self.submit_button.sizeHint().height()
            + feedback_layout.spacing() * 2
            + feedback_layout.contentsMargins().top()
            + feedback_layout.contentsMargins().bottom()
            + 16
        )

        layout.addWidget(self.feedback_group)

        contact_label = QLabel(
            'Contact Fábio Ferreira on <a href="https://x.com/fabiomlferreira">X.com</a>'
            ' · <a href="https://dotcursorrules.com/">dotcursorrules.com</a>'
        )
        contact_label.setObjectName("subtleLabel")
        contact_label.setOpenExternalLinks(True)
        contact_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(contact_label)

    def _toggle_command_section(self):
        is_visible = self.command_group.isVisible()
        self.command_group.setVisible(not is_visible)
        if not is_visible:
            self.toggle_command_button.setText("Hide Command Section")
        else:
            self.toggle_command_button.setText("Show Command Section")

        self.settings.beginGroup(self.project_group_name)
        self.settings.setValue("commandSectionVisible", self.command_group.isVisible())
        self.settings.endGroup()

        central_layout = self.centralWidget().layout()
        QApplication.processEvents()
        hint = self.centralWidget().sizeHint()
        self.resize(self.width(), hint.height() + self.centralWidget().layout().contentsMargins().top() + central_layout.contentsMargins().bottom())

    def _update_config(self):
        self.config["run_command"] = self.command_entry.text()
        self.config["execute_automatically"] = self.auto_check.isChecked()

    def _append_log(self, text: str):
        self.log_buffer.append(text)
        self.log_text.append(text.rstrip())
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def _check_process_status(self):
        if self.process and self.process.poll() is not None:
            exit_code = self.process.poll()
            self._append_log(f"\nProcess exited with code {exit_code}\n")
            self.run_button.setText("&Run")
            self.run_button.setObjectName("primaryButton")
            self.run_button.style().unpolish(self.run_button)
            self.run_button.style().polish(self.run_button)
            self.process = None
            self.activateWindow()
            self.feedback_text.setFocus()

    def _run_command(self):
        if self.process:
            kill_tree(self.process)
            self.process = None
            self.run_button.setText("&Run")
            self.run_button.setObjectName("primaryButton")
            self.run_button.style().unpolish(self.run_button)
            self.run_button.style().polish(self.run_button)
            return

        self.log_buffer = []

        command = self.command_entry.text()
        if not command:
            self._append_log("Please enter a command to run\n")
            return

        self._append_log(f"$ {command}\n")
        self.run_button.setText("Sto&p")
        self.run_button.setObjectName("dangerButton")
        self.run_button.style().unpolish(self.run_button)
        self.run_button.style().polish(self.run_button)

        try:
            self.process = subprocess.Popen(
                command,
                shell=True,
                cwd=self.project_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=get_user_environment(),
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="ignore",
                close_fds=True,
            )

            def read_output(pipe):
                for line in iter(pipe.readline, ""):
                    self.log_signals.append_log.emit(line)

            threading.Thread(
                target=read_output,
                args=(self.process.stdout,),
                daemon=True
            ).start()

            threading.Thread(
                target=read_output,
                args=(self.process.stderr,),
                daemon=True
            ).start()

            # Start process status checking
            self.status_timer = QTimer()
            self.status_timer.timeout.connect(self._check_process_status)
            self.status_timer.start(100)  # Check every 100ms

        except Exception as e:
            self._append_log(f"Error running command: {str(e)}\n")
            self.run_button.setText("&Run")

    def _submit_feedback(self):
        self.feedback_result = FeedbackResult(
            logs="".join(self.log_buffer),
            interactive_feedback=self.feedback_text.toPlainText().strip(),
        )
        self.close()

    def clear_logs(self):
        self.log_buffer = []
        self.log_text.clear()

    def _save_config(self):
        # Save run_command and execute_automatically to QSettings under project group
        self.settings.beginGroup(self.project_group_name)
        self.settings.setValue("run_command", self.config["run_command"])
        self.settings.setValue("execute_automatically", self.config["execute_automatically"])
        self.settings.endGroup()
        self._append_log("Configuration saved for this project.\n")

    def closeEvent(self, event):
        # Save general UI settings for the main window (geometry, state)
        self.settings.beginGroup("MainWindow_General")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.endGroup()

        # Save project-specific command section visibility (this is now slightly redundant due to immediate save in toggle, but harmless)
        self.settings.beginGroup(self.project_group_name)
        self.settings.setValue("commandSectionVisible", self.command_group.isVisible())
        self.settings.endGroup()

        if self.process:
            kill_tree(self.process)
        super().closeEvent(event)

    def run(self) -> FeedbackResult:
        self.show()
        QApplication.instance().exec()

        if self.process:
            kill_tree(self.process)

        if not self.feedback_result:
            return FeedbackResult(logs="".join(self.log_buffer), interactive_feedback="")

        return self.feedback_result

def get_project_settings_group(project_dir: str) -> str:
    # Create a safe, unique group name from the project directory path
    # Using only the last component + hash of full path to keep it somewhat readable but unique
    basename = os.path.basename(os.path.normpath(project_dir))
    full_hash = hashlib.md5(project_dir.encode('utf-8')).hexdigest()[:8]
    return f"{basename}_{full_hash}"

def feedback_ui(project_directory: str, prompt: str, output_file: Optional[str] = None) -> Optional[FeedbackResult]:
    app = QApplication.instance() or QApplication()
    app.setStyle("Fusion")
    app.setPalette(get_dark_mode_palette(app))
    app.setStyleSheet(DARK_STYLESHEET)
    ui = FeedbackUI(project_directory, prompt)
    result = ui.run()

    if output_file and result:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        # Save the result to the output file
        with open(output_file, "w") as f:
            json.dump(result, f)
        return None

    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the feedback UI")
    parser.add_argument("--project-directory", default=os.getcwd(), help="The project directory to run the command in")
    parser.add_argument("--prompt", default="I implemented the changes you requested.", help="The prompt to show to the user")
    parser.add_argument("--output-file", help="Path to save the feedback result as JSON")
    args = parser.parse_args()

    result = feedback_ui(args.project_directory, args.prompt, args.output_file)
    if result:
        print(f"\nLogs collected: \n{result['logs']}")
        print(f"\nFeedback received:\n{result['interactive_feedback']}")
    sys.exit(0)
