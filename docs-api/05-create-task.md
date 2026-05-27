# 创建生图任务

## 接口说明

创建文生图或图编辑任务。接口会按场景配置扣除用户积分，并同步等待生图处理完成，直接返回最终任务结果。局部重绘和提示词反推暂不开放 API。

## 请求信息

| 项目 | 内容 |
| --- | --- |
| URL | `/api/tasks` |
| Method | `POST` |
| Content-Type | `application/json` |
| 鉴权 | 需要 API Key |

## Header

| 参数名 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `X-API-Key` | 是 | `sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | 用户 API Key。 |

## Body 参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 否 | `generate` | 任务模式。当前仅支持 `generate`。 |
| `model` | string | 否 | 空 | 模型/场景标识。为空时使用默认模型。 |
| `prompt` | string | 是 | - | 提示词，不能为空，最长 5000 字符。 |
| `size` | string | 否 | `3:4` | 图片比例，例如 `1:1`、`3:4`、`9:16`。 |
| `resolution` | string | 否 | `4K` | 清晰度/图片尺寸选项。部分模型会忽略。 |
| `custom_size` | string | 否 | 空 | 自定义尺寸选项。 |
| `reference_images` | string[] | 否 | `null` | 参考图 base64/data URL 数组。 |

> `source` 字段即使传入也会被服务端强制标记为 `api`。
> 图片参数只接受纯 base64 或 `data:image/png;base64,...` 形式，不需要先上传到 COS。

## 文生图请求示例

```bash
curl --request POST \
  --url "https://你的-api域名/api/tasks" \
  --header "Content-Type: application/json" \
  --header "X-API-Key: sk-yourApiKey" \
  --data '{
    "mode": "generate",
    "model": "banana_pro",
    "prompt": "一只穿宇航服的橘猫，站在月球表面，电影感光影，超清细节",
    "size": "1:1",
    "resolution": "2K"
  }'
```

## 图编辑请求示例

```bash
curl --request POST \
  --url "https://你的-api域名/api/tasks" \
  --header "Content-Type: application/json" \
  --header "X-API-Key: sk-yourApiKey" \
  --data '{
    "mode": "generate",
    "model": "image_edit_scene",
    "prompt": "保持人物姿势不变，把背景换成海边日落",
    "size": "3:4",
    "reference_images": [
      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    ]
  }'
```

## 成功响应

```json
[
  {
    "id": "biz_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "mode": "generate",
    "model": "banana_pro",
    "source": "api",
    "prompt": "一只穿宇航服的橘猫，站在月球表面，电影感光影，超清细节",
    "size": "1:1",
    "resolution": "2K",
    "custom_size": "",
    "credit_cost": 10,
    "credit_refunded": false,
    "status": "success",
    "error_message": "",
    "created_at": "2026-05-27T14:30:00",
    "enqueued_at": null,
    "request_started_at": "2026-05-27T14:30:01",
    "request_finished_at": "2026-05-27T14:30:18",
    "images": [
      {
        "id": 123,
        "image_url": "https://cdn.example.com/generated/xxx.png",
        "preview_url": "",
        "thumb_url": "https://cdn.example.com/generated/xxx.png",
        "status": "success",
        "error_message": "",
        "image_format": "png",
        "image_size_bytes": 2048000
      }
    ]
  }
]
```

## 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `[].id` | string | 任务 ID。 |
| `[].status` | string | 处理结果：`success` 或 `failed`。 |
| `[].credit_cost` | number | 本任务消耗积分。 |
| `[].credit_refunded` | boolean | 失败时是否已退款。 |
| `[].images[].id` | number | 图片 ID。 |
| `[].images[].image_url` | string | 生成图片 URL。 |
| `[].images[].status` | string | 图片状态。 |
| `[].images[].error_message` | string | 图片错误信息。 |

## 错误示例

```json
{
  "detail": "积分不足，需要 20 积分，当前余额 5"
}
```

```json
{
  "detail": "暂不开放局部重绘 API"
}
```

```json
{
  "detail": "reference_images[0] 必须是图片 base64 或 data URL"
}
```

```json
{
  "detail": "任务同步处理失败：生图接口请求超时（120 秒）"
}
```

## 注意事项

- 每个 `POST /api/tasks` 请求默认生成 1 张图片，并按场景单价扣积分。
- 接口会等待外部 AI 服务返回，调用方需要设置足够长的 HTTP 超时时间。
- 如果生成失败，响应仍可能返回任务对象，`status` 为 `failed`，并带有 `error_message`。
