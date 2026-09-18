-- ══════════════════════════════════════════════════════════
-- Text2SQL Demo Schema — 6 tables, covers all chart types
-- ══════════════════════════════════════════════════════════

-- 1) 学生表 — 基础维度表
CREATE TABLE demo.student(
  id TEXT COMMENT '学号',
  name TEXT COMMENT '姓名',
  age INTEGER COMMENT '年龄',
  gender TEXT COMMENT '性别(男/女)',
  major TEXT COMMENT '专业',
  enrollment_year INTEGER COMMENT '入学年份',
  city TEXT COMMENT '生源城市'
)
COMMENT '学生信息表';

-- 2) 课程表
CREATE TABLE demo.course(
  course_id TEXT COMMENT '课程编号',
  course_name TEXT COMMENT '课程名称',
  teacher TEXT COMMENT '授课老师',
  credit INTEGER COMMENT '学分',
  department TEXT COMMENT '开课院系'
)
COMMENT '课程信息表';

-- 3) 成绩表 — 关联学生+课程，测试 JOIN
CREATE TABLE demo.score(
  id TEXT COMMENT '学号',
  course_id TEXT COMMENT '课程编号',
  score REAL COMMENT '成绩',
  semester TEXT COMMENT '学期(如 2025-春)'
)
COMMENT '学生成绩表';

-- 4) 销售订单表 — 有日期，测试折线图/柱状图/饼图
CREATE TABLE demo.sales_order(
  order_id TEXT COMMENT '订单编号',
  product_name TEXT COMMENT '商品名称',
  category TEXT COMMENT '商品类目(电子/服装/食品/图书/家居)',
  amount REAL COMMENT '订单金额',
  quantity INTEGER COMMENT '购买数量',
  order_date TEXT COMMENT '下单日期(yyyy-MM-dd)',
  city TEXT COMMENT '城市',
  customer_id TEXT COMMENT '客户编号'
)
COMMENT '销售订单明细表';

-- 5) 员工表 — 测试数据分布/profiling
CREATE TABLE demo.employee(
  emp_id TEXT COMMENT '员工编号',
  emp_name TEXT COMMENT '员工姓名',
  department TEXT COMMENT '部门',
  position TEXT COMMENT '职位',
  salary REAL COMMENT '月薪(元)',
  hire_date TEXT COMMENT '入职日期',
  city TEXT COMMENT '工作城市'
)
COMMENT '员工信息表';

-- 6) 网站访问日志 — 时间序列，测试趋势图
CREATE TABLE demo.page_view(
  view_id TEXT COMMENT '访问ID',
  user_id TEXT COMMENT '用户ID',
  page_url TEXT COMMENT '页面路径',
  device TEXT COMMENT '设备类型(PC/Mobile/Tablet)',
  visit_date TEXT COMMENT '访问日期(yyyy-MM-dd)',
  duration_sec INTEGER COMMENT '停留时长(秒)',
  referrer TEXT COMMENT '来源(search/direct/social/ad)'
)
COMMENT '网站访问日志表';
