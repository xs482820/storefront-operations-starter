# baby-mall-employee-taro

店员侧 Taro 小程序 MVP。

当前定位：
- 独立于客户侧小程序，不混用客户侧页面。
- 复用 Taro + React + VantUI 的最小依赖。
- 先跑通店员工作流壳子：登录、工作台、订单、订单详情、核货、发货/自提、售后、客户查询、我的。
- 暂时使用 `src/mock/work.ts`，后续接现有后端订单/售后/客户 API。

验证：

```bash
npm run build:weapp
npx tsc --noEmit --skipLibCheck
```

打开微信开发者工具时选择本目录，构建产物目录为 `dist/`。
