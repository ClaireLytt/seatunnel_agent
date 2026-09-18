"""Seed the SQLite demo database with realistic test data.

Run:  python scripts/seed_demo_db.py
Creates:  config/demo.db
"""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("config/demo.db")
random.seed(42)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # ── 1. student ──
    c.execute("""
        CREATE TABLE student (
            id TEXT PRIMARY KEY,
            name TEXT, age INTEGER, gender TEXT,
            major TEXT, enrollment_year INTEGER, city TEXT
        )
    """)
    majors = ["计算机科学", "数据科学", "软件工程", "人工智能", "信息安全", "电子商务"]
    cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京"]
    first_names = "伟芳娜秀英敏静丽强磊洋勇艳杰娟涛明超秀兰霞平刚桂英"
    last_names = "王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗"
    students = []
    for i in range(1, 201):
        sid = f"S{i:04d}"
        name = random.choice(last_names) + random.choice(first_names) + random.choice(first_names)
        age = random.randint(18, 25)
        gender = random.choice(["男", "女"])
        major = random.choice(majors)
        year = random.choice([2022, 2023, 2024, 2025])
        city = random.choice(cities)
        students.append((sid, name, age, gender, major, year, city))
    c.executemany("INSERT INTO student VALUES (?,?,?,?,?,?,?)", students)

    # ── 2. course ──
    c.execute("""
        CREATE TABLE course (
            course_id TEXT PRIMARY KEY,
            course_name TEXT, teacher TEXT,
            credit INTEGER, department TEXT
        )
    """)
    courses_data = [
        ("C001", "高等数学", "张教授", 4, "数学学院"),
        ("C002", "线性代数", "李教授", 3, "数学学院"),
        ("C003", "数据结构", "王教授", 4, "计算机学院"),
        ("C004", "数据库原理", "刘教授", 3, "计算机学院"),
        ("C005", "操作系统", "陈教授", 4, "计算机学院"),
        ("C006", "计算机网络", "杨教授", 3, "计算机学院"),
        ("C007", "人工智能导论", "赵教授", 3, "人工智能学院"),
        ("C008", "机器学习", "黄教授", 4, "人工智能学院"),
        ("C009", "大数据技术", "周教授", 3, "计算机学院"),
        ("C010", "软件工程", "吴教授", 3, "软件学院"),
        ("C011", "概率与统计", "徐教授", 3, "数学学院"),
        ("C012", "Python编程", "孙教授", 2, "计算机学院"),
    ]
    c.executemany("INSERT INTO course VALUES (?,?,?,?,?)", courses_data)

    # ── 3. score — each student takes 4-8 random courses ──
    c.execute("""
        CREATE TABLE score (
            id TEXT, course_id TEXT, score REAL, semester TEXT,
            PRIMARY KEY (id, course_id, semester)
        )
    """)
    semesters = ["2024-春", "2024-秋", "2025-春"]
    scores = []
    course_ids = [c[0] for c in courses_data]
    for sid, *_ in students:
        n_courses = random.randint(4, 8)
        chosen = random.sample(course_ids, n_courses)
        for cid in chosen:
            sem = random.choice(semesters)
            sc = round(random.gauss(75, 12), 1)
            sc = max(0, min(100, sc))
            scores.append((sid, cid, sc, sem))
    c.executemany("INSERT OR IGNORE INTO score VALUES (?,?,?,?)", scores)

    # ── 4. sales_order — 2000 orders over 12 months ──
    c.execute("""
        CREATE TABLE sales_order (
            order_id TEXT PRIMARY KEY,
            product_name TEXT, category TEXT,
            amount REAL, quantity INTEGER,
            order_date TEXT, city TEXT, customer_id TEXT
        )
    """)
    categories = {
        "电子": ["iPhone 15", "MacBook Pro", "AirPods", "iPad Air", "华为Mate60", "小米14"],
        "服装": ["运动T恤", "牛仔裤", "羽绒服", "连衣裙", "运动鞋", "衬衫"],
        "食品": ["坚果礼盒", "牛奶箱装", "进口水果", "零食大礼包", "咖啡豆", "茶叶"],
        "图书": ["算法导论", "深度学习", "经济学原理", "Python实战", "三体", "设计模式"],
        "家居": ["台灯", "抱枕", "收纳箱", "空气净化器", "智能音箱", "咖啡机"],
    }
    cat_prices = {"电子": (500, 12000), "服装": (50, 800), "食品": (30, 300),
                  "图书": (20, 150), "家居": (50, 3000)}
    order_cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆"]
    base_date = datetime(2025, 10, 1)
    orders = []
    for i in range(1, 2001):
        cat = random.choice(list(categories))
        prod = random.choice(categories[cat])
        lo, hi = cat_prices[cat]
        amount = round(random.uniform(lo, hi), 2)
        qty = random.randint(1, 5)
        days_ago = random.randint(0, 364)
        dt = base_date - timedelta(days=days_ago)
        city = random.choice(order_cities)
        cust = f"CU{random.randint(1, 300):04d}"
        orders.append((f"ORD{i:05d}", prod, cat, amount * qty, qty, dt.strftime("%Y-%m-%d"), city, cust))
    c.executemany("INSERT INTO sales_order VALUES (?,?,?,?,?,?,?,?)", orders)

    # ── 5. employee — 150 employees ──
    c.execute("""
        CREATE TABLE employee (
            emp_id TEXT PRIMARY KEY,
            emp_name TEXT, department TEXT, position TEXT,
            salary REAL, hire_date TEXT, city TEXT
        )
    """)
    departments = ["技术部", "产品部", "市场部", "运营部", "财务部", "人事部"]
    positions = {"技术部": ["工程师", "高级工程师", "架构师", "技术总监"],
                 "产品部": ["产品经理", "高级产品经理", "产品总监"],
                 "市场部": ["市场专员", "市场经理", "市场总监"],
                 "运营部": ["运营专员", "运营经理", "运营总监"],
                 "财务部": ["会计", "财务经理", "财务总监"],
                 "人事部": ["HR专员", "HR经理", "HR总监"]}
    salary_ranges = {"工程师": (10000, 20000), "高级工程师": (20000, 35000),
                     "架构师": (35000, 55000), "技术总监": (50000, 80000),
                     "产品经理": (15000, 30000), "高级产品经理": (30000, 50000),
                     "产品总监": (45000, 70000), "市场专员": (8000, 15000),
                     "市场经理": (18000, 35000), "市场总监": (40000, 60000),
                     "运营专员": (8000, 15000), "运营经理": (18000, 30000),
                     "运营总监": (35000, 55000), "会计": (8000, 15000),
                     "财务经理": (20000, 35000), "财务总监": (40000, 60000),
                     "HR专员": (8000, 14000), "HR经理": (18000, 30000),
                     "HR总监": (35000, 50000)}
    emp_cities = ["北京", "上海", "深圳", "杭州"]
    employees = []
    for i in range(1, 151):
        dept = random.choice(departments)
        pos = random.choice(positions[dept])
        lo, hi = salary_ranges[pos]
        salary = round(random.uniform(lo, hi), 0)
        hire_days = random.randint(30, 3650)
        hire_dt = datetime(2026, 9, 1) - timedelta(days=hire_days)
        employees.append((
            f"E{i:04d}",
            random.choice(last_names) + random.choice(first_names) + random.choice(first_names),
            dept, pos, salary,
            hire_dt.strftime("%Y-%m-%d"),
            random.choice(emp_cities),
        ))
    c.executemany("INSERT INTO employee VALUES (?,?,?,?,?,?,?)", employees)

    # ── 6. page_view — 5000 visits over 90 days ──
    c.execute("""
        CREATE TABLE page_view (
            view_id TEXT PRIMARY KEY,
            user_id TEXT, page_url TEXT, device TEXT,
            visit_date TEXT, duration_sec INTEGER, referrer TEXT
        )
    """)
    pages = ["/home", "/products", "/products/detail", "/cart", "/checkout",
             "/blog", "/blog/post", "/about", "/contact", "/search"]
    devices = ["PC", "Mobile", "Tablet"]
    referrers = ["search", "direct", "social", "ad"]
    views = []
    for i in range(1, 5001):
        uid = f"U{random.randint(1, 500):04d}"
        page = random.choice(pages)
        device = random.choices(devices, weights=[40, 50, 10])[0]
        days_ago = random.randint(0, 89)
        dt = datetime(2026, 9, 15) - timedelta(days=days_ago)
        dur = max(1, int(random.gauss(120, 80)))
        ref = random.choices(referrers, weights=[35, 25, 25, 15])[0]
        views.append((f"PV{i:06d}", uid, page, device, dt.strftime("%Y-%m-%d"), dur, ref))
    c.executemany("INSERT INTO page_view VALUES (?,?,?,?,?,?,?)", views)

    conn.commit()
    conn.close()

    # Print summary
    conn2 = sqlite3.connect(str(DB_PATH))
    for tbl in ["student", "course", "score", "sales_order", "employee", "page_view"]:
        cnt = conn2.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:20s} {cnt:>6,d} rows")
    conn2.close()
    print(f"\nDemo database ready: {DB_PATH}")


if __name__ == "__main__":
    main()
