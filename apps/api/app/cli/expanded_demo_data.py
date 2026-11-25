"""Deterministic fictional company, additive to office-demo-v1."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DepartmentSpec:
    code: str
    name: str
    target: int
    existing: int
    manager: str
    jobs: tuple[str, ...]


DEPARTMENTS = (
    DepartmentSpec("TECH", "Kỹ thuật", 12, 5, "manager", ("DEV", "QA", "DATA")),
    DepartmentSpec("SALES", "Kinh doanh", 10, 3, "sales.manager", ("SALES", "ACCOUNT")),
    DepartmentSpec("PRODUCT", "Sản phẩm", 7, 0, "product.manager", ("PRODUCT", "DATA")),
    DepartmentSpec("DESIGN", "Thiết kế", 6, 0, "design.manager", ("DESIGN",)),
    DepartmentSpec("MARKETING", "Marketing", 7, 0, "marketing.manager", ("MARKETING",)),
    DepartmentSpec("CARE", "Chăm sóc khách hàng", 6, 0, "care.manager", ("CARE", "ACCOUNT")),
    DepartmentSpec("FINANCE", "Tài chính - Kế toán", 6, 0, "finance.manager", ("FINANCE",)),
    DepartmentSpec("OPS", "Vận hành", 6, 0, "ops.manager", ("OPS",)),
)
POSITIONS = {
    "DEV": "Lập trình viên",
    "QA": "Chuyên viên kiểm thử",
    "DATA": "Chuyên viên dữ liệu",
    "SALES": "Chuyên viên kinh doanh",
    "ACCOUNT": "Chuyên viên quan hệ khách hàng",
    "PRODUCT": "Chuyên viên sản phẩm",
    "DESIGN": "Chuyên viên thiết kế",
    "MARKETING": "Chuyên viên marketing",
    "CARE": "Chuyên viên chăm sóc khách hàng",
    "FINANCE": "Chuyên viên tài chính - kế toán",
    "OPS": "Chuyên viên vận hành",
}
# Eleven specialized titles plus the original lead/staff titles: thirteen total.
NAMES = (
    "Nguyễn Minh Khánh",
    "Trần Quốc Bảo",
    "Lê Thảo Nguyên",
    "Phạm Đức Anh",
    "Hoàng Ngọc Hân",
    "Vũ Hải Nam",
    "Đặng Phương Thảo",
    "Bùi Tuấn Kiệt",
    "Đỗ Thanh Trúc",
    "Hồ Minh Quân",
    "Ngô Bảo Châu",
    "Dương Gia Huy",
    "Đinh Mỹ Duyên",
    "Lý Hoàng Phúc",
    "Mai Thu Trang",
    "Nguyễn Nhật Minh",
    "Trần Bích Ngọc",
    "Lê Đức Long",
    "Phạm Quỳnh Anh",
    "Hoàng Anh Tú",
    "Vũ Ngọc Ánh",
    "Đặng Trung Hiếu",
    "Bùi Khánh Linh",
    "Đỗ Quốc Đạt",
    "Hồ Phương Vy",
    "Ngô Thành Công",
    "Dương Hà My",
    "Đinh Anh Khoa",
    "Lý Thanh Tâm",
    "Mai Minh Triết",
    "Nguyễn Ngọc Diệp",
    "Trần Tuấn Anh",
    "Lê Hải Yến",
    "Phạm Gia Bảo",
    "Hoàng Mai Anh",
    "Vũ Đức Huy",
    "Đặng Thùy Dung",
    "Bùi Nhật Hào",
    "Đỗ Lan Hương",
    "Hồ Quang Vinh",
    "Ngô Phương Nhi",
    "Dương Quốc Hưng",
    "Đinh Ngọc Hà",
    "Lý Minh Đức",
    "Mai Hoài An",
    "Nguyễn Bảo Ngọc",
    "Trần Thiên Phúc",
    "Lê Tú Uyên",
    "Phạm Anh Duy",
    "Hoàng Khánh Vân",
    "Vũ Thành Đạt",
    "Đặng Minh Tâm",
)
# code, name, unit, lower-is-better
KPIS = (
    ("FEATURES", "Hoàn thành tính năng đúng hạn", "%", False),
    ("DEFECTS", "Lỗi lọt qua kiểm thử", "lỗi", True),
    ("REVENUE", "Doanh thu đạt kế hoạch", "%", False),
    ("CUSTOMER", "Khách hàng mới", "khách hàng", False),
    ("ROADMAP", "Mốc sản phẩm hoàn thành", "%", False),
    ("DESIGN", "Thiết kế được nghiệm thu", "%", False),
    ("LEADS", "Khách hàng tiềm năng đủ điều kiện", "khách hàng", False),
    ("CSAT", "Mức hài lòng khách hàng", "điểm / 5", False),
    ("RESPONSE", "Thời gian phản hồi yêu cầu", "giờ", True),
    ("FINANCE", "Báo cáo tài chính đúng hạn", "%", False),
    ("ERRORS", "Tỷ lệ sai sót chứng từ", "%", True),
    ("SLA", "Yêu cầu vận hành đạt SLA", "%", False),
)


def roster() -> list[tuple[str, str, str, str, str | None]]:
    """account, display name, department, position, manager account; managers first."""
    result: list[tuple[str, str, str, str, str | None]] = []
    names = iter(NAMES)
    for department in DEPARTMENTS:
        if not department.existing:
            result.append((department.manager, next(names), department.code, "LEAD", None))
        count = department.target - department.existing - (0 if department.existing else 1)
        for index in range(count):
            account = f"{department.code.lower()}{index + 1:02d}"
            result.append(
                (
                    account,
                    next(names),
                    department.code,
                    department.jobs[index % len(department.jobs)],
                    department.manager,
                )
            )
    assert len(result) == len(NAMES) == 52
    return result
