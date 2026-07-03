import type { ImageResult } from "@/types";

export const IMAGE_SAFETY_ERROR_MESSAGE = "生成的图片存在安全风险（色情、暴力、版权、政治敏感等），请尝试修改提示词或参考图，或换个模型尝试（不同模型审查尺度不同）！";
export const GENERATION_TASK_FAILURE_MESSAGE = "生图失败，请反馈给我们处理";
export const INVALID_REFERENCE_IMAGE_MESSAGE = "参考图被模型拒绝，请更换正常格式的参考图后重试；或换个模型尝试（不同模型审查尺度不同）！";
export const CREDIT_REFUNDED_SUFFIX = "（积分已返还）";

const IMAGE_SAFETY_ERROR_PATTERN = /unsafe|image_unsafe|content blocked/i;
const INVALID_REFERENCE_IMAGE_PATTERN =
  /invalid image file or mode|provider_request_invalid|bad request to openai|poll rejected: 400|image \d+/i;

export function isImageSafetyError(rawMessage?: string) {
  return IMAGE_SAFETY_ERROR_PATTERN.test(String(rawMessage || "").trim());
}

export function isInvalidReferenceImageError(rawMessage?: string) {
  return INVALID_REFERENCE_IMAGE_PATTERN.test(String(rawMessage || "").trim());
}

export function formatGenerationErrorMessage(rawMessage?: string, fallback = "生成失败，请重试") {
  const detail = String(rawMessage || "").trim();
  if (!detail) return fallback;
  if (isImageSafetyError(detail)) {
    return IMAGE_SAFETY_ERROR_MESSAGE;
  }
  if (isInvalidReferenceImageError(detail)) {
    return INVALID_REFERENCE_IMAGE_MESSAGE;
  }
  return detail;
}

function withCreditRefundedSuffix(message: string) {
  return message.endsWith(CREDIT_REFUNDED_SUFFIX) ? message : `${message}${CREDIT_REFUNDED_SUFFIX}`;
}

export function formatGenerationTaskFailureMessage(rawMessage?: string, creditRefunded = false) {
  const detail = String(rawMessage || "").trim();
  const message = isImageSafetyError(detail)
    ? IMAGE_SAFETY_ERROR_MESSAGE
    : isInvalidReferenceImageError(detail)
      ? INVALID_REFERENCE_IMAGE_MESSAGE
      : GENERATION_TASK_FAILURE_MESSAGE;
  return creditRefunded ? withCreditRefundedSuffix(message) : message;
}

export function getPreferredGenerationErrorMessage(
  taskError?: string,
  imageError?: string,
  creditRefunded = false,
  _fallback = "生成失败，请重试"
) {
  return formatGenerationTaskFailureMessage(imageError || taskError, creditRefunded);
}

export function getTaskImageFailureMessage(
  task: { error_message?: string; credit_refunded?: boolean } | null | undefined,
  image: Pick<ImageResult, "error_message"> | null | undefined,
  fallback = "生成失败，请重试"
) {
  return getPreferredGenerationErrorMessage(task?.error_message, image?.error_message, Boolean(task?.credit_refunded), fallback);
}
