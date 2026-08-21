
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3, hashlib, secrets, shutil

APP = FastAPI(title="Van Hoa Doc API")
APP.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)
DB = BASE / "vhd.db"
TOKENS = {}

APP.mount("/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")
APP.mount("/static", StaticFiles(directory=str(BASE.parent / "frontend")), name="static")

@APP.get("/")
def home():
    return FileResponse(str(BASE.parent / "frontend" / "index.html"))

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      name TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
      class_name TEXT DEFAULT '',
      active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS posts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      book_title TEXT NOT NULL,
      tag TEXT NOT NULL,
      content TEXT NOT NULL,
      rating INTEGER NOT NULL,
      image_url TEXT DEFAULT '',
      file_url TEXT DEFAULT '',
      url TEXT DEFAULT '',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS likes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      post_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      UNIQUE(post_id,user_id)
    );
    CREATE TABLE IF NOT EXISTS comments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      post_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      content TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    """)
    for username,pwd,name,role,cls in [
      ("hs001","123456","Nguyễn Minh Anh","student","5A1"),
      ("gv001","123456","Giáo viên Demo","teacher","5A1"),
      ("admin","admin123","Quản trị viên","admin","")
    ]:
      try:
        c.execute("INSERT INTO users(username,password_hash,name,role,class_name) VALUES(?,?,?,?,?)",
                  (username,hashlib.sha256(pwd.encode()).hexdigest(),name,role,cls))
      except sqlite3.IntegrityError: pass
    c.commit();c.close()

init()

ROLE_LABEL={"student":"Học sinh","teacher":"Giáo viên","admin":"Admin"}

def current_user(auth: str = ""):
    token=auth.replace("Bearer ","")
    uid=TOKENS.get(token)
    if not uid: raise HTTPException(401,"Unauthorized")
    c=db();u=c.execute("SELECT * FROM users WHERE id=? AND active=1",(uid,)).fetchone();c.close()
    if not u: raise HTTPException(401,"Unauthorized")
    return u

@APP.post("/auth/login")
def login(data: dict):
    c=db();u=c.execute("SELECT * FROM users WHERE username=? AND active=1",(data.get("username"),)).fetchone();c.close()
    if not u or hashlib.sha256(data.get("password","").encode()).hexdigest()!=u["password_hash"]:
        raise HTTPException(401,"Sai tài khoản hoặc mật khẩu")
    t=secrets.token_urlsafe(32);TOKENS[t]=u["id"]
    return {"access_token":t}

@APP.get("/auth/me")
def me(authorization: str = ""):
    u=current_user(authorization)
    return {"username":u["username"],"name":u["name"],"role":u["role"],"role_label":ROLE_LABEL[u["role"]],"class_name":u["class_name"]}

@APP.get("/posts")
def posts(search: str="", authorization: str = ""):
    current_user(authorization)
    c=db()
    q="""SELECT p.*,u.name author_name,u.role author_role,
       (SELECT COUNT(*) FROM likes l WHERE l.post_id=p.id) likes
       FROM posts p JOIN users u ON u.id=p.user_id
       WHERE p.book_title LIKE ? OR p.content LIKE ? OR p.tag LIKE ?
       ORDER BY p.id DESC"""
    x=f"%{search}%"
    rows=c.execute(q,(x,x,x)).fetchall();c.close()
    return [dict(r,author_role=ROLE_LABEL[r["author_role"]]) for r in rows]

@APP.post("/posts")
async def create_post(
    authorization: str = "",
    book_title: str = Form(...),
    tag: str = Form(...),
    content: str = Form(...),
    rating: int = Form(...),
    url: str = Form(""),
    image: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
):
    u=current_user(authorization)
    if not 1<=rating<=5: raise HTTPException(400,"Rating 1-5")
    c=db(); image_url="";file_url=""
    for up,kind in [(image,"image"),(file,"file")]:
        if up and up.filename:
            safe=Path(up.filename).name.replace(" ","_")
            name=f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{safe}"
            dest=UPLOADS/name
            with dest.open("wb") as f: shutil.copyfileobj(up.file,f)
            if kind=="image": image_url=f"/uploads/{name}"
            else:file_url=f"/uploads/{name}"
    c.execute("""INSERT INTO posts(user_id,book_title,tag,content,rating,image_url,file_url,url,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?)""",(u["id"],book_title,tag,content,rating,image_url,file_url,url,datetime.utcnow().isoformat()))
    c.commit();c.close();return {"ok":True}

@APP.post("/posts/{post_id}/like")
def like(post_id:int,authorization:str=""):
    u=current_user(authorization);c=db()
    try:c.execute("INSERT INTO likes(post_id,user_id) VALUES(?,?)",(post_id,u["id"]))
    except sqlite3.IntegrityError:c.execute("DELETE FROM likes WHERE post_id=? AND user_id=?",(post_id,u["id"]))
    c.commit();c.close();return {"ok":True}

class Comment(BaseModel): content:str

@APP.post("/posts/{post_id}/comments")
def comment(post_id:int,data:Comment,authorization:str=""):
    u=current_user(authorization);c=db()
    c.execute("INSERT INTO comments(post_id,user_id,content,created_at) VALUES(?,?,?,?)",
              (post_id,u["id"],data.content,datetime.utcnow().isoformat()))
    c.commit();c.close();return {"ok":True}

@APP.get("/health")
def health(): return {"status":"ok","service":"van-hoa-doc"}
