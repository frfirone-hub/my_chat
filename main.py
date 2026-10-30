from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List
import sqlite3
import datetime

app = FastAPI()

DB_FILE = "chat.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            text TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>واتساب مصغر - تعديل الشاشات</title>
        <style>
            body { font-family: Tahoma, sans-serif; direction: rtl; text-align: right; background: #e5ddd5; margin: 0; padding: 20px; }
            .chat-container { max-width: 450px; margin: 0 auto; background: #efeae2; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.2); display: flex; flex-direction: column; height: 80vh; overflow: hidden; }
            .chat-header { background: #075e54; color: white; padding: 15px; font-size: 16px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
            .clear-btn { background: #d9534f; color: white; border: none; padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 12px; }
            .clear-btn:hover { background: #c9302c; }
            
            #messages { list-style-type: none; padding: 15px; margin: 0; flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
            
            .message-bubble { padding: 8px 12px; border-radius: 7.5px; max-width: 75%; word-wrap: break-word; font-size: 14px; position: relative; box-shadow: 0 1px 0.5px rgba(0,0,0,0.13); }
            .my-message { background: #dcf8c6; align-self: flex-start; }
            .other-message { background: #ffffff; align-self: flex-end; }
            .system-msg { background: #e2e8f0; color: #555; align-self: center; font-style: italic; font-size: 12px; border-radius: 5px; }
            
            .msg-user { font-weight: bold; font-size: 11px; color: #128c7e; margin-bottom: 2px; }

            .input-form { display: flex; padding: 10px; background: #f0f0f0; gap: 8px; }
            input[type="text"] { padding: 10px; flex: 1; border: 1px solid #ccc; border-radius: 20px; outline: none; padding-right: 15px; }
            button[type="submit"] { padding: 10px 20px; background: #075e54; color: white; border: none; border-radius: 20px; cursor: pointer; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <div class="chat-header">
                <span>💬 غرفة المحادثة</span>
                <button class="clear-btn" onclick="clearChat()">مسح المحادثة</button>
            </div>
            
            <!-- شاشة إدخال الاسم (تظهر في البداية فقط) -->
            <div id="username-screen" style="padding: 40px 20px; text-align: center; margin: auto;">
                <h3 style="color: #075e54; margin-bottom: 20px;">أدخل اسمك للانضمام</h3>
                <input type="text" id="usernameInput" placeholder="اسم المستخدم..." style="width: 100%; margin-bottom: 15px; padding: 10px; border-radius: 5px; border: 1px solid #ccc; box-sizing: border-box;" /><br>
                <button onclick="joinChat()" style="padding: 10px 30px; background: #075e54; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold;">دخول الشات</button>
            </div>

            <!-- شاشة الشات والرسائل (مخفية تماماً في البداية) -->
            <div id="chat-screen" style="display: none; flex-direction: column; height: 100%;">
                <ul id='messages'></ul>
                <form action="" onsubmit="sendMessage(event)" class="input-form">
                    <input type="text" id="messageText" autocomplete="off" placeholder="اكتب رسالة..." />
                    <button type="submit">إرسال</button>
                </form>
            </div>
        </div>

        <script>
            var ws = null;
            var username = "";

            function joinChat() {
                var input = document.getElementById("usernameInput");
                if (input.value.trim() === "") return;
                
                username = input.value.trim();
                ws = new WebSocket("ws://localhost:8000/ws/" + encodeURIComponent(username));

                ws.onmessage = function(event) {
                    var data = event.data;
                    var messages = document.getElementById('messages');
                    
                    if (data === "CLEAR_ALL_SCREEN") {
                        messages.innerHTML = "";
                        return;
                    }

                    var messageLi = document.createElement('li');
                    messageLi.className = "message-bubble";

                    if (data.startsWith("🔔") || data.startsWith("❌")) {
                        messageLi.className += " system-msg";
                        messageLi.textContent = data;
                    } else {
                        var parts = data.split(": ");
                        var sender = parts[0];
                        var rest = parts.slice(1).join(": ");
                        
                        if (sender === username) {
                            messageLi.className += " my-message";
                        } else {
                            messageLi.className += " other-message";
                        }
                        
                        messageLi.innerHTML = `<div class="msg-user">${sender}</div><div>${rest}</div>`;
                    }

                    messages.appendChild(messageLi);
                    messages.scrollTop = messages.scrollHeight;
                };

                // إخفاء شاشة الاسم تماماً وإظهار شاشة الشات
                document.getElementById("username-screen").style.display = "none";
                document.getElementById("chat-screen").style.display = "flex";
            }

            function sendMessage(event) {
                var input = document.getElementById("messageText");
                if (input.value.trim() !== "") {
                    ws.send(input.value);
                    input.value = '';
                }
                event.preventDefault();
            }

            function clearChat() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send("CLEAR_CHAT_COMMAND");
                }
            }
        </script>
    </body>
</html>
"""

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT sender, text, timestamp FROM messages ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            sender, text, timestamp = row
            if sender == "SYSTEM":
                await websocket.send_text(f"{text}")
            else:
                await websocket.send_text(f"{sender}: {text} ({timestamp})")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws/{client_name}")
async def websocket_endpoint(websocket: WebSocket, client_name: str):
    await manager.connect(websocket)
    
    join_msg = f"🔔 انضم {client_name} إلى المحادثة"
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (sender, text, timestamp) VALUES (?, ?, ?)", 
                   ("SYSTEM", join_msg, datetime.datetime.now().strftime("%H:%M")))
    conn.commit()
    conn.close()
    
    await manager.broadcast(join_msg)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            if data == "CLEAR_CHAT_COMMAND":
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM messages")
                conn.commit()
                conn.close()
                await manager.broadcast("CLEAR_ALL_SCREEN")
                continue

            current_time = datetime.datetime.now().strftime("%H:%M")
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (sender, text, timestamp) VALUES (?, ?, ?)", 
                           (client_name, data, current_time))
            conn.commit()
            conn.close()

            await manager.broadcast(f"{client_name}: {data} ({current_time})")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        leave_msg = f"❌ غادر {client_name} المحادثة"
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (sender, text, timestamp) VALUES (?, ?, ?)", 
                       ("SYSTEM", leave_msg, datetime.datetime.now().strftime("%H:%M")))
        conn.commit()
        conn.close()
        
        await manager.broadcast(leave_msg)