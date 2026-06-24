import COS from "cos-js-sdk-v5";
import client from "./client";
import type { UploadCredential, UploadPurpose } from "@/types";

function inferImageContentType(file: File) {
  if (file.type) return file.type;
  const name = file.name.toLowerCase();
  if (/\.(jpe?g)$/.test(name)) return "image/jpeg";
  if (/\.png$/.test(name)) return "image/png";
  if (/\.webp$/.test(name)) return "image/webp";
  if (/\.gif$/.test(name)) return "image/gif";
  return "application/octet-stream";
}

function getUploadCredential(file: File, purpose: UploadPurpose): Promise<UploadCredential> {
  return client.post("/upload/credential", {
    file_name: file.name,
    file_size: file.size,
    content_type: inferImageContentType(file),
    purpose,
  });
}

export function uploadReferenceImage(
  file: File,
  purpose: UploadPurpose = "ref",
  onProgress?: (percent: number) => void,
): Promise<{ url: string; key: string }> {
  return new Promise(async (resolve, reject) => {
    try {
      const credential = await getUploadCredential(file, purpose);
      const cos = new COS({
        getAuthorization(_, callback) {
          callback({
            TmpSecretId: credential.tmp_secret_id,
            TmpSecretKey: credential.tmp_secret_key,
            SecurityToken: credential.session_token,
            StartTime: credential.start_time || Math.floor(Date.now() / 1000),
            ExpiredTime: credential.expired_time,
          });
        },
      });

      cos.putObject(
        {
          Bucket: credential.bucket,
          Region: credential.region,
          Key: credential.key,
          Body: file,
          onProgress(progressData) {
            onProgress?.((progressData.percent || 0) * 100);
          },
        },
        (err) => {
          if (err) {
            reject(err);
            return;
          }
          resolve({ url: credential.url, key: credential.key });
        },
      );
    } catch (error) {
      reject(error);
    }
  });
}
