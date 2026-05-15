import type { ImageResult } from "@/types";

export const IMAGE_SAFETY_ERROR_MESSAGE = "生成的图像存在安全风险，请尝试修改提示词或参考图。";

const IMAGE_SAFETY_ERROR_PATTERN = /image_unsafe|content blocked/i;

export function isImageSafetyError(rawMessage?: string) {
  return IMAGE_SAFETY_ERROR_PATTERN.test(String(rawMessage || "").trim());
}

export function formatGenerationErrorMessage(rawMessage?: string, fallback = "生成失败，请重试") {
  const detail = String(rawMessage || "").trim();
  if (!detail) return fallback;
  if (isImageSafetyError(detail)) {
    return IMAGE_SAFETY_ERROR_MESSAGE;
  }
  return detail;
}

export function getPreferredGenerationErrorMessage(
  taskError?: string,
  imageError?: string,
  fallback = "生成失败，请重试"
) {
  if (isImageSafetyError(taskError)) {
    return IMAGE_SAFETY_ERROR_MESSAGE;
  }
  if (isImageSafetyError(imageError)) {
    return IMAGE_SAFETY_ERROR_MESSAGE;
  }
  return formatGenerationErrorMessage(imageError || taskError, fallback);
}

export function getTaskImageFailureMessage(
  task: { error_message?: string } | null | undefined,
  image: Pick<ImageResult, "error_message"> | null | undefined,
  fallback = "生成失败，请重试"
) {
  return getPreferredGenerationErrorMessage(task?.error_message, image?.error_message, fallback);
}
