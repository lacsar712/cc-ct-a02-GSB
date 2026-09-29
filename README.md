# 数控刀补复核台

操作员提交刀具编号与刀补微米值；后台 worker 用 PostgreSQL 行锁（`select_for_update(skip_locked=True)`）认领待复核记录，按绝对值是否不大于**合格上限**给出「合格」或「超差」。

合格上限不再写死，在「上限台」专页调整：

- 只有操作员能改上限，每次改档追加一条**改档痕迹**（原值→新值、改档人、时间），不可删改。
- 还在待复核的新单不记上限，被领取那一刻吃**最新现行上限**；已进复核中（或已完成）的单继续用**领取当时记下的上限**（`claimed_limit_um` 快照），之后改档不影响它。
- 复核员只能查看上限与改档痕迹，不能改上限，也不能提交刀补。


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
| machinist | machine123456 | 可提交刀补、可改合格上限 |
| auditor | audit123456 | 只读：看列表、上限与改档痕迹，不能改、不能交 |

## 启动

```bash
cd projects/17-cnc-tool-offset-desk
docker compose up --build
```

健康检查：`GET http://localhost:8196/api/health` → `{"status":"ok"}`

## 验收

1. machinist 登录后，种子数据应显示刀具 T01 合格（刀补 5 µm）、T09 超差（刀补 20 µm）。
2. 提交一条新刀补后，状态先为「待复核」，数秒内 worker 处理为「已完成」并给出结论。
3. auditor 登录后只能看列表，没有提交表单；进入「上限台」只能看现行上限与改档痕迹，没有改上限表单。
4. 操作员在「上限台」把上限改成 **8** 后提交刀补 **10 µm**，worker 判**超差**（`|-?10| > 8`）；把上限改回 **12** 后再交 **10 µm**，判**合格**（`|10| ≤ 12`）。
5. 单进「复核中」后再改上限，结论仍按领取当时记下的上限判；改档痕迹如实记录每次 12→8、8→12 的变化。
6. auditor 直接调 `POST /api/limit` 返回 403。

## 接口

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/limit` | 登录即可 | 现行上限、最近调整时间/人 |
| POST | `/api/limit` | 操作员 | 改上限并留痕（相同值不留痕，负数 400） |
| GET | `/api/limit/history` | 登录即可 | 改档痕迹（最近 100 条） |

## 目录

```text
backend/          Django 工程（config/、desk/、worker.py）
frontend/         SolidJS 单页
docker-compose.yml
PRD.md
```
