-- Text2SQL schema whitelist for cladata database.
-- Only tables listed here can be queried by the Text2SQL agent.

CREATE TABLE cladata.student(
  id string COMMENT '学号',
  name string COMMENT '姓名',
  age int COMMENT '年龄',
  gender string COMMENT '性别',
  major string COMMENT '专业'
)
COMMENT '学生信息表';

CREATE TABLE cladata.course(
  course_id string COMMENT '课程编号',
  course_name string COMMENT '课程名称',
  teacher string COMMENT '授课老师',
  credit int COMMENT '学分'
)
COMMENT '课程信息表';

CREATE TABLE cladata.score(
  id string COMMENT '学号',
  course_id string COMMENT '课程编号',
  score double COMMENT '成绩',
  semester string COMMENT '学期'
)
COMMENT '学生成绩表';

CREATE TABLE cladata.sales_di(
  order_id string COMMENT '订单编号',
  product_name string COMMENT '商品名称',
  category string COMMENT '商品类目',
  amount double COMMENT '订单金额',
  quantity int COMMENT '购买数量',
  city string COMMENT '城市',
  customer_id string COMMENT '客户编号'
)
COMMENT '销售订单明细表-增量'
PARTITIONED BY (pt string COMMENT '业务日期yyyyMMdd');
