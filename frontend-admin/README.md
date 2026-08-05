# YyY 管理后台前端

这是管理后台的正式业务主线，基于 `Vue 3 + Vite + TypeScript + Pinia + Vue Router + Element Plus`。

## 先看哪里

- [项目地图](../docs/overview/00-project-map.md)
- [管理后台模块索引](../docs/admin/01-admin-module-index.md)
- [Theme and reference policy](../docs/admin/02-theme-and-reference-policy.md)
- [客户侧小程序模块索引](../docs/customer/05-customer-module-index.md)
- [后端服务模块索引](../docs/backend/06-backend-module-index.md)

## 页面范围

- 商品管理
- 订单列表
- 售后处理
- 认证审核
- 客户管理
- 店铺设置

## 共享外壳

- 个人信息编辑：`frontend-admin/src/components/admin/AdminProfileDrawer.vue`
- AI 助手：`frontend-admin/src/components/admin/AdminAiDrawer.vue`
- 侧边栏和顶部栏：`frontend-admin/src/layouts/AdminLayout.vue`

## 启动

```bash
npm install
npm run dev
```

默认本地地址：

- 前端：`http://127.0.0.1:19081`
- 后端代理：`http://127.0.0.1:19000`

## 环境变量

复制 `.env.example` 为 `.env` 后按需修改：

```bash
VITE_API_BASE_URL=/api/v1
```

## 维护约定

- 新页面先看 `src/router/index.ts`
- 列表页优先复用 `BaseListToolbar`、`BaseBatchToolbar`、`BaseMoreMenu`、`BaseDrawer`
- 主题相关改动先看 `src/styles/theme.css`

