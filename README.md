# Storefront Operations Starter

一个面向小型零售和批发门店的开源经营系统：客户小程序、店员工作台、管理后台与 FastAPI 后端共用订单、商品、库存和售后数据。

> 这是从实际门店场景中抽离出的通用版本。仓库不包含生产数据、真实门店信息、域名、支付证书、微信 AppID、AI 密钥或打印设备凭证。

## 能做什么

- 商品、分类、SKU、库存与零售/批发双价格
- 客户购物、地址、订单、售后与消息通知
- 店员订单履约、发货凭证、客户和商品只读查询
- 管理后台的商品、订单、售后、用户、门店配置与操作记录
- 可选的打印任务与 AI 图片任务接口，默认关闭，不绑定任何供应商

## 技术栈

- 后端：FastAPI、SQLAlchemy、Alembic、PostgreSQL、Redis
- 管理后台：Vue 3、TypeScript、Vite、Element Plus
- 客户与店员端：Taro 4、React、TypeScript，可编译为微信小程序

## 本地启动

1. 复制 `.env.example` 为 `.env`，把 `JWT_SECRET_KEY` 换成随机长字符串。
2. 复制 `backend/data/storefront-config.example.json` 为 `backend/data/storefront-config.json`。
3. 启动 Docker：`docker compose up --build`。
4. 打开 `http://localhost:19080` 访问管理后台，后端地址为 `http://localhost:19000`。

首次使用需按你的部署方式执行数据库迁移，并通过管理后台创建管理员、店员和商品。仓库刻意不提供通用默认管理员密码。

## 小程序配置

两个 Taro 项目的 `project.config.json` 不含 AppID。导入微信开发者工具前填入你自己的 AppID；在小程序的设置页填入可访问的 API 地址，或修改 `src/services/http.ts` 的默认地址。生产部署应使用 HTTPS 域名并在微信公众平台配置合法域名。

## 集成边界

- 微信支付、手机号能力、订阅消息：需要自行配置商户和小程序凭证。
- AI 图片服务：支持 OpenAI 兼容服务配置，但 API Key 只应放在私有部署环境。
- 打印：后端只保存和派发打印任务，具体网关由部署者接入。

## 安全说明

不要提交 `.env`、证书、上传目录、数据库备份或真实的 `storefront-config.json`。在公开部署前关闭模拟支付与调试设置，并设置强随机 `JWT_SECRET_KEY`。

## License

[MIT](LICENSE)
