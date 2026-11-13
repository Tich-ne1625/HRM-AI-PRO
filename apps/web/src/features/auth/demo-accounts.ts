export const demoRoles = [
  { id: "HR", label: "Nhân sự", description: "Tổ chức đánh giá, chốt kết quả và tạo tư vấn AI", accounts: [
    { email: "hr.demo@example.com", name: "Nhân sự demo" },
  ] },
  { id: "MANAGER", label: "Quản lý", description: "Nhập kết quả KPI, phản hồi và tính điểm nhóm", accounts: [
    { email: "manager.demo@example.com", name: "Nguyễn Lan · Quản lý kỹ thuật" },
    { email: "sales.manager.demo@example.com", name: "Trần Huy · Quản lý kinh doanh" },
  ] },
  { id: "EMPLOYEE", label: "Nhân viên", description: "Gửi phản hồi, xem điểm và tư vấn của mình", accounts: [
    { email: "binh.demo@example.com", name: "Bình · Thực hành tự đánh giá" },
    { email: "an.demo@example.com", name: "An · Xem điểm và lịch sử" },
    { email: "dung.demo@example.com", name: "Dũng · Chờ tính điểm" },
    { email: "linh.demo@example.com", name: "Linh · Phản hồi đồng nghiệp" },
    { email: "ha.demo@example.com", name: "Hà · Xem kết quả đã chốt" },
    { email: "chi.demo@example.com", name: "Chi · Xem phản hồi đã gửi" },
  ] },
  { id: "ADMIN", label: "Quản trị", description: "Quản lý tài khoản và cấu hình chấm điểm", accounts: [
    { email: "admin.demo@example.com", name: "Quản trị viên demo" },
  ] },
] as const;
