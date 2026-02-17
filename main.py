from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, Message

Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

active_connections = []  # List of tuples: (websocket, username)

# Hilfsfunktion: alle Usernamen der aktiven Verbindungen
def get_active_usernames():
    return list(set(username for _, username in active_connections))

@app.get("/")
async def get(request: Request):
    db: Session = SessionLocal()
    try:
        messages = db.query(Message).all()
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "messages": messages}
        )
    finally:
        db.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, username: str = Query(...)):
    await websocket.accept()
    active_connections.append((websocket, username))

    # Alle Clients über neue Userliste informieren
    async def broadcast_users():
        users = get_active_usernames()
        for conn, _ in active_connections:
            try:
                await conn.send_text("__users__:" + ",".join(users))
            except:
                pass

    await broadcast_users()

    db: Session = SessionLocal()
    try:
        while True:
            data = await websocket.receive_text()

            # Nachricht speichern
            msg = Message(username=username, content=data)
            db.add(msg)
            db.commit()
            db.refresh(msg)

            # Nachricht an alle anderen Clients senden
            for conn, _ in active_connections:
                if conn != websocket:
                    try:
                        await conn.send_text(f"{msg.username}: {msg.content}")
                    except:
                        pass
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.remove((websocket, username))
        await broadcast_users()  # Update user list
        db.close()

import os

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
