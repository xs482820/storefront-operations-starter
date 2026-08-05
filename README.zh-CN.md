# Storefront Operations Starter

[English](README.md) | [简体中文](README.zh-CN.md)

面向小型零售与批发门店的开源经营系统。

它将客户下单、店员履约和门店管理后台放入同一套代码库，适合作为私域店铺、本地零售店或轻量批发生意的自部署起点。

> 本仓库是通用起步版本，不包含生产数据库、客户记录、真实门店标识、支付凭证、小程序 AppID、AI 密钥、打印机凭证或上传文件。

## 为什么做这个项目

小型门店通常需要比单一商城更完整的经营能力，但又不需要大型 ERP。本项目聚焦日常经营闭环：

- 商品发布：分类、SKU、库存、零售/批发双价格。
- 客户侧：浏览、下单、收货地址、售后申请与消息通知。
- 店员侧：订单履约、发货凭证、客户及商品的只读查询。
- 管理后台：商品、订单、售后、账号、门店设置与操作日志。

仓库还预留了打印和 AI 图片任务的可选接入点；它们默认关闭，不绑定任何供应商。

## 架构

```text
客户小程序  ─┐
店员小程序  ─┼── FastAPI API ── PostgreSQL / Redis
管理后台    ─┘
```

| 模块 | 技术栈 | 用途 |
| --- | --- | --- |
| `backend/` | FastAPI、SQLAlchemy、Alembic | API、权限、业务规则与任务 |
| `frontend-admin/` | Vue 3、TypeScript、Vite、Element Plus | 门店管理后台 |
| `baby-mall-fresh-taro/` | Taro 4、React、TypeScript | 客户侧小程序 |
| `baby-mall-employee-taro/` | Taro 4、React、TypeScript | 店员工作台小程序 |

## 快速开始

### 前置条件

- Docker 与 Docker Compose
- Node.js 20+，用于开发小程序
- 微信开发者工具，用于将 Taro 项目编译为小程序

### 启动后端与管理后台

1. 将 `.env.example` 复制为 `.env`，并把 `JWT_SECRET_KEY` 替换为足够长的随机字符串。
2. 将 `backend/data/storefront-config.example.json` 复制为 `backend/data/storefront-config.json`。
3. 启动本地服务：

   ```bash
   docker compose up --build
   ```

4. 访问 `http://localhost:19080` 打开管理后台；API 地址为 `http://localhost:19000`。

按你的部署流程执行数据库迁移后，再创建管理员、店员、分类和商品。仓库不提供默认管理员密码。

### 启动小程序

两个 Taro 项目各自有独立的 `package.json`：

```bash
cd baby-mall-fresh-taro
npm install
npm run dev:weapp
```

将项目导入微信开发者工具，在 `project.config.json` 填入你自己的 AppID，并在生产环境配置 HTTPS API 域名。店员端在 `baby-mall-employee-taro` 中按同样方式启动。

## 可选集成

核心系统不依赖任何第三方商业服务。只有在配置好你自己的凭证后，才需要启用以下能力：

- **微信能力**：支付、手机号授权与订阅消息。
- **AI 图片**：兼容 OpenAI 的图像服务，密钥只能存放在私有部署环境中。
- **打印**：消费后端创建的打印任务的打印网关。

## 部署提示

- 生产环境使用 HTTPS，并设置强随机 `JWT_SECRET_KEY`。
- `.env`、证书、上传目录、数据库备份和真实 `storefront-config.json` 不应提交到 Git。
- 在服务真实客户前，请按自身业务审查支付、配送和售后规则。仓库内流程仅是工程基础，不构成法律或财务建议。

## 参与贡献

欢迎贡献。小而聚焦的 Pull Request 最容易被审阅：

1. 先创建 Issue，说明问题或改动建议。
2. 改动保持聚焦；非简单逻辑请附带可复现的检查方式。
3. 不要提交任何凭证、生产数据、客户信息或供应商私有配置。

## 路线图

- 补充本地开发用的示例数据与测试夹具。
- 提供常见自部署环境的部署指南。
- 完善打印网关示例和集成文档。
- 增强无障碍支持与多设备小程序测试。

## 许可证

本项目采用 [MIT License](LICENSE) 发布。
