# Banana API 生图接口文档

本文档面向普通用户 API Key 调用方，接口服务来自 `backend-api`。

## 基础信息

- Base URL：`https://你的-api域名`
- 本地示例：`http://127.0.0.1:8000`
- 数据格式：请求与响应均为 JSON。
- 鉴权方式：需要鉴权的接口支持以下任一 Header：

```http
X-API-Key: sk-yourApiKey
```

或：

```http
Authorization: Bearer sk-yourApiKey
```

## 通用错误响应

```json
{
  "detail": "错误说明"
}
```

常见状态码：

- `400`：请求参数错误、积分不足、业务校验失败。
- `401`：缺少 API Key 或 API Key 无效。
- `403`：API Key 禁用/过期、账号禁用、无权访问资源。
- `502`：AI 服务调用失败或同步处理失败。

## 推荐调用流程

1. 查询可用模型/场景配置：`GET /api/config/generation-models`、`GET /api/config/task-scenes`。
2. 如需参考图，将图片转为 base64 或 data URL，直接放入创建任务参数。
3. 创建同步生图任务：`POST /api/tasks`，接口会等待处理完成并直接返回结果。

## 文档列表

- [查询生图模型列表](./01-get-generation-models.md)
- [查询任务场景配置](./02-get-task-scenes.md)
- [创建生图任务](./05-create-task.md)
