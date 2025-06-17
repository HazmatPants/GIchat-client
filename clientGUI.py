import sys
import asyncio
import threading
import os
import json
import time
import random
import base64
import traceback
import markdown
import requests
import uuid
import websockets
import toml
import webbrowser
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton, QTextEdit, QLabel,
                             QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QLineEdit, QDialog,
                             QProgressBar, QMenuBar, QAction, QGridLayout, QLayout)
from PyQt5.QtGui import QIcon, QPixmap, QTextCursor, QFont, QTextDocument
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QCoreApplication, QEventLoop, QMetaObject, QUrl
from PIL import Image
from ping3 import ping
from pygame import mixer

mixer.init()

# === Config and Logging ===
CLI_VERSION = "2.1.2"
CLI_DIR = os.path.dirname(__file__)
os.chdir(CLI_DIR)

LOG_FILE = os.path.join(CLI_DIR, "latest.log")
CONFIG_FILE = os.path.join(CLI_DIR, "config.toml")

with open(LOG_FILE, "w") as f:
    f.write("")

def log(msg):
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        toml.dump(data, f)

def load_config():
    try:
        data = toml.load(CONFIG_FILE)
        log("Config Loaded")
        return data
    except toml.TomlDecodeError:
        log("Invalid Config TOML")
        QMessageBox.critical(None, "TOML Decode Error",
                             "Config file contains invalid TOML. Fix the issues or delete it to generate a new one.")
        sys.exit()
    except FileNotFoundError:
        log("Config file missing, using defaults")
        data = {
            "client": {
                "username": f"NewUser_{random.randint(1, 1000000)}",
                "font": {"name": "Helvetica", "size": 10},
                "admin_key": "",
                "soundpack": "gichat"
            },
            "server": {
                "host": "grigga-industries.ydns.eu",
                "port": 8765
            }
        }
        save_config(data)
        return data

# === Utility ===
def playsound(path):
    mixer.Sound(path).play()

def playerror():
    errorSoundPath = os.path.join("assets", "sounds", "error.wav")
    if os.path.exists(errorSoundPath):
        playsound(errorSoundPath)

def playeventsound(event):
    path = os.path.join("assets", "sounds", CLI_CONFIG["client"]["soundpack"], f"{event}.wav")
    if os.path.exists(path):
        playsound(path)
    else:
        log(f"sound `{path}` not found!")
        playerror()

def b64encode(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def b64decode(b64string):
    return base64.b64decode(b64string)

def markdown_to_html(markdown_text):
    html_output = markdown.markdown(markdown_text)
    return html_output

# === Async Communication Handler ===
class Communicator(QObject):
    print_to_console = pyqtSignal(str, object)
    load_messages = pyqtSignal(list)
    show_conf = pyqtSignal()
    clear_console = pyqtSignal()

class ConfigWindow(QMainWindow):
    def __init__(self, chat_client):
        super().__init__()
        
        self.chat = chat_client
        self.loop = asyncio.get_event_loop()
        self.setWindowTitle("Configuration")
        self.setFixedSize(350, 300)
        self.setStyleSheet("background-color: black; color: white;")
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        
        layout = QGridLayout()
        
        self.username_label = QLabel("Username:", self)
        layout.addWidget(self.username_label, 1, 0)
        self.username_field = QLineEdit(self)
        layout.addWidget(self.username_field, 1, 1)
        self.username_field.setText(CLI_CONFIG["client"]["username"])
        
        self.soundpack_label = QLabel("Sound Pack:", self)
        layout.addWidget(self.soundpack_label, 2, 0)
        self.soundpack_field = QLineEdit(self)
        layout.addWidget(self.soundpack_field, 2, 1)
        self.soundpack_field.setText(CLI_CONFIG["client"]["soundpack"])
        
        self.adminkey_label = QLabel("Admin Key:", self)
        layout.addWidget(self.adminkey_label, 3, 0)
        self.adminkey_field = QLineEdit(self)
        layout.addWidget(self.adminkey_field, 3, 1)
        self.adminkey_field.setText(CLI_CONFIG["client"]["admin_key"])
        self.adminkey_field.setEchoMode(QLineEdit.EchoMode.Password)

        self.seperator1 = QWidget(self)
        self.seperator1.setMaximumHeight(20)
        layout.addWidget(self.seperator1, 4, 0)
        
        self.font_name_label = QLabel("Font Name:", self)
        layout.addWidget(self.font_name_label, 5, 0)
        self.font_name_field = QLineEdit(self)
        layout.addWidget(self.font_name_field, 5, 1)
        self.font_name_field.setText(CLI_CONFIG["client"]["font"]["name"])
        
        self.font_size_label = QLabel("Font Size:", self)
        layout.addWidget(self.font_size_label, 6, 0)
        self.font_size_field = QLineEdit(self)
        layout.addWidget(self.font_size_field, 6, 1)
        self.font_size_field.setText(str(CLI_CONFIG["client"]["font"]["size"]))

        self.seperator2 = QWidget(self)
        self.seperator2.setMaximumHeight(20)
        layout.addWidget(self.seperator2, 7, 0)
        
        self.host_label = QLabel("Host:", self)
        layout.addWidget(self.host_label, 8, 0)
        self.host_field = QLineEdit(self)
        layout.addWidget(self.host_field, 8, 1)
        self.host_field.setText(CLI_CONFIG["server"]["host"])
        
        self.port_label = QLabel("Port:", self)
        layout.addWidget(self.port_label, 9, 0)
        self.port_field = QLineEdit(self)
        layout.addWidget(self.port_field, 9, 1)
        self.port_field.setText(str(CLI_CONFIG["server"]["port"]))
        
        self.seperator3 = QWidget(self)
        self.seperator3.setMaximumHeight(20)
        layout.addWidget(self.seperator3, 10, 0)
        
        self.save_button = QPushButton("Save", self)
        self.save_button.setStyleSheet("background-color: #424242; color: white; border-radius: 1px; padding: 8px 10px;")
        self.save_button.clicked.connect(self.save_config_window)
        layout.addWidget(self.save_button, 11, 0)
        
        layout.setAlignment(Qt.AlignHCenter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
    def save_config_window(self):
        self.error = False
        try:
            data = {
                "client": {
                    "username": self.username_field.text(),
                    "font": {"name": self.font_name_field.text(), "size": int(self.font_size_field.text())},
                    "admin_key": self.adminkey_field.text(),
                    "soundpack": self.soundpack_field.text()
                },
                "server": {
                    "host": self.host_field.text(),
                    "port": self.port_field.text()
                }
            }
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
            self.error = True
        
        if not self.error:
            save_config(data)
            QMessageBox.information(self, "Changes require restart", "Client will now exit to apply changes.")
            self.destroy()
            exit()

class LoadingWindow(QMainWindow):
    def __init__(self, messages, chat_client):
        super().__init__()

        self.chat = chat_client
        self.messages = messages
        self.setWindowTitle("Loading...")
        self.setStyleSheet("background-color: black;")
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setFixedSize(350, 150)

        layout = QVBoxLayout()

        self.loading_label = QLabel("Loading Messages...", self)
        self.loading_label.setStyleSheet("color: white;")
        layout.addWidget(self.loading_label)
        
        self.progress = QProgressBar(self)
        self.progress.setStyleSheet("QProgressBar {color: white; background-color: #333;} QProgressBar::chunk {background-color: #05B8CC;}")
        self.progress.setMaximum(len(self.messages))
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        container = QWidget(self)
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.idx = 0
        
        self.chat.clear_console()
        
        QTimer.singleShot(0, self.process_messages)

    def process_messages(self):
        for self.idx, message in enumerate(self.messages):
            message = self.messages[self.idx]
            username, content, timestamp = message
            if content.startswith("[Image] http"):
                url = content.split(" ", 1)[1]
                try:
                    image_req = requests.get(url)
                    if image_req.ok:
                        image_data = image_req.content
                        pixmap = QPixmap()
                        pixmap.loadFromData(image_data)
                        pixmap = pixmap.scaledToWidth(300, Qt.SmoothTransformation)
                        self.chat.comm.print_to_console.emit(f"[{timestamp}] &lt;{username}&gt; sent an image: {url}", None)
                        self.chat.comm.print_to_console.emit("", pixmap)
                    else:
                        self.chat.comm.print_to_console.emit(f"<p style='color: #ff5555;'>[{timestamp}] &lt;{username}&gt; sent an image but it failed to load (error {image_req.status_code})</p>", None)
                except Exception as e:
                    self.chat.comm.print_to_console.emit("Failed to load image.", None)
                    log(f"Image load error: {e}")
            else:
                html = markdown_to_html(content.strip())
                self.chat.comm.print_to_console.emit(f"[{timestamp}] &lt;{username}&gt;", None)
                self.chat.comm.print_to_console.emit(html, None)
            self.progress.setValue(self.idx + 1)
            log(f"loaded message {self.idx}")
            QCoreApplication.processEvents()

        self.close()

class ChatInput(QTextEdit):
    enter_pressed = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() == Qt.ShiftModifier:
                super().keyPressEvent(event) # allow newline
            else:
                event.accept()
                self.enter_pressed.emit() # emit signal to send message
        else:
            super().keyPressEvent(event)

class ChatClient(QMainWindow):
    def __init__(self):
        super().__init__()

        self.websocket = None
        self.loop = asyncio.new_event_loop()
        self.shutdown_flag = False

        self.comm = Communicator()
        self.comm.print_to_console.connect(self.print_to_console)
        self.comm.load_messages.connect(self.show_loading_window)
        self.comm.show_conf.connect(self.show_config_window)
        
        
        self.init_ui()
        
        self.comm.clear_console.connect(self.console.clear)

        threading.Thread(target=self.start_asyncio_loop, daemon=True).start()

    def show_loading_window(self, messages):
        self.loading_window = LoadingWindow(messages, self)
        self.loading_window.show()
    
    def show_config_window(self):
        self.conf_window = ConfigWindow(self)
        self.conf_window.show()

    def init_ui(self):
        self.setWindowTitle(f"GIchat Client {CLI_VERSION}")
        self.setStyleSheet("background-color: #000000; color: white")
        self.setGeometry(100, 100, 900, 500)
        self.setWindowIcon(QIcon("assets/images/GIchat_Icon.ico"))

        self.console = QTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setFont(QFont(CLI_CONFIG["client"]["font"]["name"], CLI_CONFIG["client"]["font"]["size"]))
        self.console.setStyleSheet("background-color: #232323; color: white")

        self.message_input = ChatInput(self)
        self.message_input.setFixedHeight(50)
        self.message_input.setStyleSheet("background-color: #232323; color: white")
        self.message_input.enter_pressed.connect(self.send_message)
        
        self.server_status_label = QLabel("Offline", self)
        self.server_status_label.setStyleSheet("background-color: #000000; color: white")
        
        self.server_status_dot = QLabel()
        self.server_status_dot.setFixedSize(10, 10)
        self.server_status_dot.setStyleSheet("background-color: red; border-radius: 5px;")

        send_button = QPushButton(">", self)
        send_button.clicked.connect(self.send_message)
        send_button.setFixedWidth(50)
        send_button.setStyleSheet("background-color: #424242; color: white; border-radius: 1px; padding: 8px 10px;")

        file_button = QPushButton("Send\nImage", self)
        file_button.clicked.connect(self.send_file)
        file_button.setStyleSheet("background-color: #424242; color: white; border-radius: 1px; padding: 8px 10px;")

        ping_button = QPushButton("Ping", self)
        ping_button.clicked.connect(self.ping_server)
        ping_button.setStyleSheet("background-color: #424242; color: white; border-radius: 1px; padding: 8px 10px;")

        clear_button = QPushButton("Clear", self)
        clear_button.clicked.connect(lambda: self.console.clear())
        clear_button.setStyleSheet("background-color: #424242; color: white; border-radius: 1px; padding: 8px 10px;")

        disconnect_button = QPushButton("Disconnect", self)
        disconnect_button.clicked.connect(lambda: asyncio.run_coroutine_threadsafe(self.disconnect(reason="client"), self.loop))
        disconnect_button.setStyleSheet("background-color: #424242; color: white; border-radius: 1px; padding: 8px 10px;")

        reconnect_button = QPushButton("Reconnect", self)
        reconnect_button.clicked.connect(lambda: asyncio.run_coroutine_threadsafe(self.reconnect(), self.loop))
        reconnect_button.setStyleSheet("background-color: #424242; color: white; border-radius: 1px; padding: 8px 10px;")

        # Layouts
        button_layout = QVBoxLayout()
        button_layout.addWidget(ping_button)
        button_layout.addWidget(disconnect_button)
        button_layout.addWidget(reconnect_button)
        button_layout.addWidget(clear_button)
        button_layout.addWidget(file_button)

        message_layout = QHBoxLayout()
        message_layout.addWidget(self.message_input)
        message_layout.addWidget(send_button)

        main_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.console)
        
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.server_status_dot)
        status_layout.addWidget(self.server_status_label)
        status_layout.addStretch()

        central_widget = QWidget()
        central_layout = QVBoxLayout()
        central_layout.addLayout(status_layout)
        central_layout.addLayout(main_layout)
        central_layout.addLayout(message_layout)
        central_widget.setLayout(central_layout)

        self.setCentralWidget(central_widget)

        # Menu bar
        menubar = QMenuBar(self)
        options_menu = menubar.addMenu("Options")

        credits_action = QAction("Credits", self)
        credits_action.triggered.connect(lambda: QMessageBox.information(self, "Credits",
                                                                         "Made by GI\nWritten in Python 3.10 with PyQt5"))
        options_menu.addAction(credits_action)
        
        bugreport_action = QAction("Report bug", self)
        bugreport_action.triggered.connect(lambda: webbrowser.open("https://github.com/HazmatPants/GIchat-client-2.0/issues/new"))
        
        options_menu.addAction(bugreport_action)
        
        conf_action = QAction("Settings", self)
        conf_action.triggered.connect(self.comm.show_conf.emit)
        
        options_menu.addAction(conf_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(lambda: asyncio.run_coroutine_threadsafe(self.client_exit(), self.loop))
        options_menu.addAction(exit_action)

        self.setMenuBar(menubar)

    def print_to_console(self, text, image=None):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.console.setTextCursor(cursor)

        if image and isinstance(image, QPixmap):
            image_id = str(uuid.uuid4())  # unique ID per image
            self.console.insertPlainText("\n")
            self.console.document().addResource(
                QTextDocument.ImageResource,
                QUrl(image_id),
                image
            )
            cursor.insertImage(image_id)
            self.console.insertPlainText("\n")
        elif isinstance(image, str):
            self.console.insertHtml(f'<img src="{image}" width="200">')

        if text:
            self.console.insertHtml(text + "<br>")

        self.console.moveCursor(QTextCursor.End)

    
    def clear_console(self):
        self.comm.clear_console.emit()
    
    async def retrieve_messages(self):
        data = {
            "username": username,
            "message": "RAW:MSGDB",
            "event": "request",
            "type": "msg"
        }
        await self.websocket.send(json.dumps(data))
        log("Requesting message DB from server...")

        messages = await self.websocket.recv()
        messages = json.loads(messages)
        log(f"Retrieved {len(messages)} messages from server")

        self.comm.load_messages.emit(messages)

    def ping_server(self):
        responsetime = ping(host)
        if responsetime:
            QMessageBox.information(self, "Ping Successful",
                                    f"Response Time: {round(responsetime * 1000, 2)}ms")
        else:
            QMessageBox.critical(self, "Ping Failed", "Host unreachable")

    def start_asyncio_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.connect())
        except ConnectionRefusedError:
            QMessageBox.critical(self, "Connection Error", "Connection Refused")
        while not self.shutdown_flag:
            self.loop.run_forever()

    async def connect(self):
        uri = f"ws://{host}:{port}"
        try:
            self.websocket = await websockets.connect(uri)
            await self.websocket.send(username)
            server_info = await self.websocket.recv()
            server_info = json.loads(server_info)
            playeventsound("connect")
            data = {
                "username": username,
                "message": "RAW:USERLIST",
                "event": "request",
                "type": "msg"
            }
            await self.websocket.send(json.dumps(data))
            log(f"Requesting user list from server...")
            online_users = await self.websocket.recv()
            online_users = json.loads(online_users)
            log(f"Retrieved user list")
            await self.retrieve_messages()
            self.comm.print_to_console.emit(f"Connected to &quot;{server_info['name']}&quot; ({uri})", None)
            if type(online_users) == list:
                users = ", ".join(online_users)
                self.comm.print_to_console.emit("Online Users: " + users + "<br>", None)
            self.server_status_label.setText(f"Connected to \"{server_info['name']}\" ({uri})")
            self.server_status_dot.setStyleSheet("background-color: #00ff00; border-radius: 5px;")
            await self.receive_messages()
        except Exception as e:
            self.comm.print_to_console.emit(f"<p style='color: #ff5555;'> Connection failed: {e}</p>", None)
            traceback.print_exc()
            playerror()

    async def disconnect(self, reason: str):
        if self.websocket:
            try:
                await self.websocket.close(reason="Client Disconnect")
            except Exception as e:
                log(f"WebSocket close error: {e}")
            self.websocket = None
            if reason == "client":
                playeventsound("disconnect")
            elif reason == "kick":
                playeventsound("kicked")
            self.comm.print_to_console.emit("Disconnected.", None)
            self.server_status_label.setText("Offline")
            self.server_status_dot.setStyleSheet("background-color: red; border-radius: 5px;")

    async def reconnect(self):
        self.comm.print_to_console.emit("Reconnecting...", None)
        await self.disconnect(reason="reconnect")
        await self.connect()

    async def client_exit(self):
        self.shutdown_flag = True
        await self.disconnect(reason="client")
        log("Client exited")
        self.close()
        os._exit(0)

    def send_message(self):
        msg = self.message_input.toPlainText().strip()
        if msg:
            self.message_input.clear()
            asyncio.run_coroutine_threadsafe(self._send_message(msg), self.loop)

    async def _send_message(self, msg):
        data = {
            "type": "msg",
            "username": username,
            "message": msg,
            "event": "send_message",
            "admin_key": CLI_CONFIG["client"].get("admin_key", " ")
        }

        if self.websocket and self.websocket.open:
            await self.websocket.send(json.dumps(data))
            playeventsound("send_message")
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if msg.startswith("[Image] http"):
                url = msg.split(" ", 1)[1]
                self.comm.print_to_console.emit(f"[{timestamp}] &lt;{username}&gt; sent an image: {url}", None)
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    image_data = response.content
                    pixmap = QPixmap()
                    pixmap.loadFromData(image_data)
                    pixmap = pixmap.scaledToWidth(300, Qt.SmoothTransformation)
                    self.comm.print_to_console.emit("", pixmap)
                except Exception as e:
                    self.comm.print_to_console.emit("Failed to load image.", None)
                    log(f"Image load error (sender): {e}")
            else:
                self.comm.print_to_console.emit(f"[{timestamp}] &lt;{username}&gt;", None)
                msg_html = markdown_to_html(msg)
                self.comm.print_to_console.emit(msg_html, None)

    def send_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select a file", "", "Image files (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.xpm *.ico)")
        if file_path:
            files = {'file': open(file_path, 'rb')}
            response = requests.post(f"http://{host}:8000/upload", files=files)
            if response.ok:
                filename = response.json()['filename']
                msg = f"[Image] http://{host}:8000/uploads/{filename}"
                asyncio.run_coroutine_threadsafe(self._send_message(msg), self.loop)

    async def receive_messages(self):
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    if data["event"] == "srv_message":
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        self.comm.print_to_console.emit(f"[{timestamp}] &lt;{data['username']}&gt;", None)
                        self.comm.print_to_console.emit(data['message'] + "<br>", None)
                        if "join" in data['message']:
                            playeventsound("user_join")
                        elif "left" in data['message']:
                            playeventsound("user_leave")
                        elif "have been kicked" in data['message']:
                            await self.disconnect("kick")
                    elif data["event"] == "srv_command":
                        if data['message'] == "CLEAR_MESSAGE_DB":
                            self.comm.clear_console.emit()
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            self.comm.print_to_console.emit(f"[{timestamp}] &lt;server&gt;", None)
                            self.comm.print_to_console.emit("Message DB was cleared.", None)
                    else:
                        if data["type"] == "msg" and not data["event"] == "request":
                            message = data['message']
                            if message.startswith("[Image] http"):
                                url = message.split(" ", 1)[1]
                                try:
                                    image_data = requests.get(url).content
                                    pixmap = QPixmap()
                                    pixmap.loadFromData(image_data)
                                    pixmap = pixmap.scaledToWidth(300, Qt.SmoothTransformation)
                                    self.comm.print_to_console.emit(f"[{timestamp}] &lt;{data['username']}&gt; sent an image: {url}", pixmap)
                                except Exception as e:
                                    self.comm.print_to_console.emit("Failed to load image.", None)
                                    log(f"Image load error: {e}")
                            elif message.startswith("[File] http"):
                                url = message.split(" ", 1)[1]
                                self.comm.print_to_console.emit(f"[{timestamp}] &lt;{data['username']}&gt; sent an file: {url}")
                            else:
                                msg_html = markdown_to_html(data['message'])
                                self.comm.print_to_console.emit(f"[{timestamp}] &lt;{data['username']}&gt;", None)
                                self.comm.print_to_console.emit(msg_html, None)
                            
                        playeventsound("rcv_message")
                except json.JSONDecodeError:
                    self.comm.print_to_console.emit("Received invalid JSON", None)
                except Exception as e:
                    log(f"Error occurred when receiving a message: {e}")
        except websockets.exceptions.ConnectionClosed:
            self.comm.print_to_console.emit("Connection closed.", None)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    try:
        CLI_CONFIG = load_config()
        username = CLI_CONFIG["client"]["username"]
        host = CLI_CONFIG["server"]["host"]
        port = CLI_CONFIG["server"]["port"]
    except Exception as e:
        QMessageBox.critical(None, "Config Error", str(e))
        sys.exit(1)
    window = ChatClient()
    window.show()
    sys.exit(app.exec_())
