Chứng chỉ tự ký **chỉ để demo** (khoá riêng nằm trong repo nên không an toàn cho mạng công cộng). Trình duyệt điện thoại chỉ cho dùng micro trên https,
nên trang `https://<ip-pi>:8443/phone` cần chứng chỉ này; lần đầu bấm "Nâng cao → Tiếp tục" để chấp nhận cảnh báo.
Tạo lại: `openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=vieedge.local" -addext "subjectAltName=DNS:vieedge.local,DNS:raspberrypi5,IP:127.0.0.1" -keyout vieedge.key -out vieedge.crt`
