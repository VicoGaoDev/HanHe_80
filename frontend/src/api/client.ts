import axios from "axios";
import router from "@/router";
import { clearStoredAuth, getStoredToken } from "@/lib/auth";

const BASE = import.meta.env.VITE_API_BASE_URL || "";

const client = axios.create({
  baseURL: `${BASE}/api`,
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res.data,
  (error) => {
    if (error.response?.status === 401) {
      const url = String(error.config?.url ?? "");
      const isAuthCredentialsRequest =
        url.includes("/auth/login") || url.includes("/auth/register");
      if (!isAuthCredentialsRequest) {
        clearStoredAuth();
        router.push("/templates");
      }
    }
    return Promise.reject(error);
  }
);

export default client;
