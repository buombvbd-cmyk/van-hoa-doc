from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3, os, secrets
from werkzeug.utils import secure_filename

app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY','change-this-secret-key-before-production')
ROOT=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(ROOT,"data.db")
UPLOAD=os.path.join(ROOT,"static","uploads")
os.makedirs(UPLOAD,exist_ok=True)

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,code TEXT UNIQUE,password TEXT,role TEXT,class_name TEXT);
    CREATE TABLE IF NOT EXISTS teacher_classes(teacher_id INTEGER,class_name TEXT,UNIQUE(teacher_id,class_name));
    CREATE TABLE IF NOT EXISTS classes(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,teacher_id INTEGER);
    CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,author TEXT,category TEXT,description TEXT,cover TEXT);
    CREATE TABLE IF NOT EXISTS videos(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,description TEXT,url TEXT,file TEXT);
    CREATE TABLE IF NOT EXISTS documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        filename TEXT,
        content_type TEXT,
        tag TEXT,
        grade TEXT,
        description TEXT,
        uploaded_by INTEGER,
        created TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,description TEXT,due TEXT,points INTEGER DEFAULT 10,class_name TEXT);
    CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT,message TEXT,read INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS badges(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,description TEXT,icon TEXT,points INTEGER);
    CREATE TABLE IF NOT EXISTS user_badges(user_id INTEGER,badge_id INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT,assignment_id INTEGER,user_id INTEGER,answer TEXT,score INTEGER DEFAULT 0,status TEXT DEFAULT 'Đã nộp');
    CREATE TABLE IF NOT EXISTS journals(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,book TEXT,content TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0:
        c.executemany("INSERT INTO users(name,code,password,role) VALUES(?,?,?,?)",[
            ("Quản trị viên","admin","admin123","admin"),
            ("Giáo viên Demo","gv001","123456","teacher"),
            ("Nguyễn Minh Anh","hs001","123456","student")])
        c.executemany("INSERT INTO books(title,author,category,description) VALUES(?,?,?,?)",[
            ("Dế Mèn Phiêu Lưu Ký","Tô Hoài","Văn học thiếu nhi","Hành trình trưởng thành của Dế Mèn qua nhiều cuộc phiêu lưu."),
            ("Cho Tôi Xin Một Vé Đi Tuổi Thơ","Nguyễn Nhật Ánh","Văn học","Những ký ức trong trẻo về tuổi thơ."),
            ("Hạt Giống Tâm Hồn","Nhiều tác giả","Kỹ năng sống","Những câu chuyện nhỏ mang thông điệp tích cực.")])
        c.executemany("INSERT INTO assignments(title,description,due,points) VALUES(?,?,?,?)",[
            ("Đọc hiểu: Nhân vật em yêu thích","Đọc một truyện và viết 5–7 câu cảm nhận.","2026-09-05",20),
            ("Câu hỏi sau khi đọc","Trả lời câu hỏi về cuốn sách em đã đọc.","2026-09-10",10)])
        c.executemany("INSERT INTO videos(title,description,url,file) VALUES(?,?,?,?)",[
            ("5 phút cùng một cuốn sách","Cách giới thiệu một cuốn sách hấp dẫn.","https://www.youtube.com/embed/dQw4w9WgXcQ","")])
    c.commit()
    c.close()

init()

def current():
    return session.get("user")

@app.context_processor
def inject():
    return {"me":current()}

@app.route("/")
def home():
    c=db()
    data={
        "books":c.execute("SELECT * FROM books ORDER BY id DESC").fetchall(),
        "assignments":c.execute("SELECT * FROM assignments ORDER BY id DESC").fetchall(),
        "videos":c.execute("SELECT * FROM videos ORDER BY id DESC").fetchall()
    }
    c.close()
    return render_template("home.html",**data)

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        code=request.form["code"].strip()
        pw=request.form["password"]
        c=db()
        u=c.execute("SELECT * FROM users WHERE code=? AND password=?",(code,pw)).fetchone()
        c.close()
        if u:
            session["user"]=dict(u)
            return redirect(url_for("home"))
        flash("Sai mã tài khoản hoặc mật khẩu.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def teacher_required():
    return current() and current()["role"] in ("teacher","admin")

@app.route("/books")
def books():
    c=db()
    rows=c.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    c.close()
    return render_template("books.html",books=rows)

@app.route("/assignments")
def assignments():
    c=db()
    rows=c.execute("SELECT * FROM assignments ORDER BY id DESC").fetchall()
    c.close()
    return render_template("assignments.html",assignments=rows)

@app.route("/assignment/<int:aid>",methods=["GET","POST"])
def assignment(aid):
    if not current():
        return redirect(url_for("login"))
    c=db()
    a=c.execute("SELECT * FROM assignments WHERE id=?",(aid,)).fetchone()
    if request.method=="POST":
        c.execute("INSERT INTO submissions(assignment_id,user_id,answer) VALUES(?,?,?)",
                  (aid,current()["id"],request.form["answer"]))
        c.commit()
        flash("Đã nộp bài.")
        c.close()
        return redirect(url_for("assignments"))
    c.close()
    return render_template("assignment.html",a=a)

@app.route("/videos")
def videos():
    c=db()
    rows=c.execute("SELECT * FROM videos ORDER BY id DESC").fetchall()
    c.close()
    return render_template("videos.html",videos=rows)

@app.route("/documents")
def documents():
    c=db()
    content_type=request.args.get("type","").strip()
    tag=request.args.get("tag","").strip()
    grade=request.args.get("grade","").strip()

    query="SELECT * FROM documents WHERE 1=1"
    params=[]

    if content_type:
        query+=" AND content_type=?"
        params.append(content_type)

    if tag:
        query+=" AND tag=?"
        params.append(tag)

    if grade:
        query+=" AND grade=?"
        params.append(grade)

    query+=" ORDER BY id DESC"

    rows=c.execute(query,params).fetchall()
    c.close()

    return render_template(
        "documents.html",
        documents=rows,
        selected_type=content_type,
        selected_tag=tag,
        selected_grade=grade
    )

@app.route("/journal",methods=["GET","POST"])
def journal():
    if not current():
        return redirect(url_for("login"))
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO journals(user_id,book,content) VALUES(?,?,?)",
                  (current()["id"],request.form["book"],request.form["content"]))
        c.commit()
        flash("Đã lưu nhật ký đọc sách.")
    rows=c.execute("SELECT * FROM journals WHERE user_id=? ORDER BY id DESC",
                   (current()["id"],)).fetchall()
    c.close()
    return render_template("journal.html",journals=rows)

@app.route("/admin")
def admin():
    if not teacher_required():
        return redirect(url_for("login"))

    c=db()

    stats={
        k:c.execute(q).fetchone()[0]
        for k,q in {
            "users":"SELECT COUNT(*) FROM users",
            "books":"SELECT COUNT(*) FROM books",
            "assignments":"SELECT COUNT(*) FROM assignments",
            "videos":"SELECT COUNT(*) FROM videos",
            "submissions":"SELECT COUNT(*) FROM submissions"
        }.items()
    }

    subs=c.execute("""
        SELECT s.*, u.name, a.title
        FROM submissions s
        JOIN users u ON u.id=s.user_id
        JOIN assignments a ON a.id=s.assignment_id
        ORDER BY s.id DESC
    """).fetchall()

    users=c.execute("""
        SELECT id,name,code,role,class_name
        FROM users
        ORDER BY
            CASE role
                WHEN 'admin' THEN 1
                WHEN 'teacher' THEN 2
                WHEN 'student' THEN 3
                ELSE 4
            END,
            name
    """).fetchall()

    documents=c.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()

    c.close()

    return render_template(
        "admin.html",
        stats=stats,
        subs=subs,
        users=users,
        files=os.listdir(UPLOAD),
        documents=documents
    )

@app.route("/admin/book",methods=["POST"])
def add_book():
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    c.execute("INSERT INTO books(title,author,category,description) VALUES(?,?,?,?)",
              (request.form["title"],request.form["author"],request.form["category"],request.form["description"]))
    c.commit()
    c.close()
    return redirect(url_for("admin"))

@app.route("/admin/assignment",methods=["POST"])
def add_assignment():
    if not teacher_required():
        return redirect(url_for("login"))
    cls=request.form.get("class_name","")
    if current()["role"]=="teacher" and cls and cls not in teacher_classes():
        flash("Bạn không được giao bài cho lớp này.")
        return redirect(url_for("admin"))
    c=db()
    c.execute("INSERT INTO assignments(title,description,due,points,class_name) VALUES(?,?,?,?,?)",
              (request.form["title"],request.form["description"],request.form["due"],request.form["points"],cls))
    c.commit()
    if cls:
        students=c.execute("SELECT id FROM users WHERE role='student' AND class_name=?",(cls,)).fetchall()
        for u in students:
            c.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",
                      (u["id"],"Có bài tập mới",f"Bạn có bài tập mới: {request.form['title']}"))
    c.commit()
    c.close()
    return redirect(url_for("admin"))

@app.route("/admin/video",methods=["POST"])
def add_video():
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    c.execute("INSERT INTO videos(title,description,url,file) VALUES(?,?,?,?)",
              (request.form["title"],request.form["description"],request.form["url"],""))
    c.commit()
    c.close()
    return redirect(url_for("admin"))

@app.route("/admin/score/<int:sid>",methods=["POST"])
def score(sid):
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    c.execute("UPDATE submissions SET score=?,status=? WHERE id=?",
              (request.form["score"],"Đã chấm",sid))
    c.commit()
    c.close()
    return redirect(url_for("admin"))

@app.route("/leaderboard")
def leaderboard():
    c=db()
    rows=c.execute("""
        SELECT u.name, COALESCE(SUM(s.score),0) score
        FROM users u
        LEFT JOIN submissions s ON u.id=s.user_id
        WHERE u.role='student'
        GROUP BY u.id
        ORDER BY score DESC
    """).fetchall()
    c.close()
    return render_template("leaderboard.html",rows=rows)

@app.route("/students")
def students():
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    rows=c.execute("SELECT * FROM users WHERE role='student' ORDER BY class_name,name").fetchall()
    classes=c.execute("SELECT * FROM classes ORDER BY name").fetchall()
    c.close()
    return render_template("students.html",students=rows,classes=classes)

@app.route("/admin/student",methods=["POST"])
def add_student():
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    try:
        c.execute(
            "INSERT INTO users(name,code,password,role,class_name) VALUES(?,?,?,?,?)",
            (request.form["name"],request.form["code"],request.form["password"],"student",request.form["class_name"])
        )
        c.commit()
    except sqlite3.IntegrityError:
        flash("Mã học sinh đã tồn tại.")
    c.close()
    return redirect(url_for("students"))

@app.route("/admin/user",methods=["POST"])
def add_user():
    if not current() or current()["role"]!="admin":
        return redirect(url_for("login"))

    name=request.form.get("name","").strip()
    code=request.form.get("code","").strip()
    password=request.form.get("password","").strip()
    role=request.form.get("role","student").strip()
    class_name=request.form.get("class_name","").strip()

    if not name or not code or not password:
        flash("Vui lòng nhập đầy đủ thông tin.")
        return redirect(url_for("admin"))

    if role not in ("student","teacher"):
        flash("Loại tài khoản không hợp lệ.")
        return redirect(url_for("admin"))

    c=db()
    try:
        c.execute("INSERT INTO users(name,code,password,role,class_name) VALUES(?,?,?,?,?)",
                  (name,code,password,role,class_name))
        c.commit()
        flash(f"Đã tạo tài khoản {code}.")
    except sqlite3.IntegrityError:
        flash("Mã tài khoản đã tồn tại.")
    c.close()
    return redirect(url_for("admin"))

@app.route("/admin/user/<int:user_id>/reset-password",methods=["POST"])
def reset_user_password(user_id):
    if not current() or current()["role"]!="admin":
        return redirect(url_for("login"))

    if user_id==current()["id"]:
        flash("Không thể cấp lại mật khẩu cho chính mình.")
        return redirect(url_for("admin"))

    c=db()
    user=c.execute("SELECT name,code FROM users WHERE id=?",(user_id,)).fetchone()

    if not user:
        flash("Không tìm thấy tài khoản.")
        c.close()
        return redirect(url_for("admin"))

    new_password=secrets.token_urlsafe(6)
    c.execute("UPDATE users SET password=? WHERE id=?",(new_password,user_id))
    c.commit()
    c.close()

    flash(f"Mật khẩu mới của {user['name']} ({user['code']}) là: {new_password}")
    return redirect(url_for("admin"))

@app.route("/admin/user/<int:user_id>/delete",methods=["POST"])
def delete_user(user_id):
    if not current() or current()["role"]!="admin":
        return redirect(url_for("login"))

    if user_id==current()["id"]:
        flash("Không thể tự xóa tài khoản đang đăng nhập.")
        return redirect(url_for("admin"))

    c=db()
    user=c.execute("SELECT name,code FROM users WHERE id=?",(user_id,)).fetchone()

    if not user:
        flash("Không tìm thấy tài khoản.")
        c.close()
        return redirect(url_for("admin"))

    c.execute("DELETE FROM notifications WHERE user_id=?",(user_id,))
    c.execute("DELETE FROM user_badges WHERE user_id=?",(user_id,))
    c.execute("DELETE FROM journals WHERE user_id=?",(user_id,))
    c.execute("DELETE FROM submissions WHERE user_id=?",(user_id,))
    c.execute("DELETE FROM teacher_classes WHERE teacher_id=?",(user_id,))
    c.execute("DELETE FROM users WHERE id=?",(user_id,))
    c.commit()
    c.close()

    flash(f"Đã xóa tài khoản {user['name']} ({user['code']}).")
    return redirect(url_for("admin"))

@app.route("/admin/class",methods=["POST"])
def add_class():
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    try:
        c.execute("INSERT INTO classes(name,teacher_id) VALUES(?,?)",
                  (request.form["name"],current()["id"]))
        c.commit()
    except sqlite3.IntegrityError:
        flash("Lớp đã tồn tại.")
    c.close()
    return redirect(url_for("students"))

@app.route("/profile")
def profile():
    if not current():
        return redirect(url_for("login"))
    c=db()
    u=c.execute("SELECT * FROM users WHERE id=?",(current()["id"],)).fetchone()
    c.close()
    return render_template("profile.html",u=u)

@app.route("/change-password",methods=["POST"])
def change_password():
    if not current():
        return redirect(url_for("login"))
    c=db()
    c.execute("UPDATE users SET password=? WHERE id=?",(request.form["password"],current()["id"]))
    c.commit()
    c.close()
    flash("Đã đổi mật khẩu.")
    return redirect(url_for("profile"))

@app.route("/notifications")
def notifications():
    if not current():
        return redirect(url_for("login"))
    c=db()
    rows=c.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC",
                   (current()["id"],)).fetchall()
    c.execute("UPDATE notifications SET read=1 WHERE user_id=?",(current()["id"],))
    c.commit()
    c.close()
    return render_template("notifications.html",notifications=rows)

@app.route("/admin/notify",methods=["POST"])
def notify():
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    users=c.execute("SELECT id FROM users WHERE role='student'").fetchall()
    for u in users:
        c.execute("INSERT INTO notifications(user_id,title,message) VALUES(?,?,?)",
                  (u["id"],request.form["title"],request.form["message"]))
    c.commit()
    c.close()
    flash("Đã gửi thông báo.")
    return redirect(url_for("admin"))

@app.route("/badges")
def badges():
    if not current():
        return redirect(url_for("login"))
    c=db()
    rows=c.execute("""
        SELECT b.*, CASE WHEN ub.user_id IS NULL THEN 0 ELSE 1 END earned
        FROM badges b
        LEFT JOIN user_badges ub
          ON b.id=ub.badge_id AND ub.user_id=?
    """,(current()["id"],)).fetchall()
    c.close()
    return render_template("badges.html",badges=rows)

@app.route("/admin/badge",methods=["POST"])
def add_badge():
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    c.execute("INSERT INTO badges(name,description,icon,points) VALUES(?,?,?,?)",
              (request.form["name"],request.form["description"],request.form["icon"],request.form["points"]))
    c.commit()
    c.close()
    return redirect(url_for("admin"))

@app.route("/upload",methods=["POST"])
def upload():
    if not teacher_required():
        return redirect(url_for("login"))

    f=request.files.get("file")

    if not f or not f.filename:
        flash("Chưa chọn file.")
        return redirect(url_for("admin"))

    allowed={"pdf","doc","docx","jpg","jpeg","png","mp4","webm"}
    ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""

    if ext not in allowed:
        flash("Định dạng chưa được hỗ trợ.")
        return redirect(url_for("admin"))

    title=request.form.get("title","").strip()
    content_type=request.form.get("content_type","document").strip()
    tag=request.form.get("tag","").strip()
    grade=request.form.get("grade","").strip()
    description=request.form.get("description","").strip()

    if not title:
        title=os.path.splitext(f.filename)[0]

    filename=secure_filename(f.filename)
    base,extension=os.path.splitext(filename)
    final_name=filename
    counter=1

    while os.path.exists(os.path.join(UPLOAD,final_name)):
        final_name=f"{base}_{counter}{extension}"
        counter+=1

    f.save(os.path.join(UPLOAD,final_name))

    c=db()
    c.execute("""
        INSERT INTO documents
        (title,filename,content_type,tag,grade,description,uploaded_by)
        VALUES(?,?,?,?,?,?,?)
    """,(title,final_name,content_type,tag,grade,description,current()["id"]))
    c.commit()
    c.close()

    flash("Đã tải tài liệu và phân loại thành công.")
    return redirect(url_for("admin"))

@app.route("/files/<path:name>")
def files(name):
    return send_from_directory(UPLOAD,name)

def teacher_classes():
    if not current():
        return []

    if current()["role"]=="admin":
        c=db()
        rows=c.execute("SELECT name FROM classes ORDER BY name").fetchall()
        c.close()
        return [r["name"] for r in rows]

    c=db()
    rows=c.execute("SELECT class_name FROM teacher_classes WHERE teacher_id=?",
                   (current()["id"],)).fetchall()
    c.close()
    return [r["class_name"] for r in rows]

@app.route("/dashboard")
def dashboard():
    if not current():
        return redirect(url_for("login"))

    c=db()

    if current()["role"]=="student":
        stats={
            "books":c.execute("SELECT COUNT(*) FROM books").fetchone()[0],
            "assignments":c.execute("SELECT COUNT(*) FROM submissions WHERE user_id=?",
                                    (current()["id"],)).fetchone()[0],
            "journals":c.execute("SELECT COUNT(*) FROM journals WHERE user_id=?",
                                 (current()["id"],)).fetchone()[0],
            "score":c.execute("SELECT COALESCE(SUM(score),0) FROM submissions WHERE user_id=?",
                              (current()["id"],)).fetchone()[0]
        }
    else:
        stats={
            "students":c.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
            "classes":c.execute("SELECT COUNT(*) FROM classes").fetchone()[0],
            "submissions":c.execute("SELECT COUNT(*) FROM submissions").fetchone()[0],
            "books":c.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        }

    c.close()
    return render_template("dashboard.html",stats=stats)

@app.route("/admin/teacher-class",methods=["POST"])
def teacher_class():
    if current()["role"]!="admin":
        return redirect(url_for("login"))
    c=db()
    try:
        c.execute("INSERT INTO teacher_classes(teacher_id,class_name) VALUES(?,?)",
                  (request.form["teacher_id"],request.form["class_name"]))
        c.commit()
    except sqlite3.IntegrityError:
        pass
    c.close()
    return redirect(url_for("admin"))

@app.route("/reports")
def reports():
    if not teacher_required():
        return redirect(url_for("login"))
    c=db()
    classes=c.execute("""
        SELECT class_name, COUNT(*) students
        FROM users
        WHERE role='student'
        GROUP BY class_name
        ORDER BY class_name
    """).fetchall()
    activity=c.execute("""
        SELECT a.class_name, COUNT(s.id) submissions, COALESCE(SUM(s.score),0) score
        FROM assignments a
        LEFT JOIN submissions s ON a.id=s.assignment_id
        GROUP BY a.class_name
        ORDER BY a.class_name
    """).fetchall()
    c.close()
    return render_template("reports.html",classes=classes,activity=activity)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
