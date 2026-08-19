VĂN HÓA ĐỌC – V4
Mục tiêu: nền tảng quản lý Văn hóa đọc cho trường học.

V4 bổ sung:
- Dashboard học sinh/giáo viên/admin
- Quản lý lớp và học sinh
- Giao bài theo lớp
- Tự động gửi thông báo khi giao bài
- Báo cáo theo lớp
- Kho sách/video
- Nộp bài và chấm điểm
- Nhật ký đọc sách
- Huy hiệu và xếp hạng
- Upload tài liệu/video
- Hồ sơ và đổi mật khẩu

Chạy local:
1) pip install -r requirements.txt
2) python app.py
3) mở http://127.0.0.1:5000

Demo:
hs001 / 123456
gv001 / 123456
admin / admin123

ĐỂ ĐƯA LÊN INTERNET:
- Dùng PostgreSQL thay SQLite
- Hash mật khẩu (bcrypt/argon2)
- CSRF
- giới hạn kích thước/MIME upload
- object storage cho video
- HTTPS
- backup
- biến môi trường SECRET_KEY
- cấu hình domain vanhoadoc.truongxanh.edu.vn tại DNS của trường

Bản này là production-oriented prototype; chưa thể tự đăng ký domain/hosting hoặc thay đổi DNS của trường.
