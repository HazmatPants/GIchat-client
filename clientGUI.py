from tkinter import messagebox 
import tkinter as tk # for GUI

from ping3 import ping # for pinging the server
import time # for timestamps
import asyncio # for async functions
import websockets # for communication with the server
import threading # for running multiple functions at once
import json # for sending multiple values to the server
import os
from pygame import mixer # for sound effects

mixer.init()

def playsound(sound: str):
    mixer.Sound(sound).play()

def playeventsound(event: str):
    if event == "send_message":
        playsound("sounds/send.wav")
    elif event == "rcv_message":
        playsound("sounds/receive.wav")
    elif event == "connect":
        playsound("sounds/connect.wav")
    elif event == "disconnect":
        playsound("sounds/disconnect.wav")

username="test42"

# Initialize Tkinter
root = tk.Tk()
root.title("GIchat Client 1.3")
root.geometry("700x500")
root.grid_columnconfigure(1, weight=1)  # Allow text widget to expand
root.grid_rowconfigure(0, weight=1)     # Allow window resizing
root.configure(bg="black")

# Global Variables
websocket = None
loop = None
asyncio_thread = None
shutdown_flag = False # if this is true, program and threads will shutdown

host = "192.168.0.41"
port = 8765

# Function to print messages to the text console
def consoleprint(text: str):
    def updateconsole():
        text_console.config(state=tk.NORMAL)
        text_console.insert(tk.END, text + "\n")
        text_console.config(state=tk.DISABLED)
    
    root.after(0, updateconsole)

# Function to ping the server
def pingserver() -> float:
    responsetime = ping(dest_addr=host)
    if responsetime is None or responsetime is False:
        consoleprint("Ping Failed")
        messagebox.showerror(title="Ping Failed", message="Host unreachable")
    else:
        consoleprint(f"Ping Success: {str(round(responsetime, 3) * 1000)}ms")
        print("ping success:", responsetime)
        messagebox.showinfo(title="Ping Sucessful", message="Response Time: " + str(round(responsetime, 3) * 1000) + "ms")

# Menu bar for the app
menubar = tk.Menu(root)
root.config(menu=menubar)

# Show credits window
def showcredits():
    messagebox.showinfo(title="Credits", message="Made by Grigga Industries\nWritten in Python 3.10")

# Connect to the WebSocket server
async def connect():
    global websocket
    global username
    uri = "ws://" + host + ":" + str(port)
    websocket = await websockets.connect(uri)
    
    await websocket.send(username)
    
    srv_info = json.loads(await websocket.recv())
    consoleprint(f"Connected to {srv_info['name']} ({uri})\nThis server is running version {srv_info['version']}")
    playeventsound("connect")
    await receive_messages()

async def disconnect(silent: bool=False):
    global websocket
    
    if websocket:
        try:
            await websocket.close(reason="Client exiting")
        except Exception as e:
            consoleprint(f"Error closing WebSocket: {e}")
        finally:
            websocket = None  # Ensure it's fully cleaned up
            
        if not silent:
            playeventsound("disconnect")
        consoleprint("Disconnected.")
    else:
        consoleprint("Error: Not connected to a server")

async def reconnect():
    global websocket, loop
    consoleprint("Attempting to reconnect...")

    if websocket:
        await websocket.close()

    try:
        await connect()
        consoleprint("Reconnected successfully!")
    except Exception as e:
        consoleprint(f"Reconnection failed: {e}")

async def client_exit():
    global shutdown_flag
    shutdown_flag = True  

    try:
        asyncio.create_task(disconnect())
    except Exception as e:
        consoleprint(f"Error during exit: {e}")

    root.quit() 
    os._exit(0)
    
root.protocol("WM_DELETE_WINDOW", lambda: asyncio.run_coroutine_threadsafe(client_exit(), loop))

menu_info = tk.Menu(menubar, tearoff=0)
menu_info.add_command(label="Credits", command=showcredits)
menu_info.add_command(label="Exit", command=lambda: asyncio.run_coroutine_threadsafe(client_exit(), loop))
menubar.add_cascade(label="Options", menu=menu_info)

# Frame to hold buttons
frame_button = tk.Frame(root, bg="black")
frame_button.grid(row=0, column=0, padx=5, pady=5, sticky="ns")

button_ping = tk.Button(frame_button, text="Ping", width=8, bg="#232323", fg="#ffffff", command=pingserver)

# Received messages and errors go to the text console
text_console = tk.Text(root, width=30, height=10, bg="#232323", fg="#ffffff")

button_ping.pack()

button_disconnect = tk.Button(frame_button, text="Disconnect", width=8, bg="#232323", fg="#ffffff",
                              command=lambda: asyncio.run_coroutine_threadsafe(disconnect(), loop))
button_disconnect.pack()

button_reconnect = tk.Button(frame_button, text="Reconnect", width=8, bg="#232323", fg="#ffffff",
                             command=lambda: asyncio.run_coroutine_threadsafe(reconnect(), loop))
button_reconnect.pack()

text_console.grid(row=0, column=1, pady=5, columnspan=2, sticky="nsew")
text_console.config(state=tk.DISABLED)

messagefield = tk.Text(root, bg="#232323", fg="#ffffff", height=2)
messagefield.grid(row=3, column=1, columnspan=1, pady=5, sticky="ew")

# Function to send the message
async def sendmessage():
    global websocket
    message = messagefield.get("1.0", tk.END)  # Get the message from the field
    messagefield.delete("1.0", tk.END)
    if message:
        message_data = {
            "username": username,
            "message": message,
            "event": "send_message"
            }
        
        message_json = json.dumps(message_data)
        
        timestamp = time.time()
        
        if websocket and websocket.open:
            await websocket.send(message_json)
            playeventsound("send_message")
            root.after(0, consoleprint, f"{username} (You): {message}")
            print(f"Sent {message.strip()} at {timestamp:.4f}")
        else:
            consoleprint("Error: Not connected to a server")

# Function to handle receiving messages
async def receive_messages():
    global websocket
    try:
        async for message in websocket:
            try:
                message_data = json.loads(message)
                print(f"Received data: {message_data}")
            except json.JSONDecodeError:
                consoleprint("Received invalid data: " + message)
            if message_data["event"] == "srv_message":
                playeventsound("srv_message")
                consoleprint(message_data["username"] + ": " + message_data["message"])
            elif message_data["event"] == "send_message":
                playeventsound("rcv_message")
                consoleprint(message_data["username"] + ": " + message_data["message"])
    except websockets.exceptions.ConnectionClosed:
        consoleprint("Connection to server closed")

# Tkinter button command to send messages
def send_button_click():
    global loop
    if loop:
        asyncio.run_coroutine_threadsafe(sendmessage(), loop)
    else:
        print("No event loop")

# Start the WebSocket connection in the background
def start_asyncio_loop():
    global loop
    loop = asyncio.new_event_loop()  # Create a new event loop
    asyncio.set_event_loop(loop)  # Set it as the current event loop
    try:
        loop.run_until_complete(connect())  # Start the connection
    except ConnectionRefusedError:
        tk.messagebox.showerror(title="Failed to connect...", message="Error: Connection Refused")
    while not shutdown_flag:
        loop.run_forever()  # Keep the loop running

# Add button to send message
button_send = tk.Button(root, width=5, text="Send", bg="#232323", fg="#ffffff", command=send_button_click)
button_send.grid(row=3, column=2)

# Start the asyncio event loop in a separate thread to avoid blocking Tkinter
asyncio_thread = threading.Thread(target=start_asyncio_loop, daemon=True)
asyncio_thread.start()

root.mainloop()