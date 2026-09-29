# 数控刀补复核台

操作员提交刀具编号与刀补微米值；后台 worker 用 PostgreSQL 行锁（`select_for_update(skip_locked=True)`）认领待复核记录，按「上限台」现行合格上限给出「合格」或「超差」：刀补绝对值不大于上限为合格，超过为超差。初始上限 12 微米，可由操作员在「上限台」专页调整，每次改档留痕。

## 上限如何吃

- **待复核**的单不记上限，随时吃上限台的最新现行数字；交单后、认领前改档，判定跟新值走。
- worker 行锁认领、单子转入**复核中**的瞬间，把当时上限快照到该单（`limit_um`）；此后再改档，复核中/已完成的单继续用认领时记下的上限，结论不变。
- 改档与认领都锁上限单行，两者并发时被数据库串行化，不会读到不确定的中间值。


## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Django 5 + django-ninja（ASGI / uvicorn） |
| 前端 | SolidJS + Vite，nginx 反代 `/api` |
| 数据库 | PostgreSQL 16 |
| 鉴权 | JWT（python-jose），令牌存浏览器 localStorage |

## 端口

| 服务 | 地址 |
|------|------|
| 页面 | http://localhost:3196 |
| 接口 | http://localhost:8196 |
| PostgreSQL | localhost:54396（库名 `cncoffset`） |

## 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| machinist | machine123456 | 可提交刀补、可在「上限台」改档 |
| auditor | audit123456 | 只读：能看列表、现行上限与改档痕迹，不能改上限也不能交刀补 |

## 启动

```bash
cd projects/17-cnc-tool-offset-desk
docker compose up --build
```

健康检查：`GET http://localhost:8196/api/health` → `{"status":"ok"}`

## 验收

1. machinist 登录后，种子数据应显示刀具 T01 合格（刀补 5 µm）、T09 超差（刀补 20 µm，上限 12 µm）。
2. 提交一条新刀补后，状态先为「待复核」，数秒内 worker 处理为「已完成」并给出结论。
3. auditor 登录后只能看列表，没有提交表单；进入「上限台」只能查看现行上限与改档痕迹，没有改档表单。
4. machinist 在「上限台」把上限改成 **8** 后交一条刀补 **10 µm**，worker 处理后应判**超差**；再把上限改回 **12**，另交一条 **10 µm**，应判**合格**；两次改档都留在痕迹表里。
5. 上限为 8 时交一条 10 µm（待复核），在 worker 认领前把上限改回 12，该单最终应合格（吃最新上限）；已进入复核中的单不受之后改档影响（按认领时快照）。

## 目录

```text
backend/          Django 工程（config/、desk/、worker.py）
frontend/         SolidJS 单页
docker-compose.yml
PRD.md
```
