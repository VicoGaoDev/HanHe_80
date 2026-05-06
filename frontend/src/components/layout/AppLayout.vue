<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, h, provide, nextTick, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { message } from "ant-design-vue";
import {
  login as apiLogin,
  register as apiRegister,
  getMe,
  getContactConfig,
  getAnnouncementConfig,
} from "@/api/auth";
import { registerCloudbaseAccount, sendRegisterEmailCode } from "@/lib/cloudbase";
import { APP_THEME_ATTRIBUTE, type AppThemeName } from "@/config/theme";
import { getCurrentTheme } from "@/lib/theme";
import type { AnnouncementConfig } from "@/types";
import {
  PictureOutlined,
  SettingOutlined,
  TeamOutlined,
  BarChartOutlined,
  KeyOutlined,
  CloudUploadOutlined,
  LogoutOutlined,
  LockOutlined,
  DownOutlined,
  UserOutlined,
  UserAddOutlined,
  ThunderboltOutlined,
  MenuOutlined,
  MailOutlined,
  MessageOutlined,
} from "@ant-design/icons-vue";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const isAdmin = computed(() => auth.isAdmin);
const isSuperAdmin = computed(() => auth.isSuperAdmin);
const mobileDrawerOpen = ref(false);
const routeTransitionName = ref("route-page-forward");

const routeOrder = new Map<string, number>([
  ["/", 0],
  ["/templates", 1],
  ["/generate", 2],
  ["/history", 3],
  ["/profile", 4],
  ["/settings", 5],
  ["/credit-logs", 6],
  ["/feedbacks", 7],
  ["/feedbacks/:feedbackId", 8],
  ["/admin/templates", 9],
  ["/admin/users", 10],
  ["/admin/dashboard", 11],
  ["/admin/feedbacks", 12],
  ["/admin/feedbacks/:feedbackId", 13],
  ["/admin/api-key", 14],
  ["/admin/cos-config", 15],
  ["/admin/external-api-configs", 16],
]);

const currentTheme = ref<AppThemeName>(getCurrentTheme());
let themeObserver: MutationObserver | null = null;

const primaryMenuItems = [
  { key: "templates", label: "创意模版", iconSrc: "/nav-templates.svg", darkIconSrc: "/nav-templates-mono.svg" },
  { key: "generate", label: "自定义绘图", iconSrc: "/nav-generate.svg" },
  { key: "history", label: "历史记录", iconSrc: "/nav-history.svg", darkIconSrc: "/nav-history-mono.svg" },
];

function getPrimaryMenuIconSrc(item: (typeof primaryMenuItems)[number]) {
  if (currentTheme.value === "dark" && item.darkIconSrc) {
    return item.darkIconSrc;
  }
  return item.iconSrc;
}

const adminMenuItems = computed(() =>
  [
    { key: "/admin/templates", label: "模版管理", icon: PictureOutlined, superAdminOnly: false },
    { key: "/admin/users", label: "用户管理", icon: TeamOutlined, superAdminOnly: false },
    { key: "/admin/dashboard", label: "数据统计", icon: BarChartOutlined, superAdminOnly: false },
    { key: "/admin/feedbacks", label: "用户 Feedback", icon: MessageOutlined, superAdminOnly: false },
    { key: "/admin/cos-config", label: "COS 配置", icon: CloudUploadOutlined, superAdminOnly: true },
    { key: "/admin/external-api-configs", label: "接口管理", icon: KeyOutlined, superAdminOnly: true },
  ].filter((item) => !item.superAdminOnly || isSuperAdmin.value)
);

const userMenuItems = [
  { key: "profile", label: "个人主页", icon: UserOutlined, danger: false },
  { key: "my-feedback", label: "我的反馈", icon: MessageOutlined, danger: false },
  { key: "settings", label: "设置", icon: SettingOutlined, danger: false },
  { key: "credits", label: "积分记录", icon: ThunderboltOutlined, danger: false },
  { key: "logout", label: "退出登录", icon: LogoutOutlined, danger: true },
];

function getRouteRank(path: string) {
  if (path.startsWith("/feedbacks/")) return routeOrder.get("/feedbacks/:feedbackId") ?? 0;
  if (path.startsWith("/admin/feedbacks/")) return routeOrder.get("/admin/feedbacks/:feedbackId") ?? 0;
  return routeOrder.get(path) ?? 0;
}

const selectedKeys = computed(() => {
  const p = route.path;
  if (p.startsWith("/admin")) return ["admin"];
  if (p === "/") return [];
  if (p === "/templates") return ["templates"];
  if (p === "/history") return ["history"];
  if (p === "/profile" || p === "/settings" || p === "/credit-logs" || p.startsWith("/feedbacks")) return [];
  return ["generate"];
});

const adminSelectedKeys = computed(() => {
  if (!route.path.startsWith("/admin")) return [];
  if (route.path.startsWith("/admin/feedbacks")) return ["/admin/feedbacks"];
  return [route.path];
});

watch(
  () => route.path,
  (to, from) => {
    const toRank = getRouteRank(to);
    const fromRank = getRouteRank(from ?? "");
    routeTransitionName.value = toRank < fromRank ? "route-page-back" : "route-page-forward";
  },
  { immediate: true }
);

function handleMenuClick({ key }: { key: string }) {
  mobileDrawerOpen.value = false;
  if (key === "templates") router.push("/templates");
  else if (key === "generate") router.push("/generate");
  else if (key === "history") {
    if (!auth.isLoggedIn) {
      loginModalVisible.value = true;
      return;
    }
    router.push("/history");
  }
}

function handleAdminMenu({ key }: { key: string }) {
  mobileDrawerOpen.value = false;
  router.push(key);
}

function handleUserMenu({ key }: { key: string }) {
  mobileDrawerOpen.value = false;
  if (key === "profile") router.push("/profile");
  else if (key === "my-feedback") router.push("/feedbacks");
  else if (key === "settings") router.push("/settings");
  else if (key === "credits") router.push("/credit-logs");
  else if (key === "logout") {
    auth.logout();
    router.push("/");
  }
}

const loginModalVisible = ref(false);
provide("loginModalVisible", loginModalVisible);
const authTab = ref<"login" | "register">("login");
const loginForm = reactive({ account: "", password: "" });
const loginLoading = ref(false);
const registerForm = reactive({ email: "", verificationCode: "", username: "", password: "", confirmPassword: "" });
const registerLoading = ref(false);
const registerCodeLoading = ref(false);

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function openAuthModal(tab: "login" | "register") {
  mobileDrawerOpen.value = false;
  authTab.value = tab;
  loginModalVisible.value = true;
}

function resetAuthForms() {
  loginForm.account = "";
  loginForm.password = "";
  registerForm.email = "";
  registerForm.verificationCode = "";
  registerForm.username = "";
  registerForm.password = "";
  registerForm.confirmPassword = "";
}

async function handleLoginSubmit() {
  if (!loginForm.account || !loginForm.password) {
    message.warning("请输入邮箱/用户名和密码");
    return;
  }
  loginLoading.value = true;
  try {
    const res = await apiLogin(loginForm.account, loginForm.password);
    auth.setAuth(res.token, res.user);
    message.success("登录成功");
    loginModalVisible.value = false;
    resetAuthForms();
    await nextTick();
    await checkAnnouncement();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "登录失败");
  } finally {
    loginLoading.value = false;
  }
}

async function handleSendRegisterCode() {
  if (!registerForm.email) {
    message.warning("请输入邮箱");
    return;
  }
  if (!isValidEmail(registerForm.email)) {
    message.warning("邮箱格式不正确");
    return;
  }
  registerCodeLoading.value = true;
  try {
    await sendRegisterEmailCode(registerForm.email.trim());
    message.success("验证码已发送，请检查邮箱");
  } catch (err: any) {
    message.error(err.message || "验证码发送失败");
  } finally {
    registerCodeLoading.value = false;
  }
}

async function handleRegisterSubmit() {
  if (!registerForm.email || !registerForm.verificationCode || !registerForm.username || !registerForm.password) {
    message.warning("请完整填写注册信息");
    return;
  }
  if (!isValidEmail(registerForm.email)) {
    message.warning("邮箱格式不正确");
    return;
  }
  if (registerForm.password.length < 6) {
    message.warning("密码至少6位");
    return;
  }
  if (!/^\d{6}$/.test(registerForm.verificationCode.trim())) {
    message.warning("请输入正确的 6 位验证码");
    return;
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    message.warning("两次密码不一致");
    return;
  }
  registerLoading.value = true;
  try {
    await registerCloudbaseAccount(
      registerForm.email.trim(),
      registerForm.verificationCode.trim(),
      registerForm.password
    );
    const res = await apiRegister(
      registerForm.username.trim(),
      registerForm.email.trim(),
      registerForm.password
    );
    auth.setAuth(res.token, res.user);
    message.success("注册成功");
    loginModalVisible.value = false;
    resetAuthForms();
    await nextTick();
    await checkAnnouncement();
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || "注册失败");
  } finally {
    registerLoading.value = false;
  }
}

const creditsContactVisible = ref(false);
const contactQrImage = ref("");
const announcementVisible = ref(false);
const announcementDismissToday = ref(false);
const announcementConfig = ref<AnnouncementConfig>({
  announcement_enabled: false,
  announcement_content: "",
  announcement_updated_at: null,
});
const ANNOUNCEMENT_DISMISS_KEY = "systemAnnouncementDismissState";
const authInputPrefixStyle = { color: "var(--theme-input-prefix-color)" };

const avatarUrl = computed(() => auth.user?.avatar_url || "");
const avatarFallback = computed(() => auth.user?.username?.charAt(0)?.toUpperCase() || "U");

function getTodayString() {
  return new Date().toLocaleDateString("en-CA");
}

function getAnnouncementVersion(config: AnnouncementConfig) {
  return config.announcement_updated_at || "";
}

function shouldSuppressAnnouncement(config: AnnouncementConfig) {
  try {
    const raw = localStorage.getItem(ANNOUNCEMENT_DISMISS_KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw);
    return parsed?.date === getTodayString() && parsed?.version === getAnnouncementVersion(config);
  } catch {
    return false;
  }
}

function handleAnnouncementClose() {
  if (announcementDismissToday.value) {
    localStorage.setItem(ANNOUNCEMENT_DISMISS_KEY, JSON.stringify({
      date: getTodayString(),
      version: getAnnouncementVersion(announcementConfig.value),
    }));
  }
  announcementVisible.value = false;
}

async function checkAnnouncement() {
  try {
    const res = await getAnnouncementConfig();
    announcementConfig.value = res;
    if (!res.announcement_enabled || !res.announcement_content.trim() || shouldSuppressAnnouncement(res)) {
      return;
    }
    announcementDismissToday.value = false;
    announcementVisible.value = true;
  } catch {
    // ignore announcement config failures
  }
}

onMounted(async () => {
  if (typeof document !== "undefined") {
    themeObserver = new MutationObserver(() => {
      currentTheme.value = getCurrentTheme();
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: [APP_THEME_ATTRIBUTE],
    });
  }

  await Promise.allSettled([
    (async () => {
      const res = await getContactConfig();
      contactQrImage.value = res.contact_qr_image || "";
    })(),
    checkAnnouncement(),
  ]);

  if (!auth.isLoggedIn) return;
  try {
    auth.updateUser(await getMe());
  } catch {
    // ignore sync failures for stale sessions
  }
});

onBeforeUnmount(() => {
  themeObserver?.disconnect();
  themeObserver = null;
});

function openCreditsContact() {
  mobileDrawerOpen.value = false;
  creditsContactVisible.value = true;
}

function toggleMobileDrawer() {
  mobileDrawerOpen.value = !mobileDrawerOpen.value;
}

watch(
  () => route.fullPath,
  () => {
    mobileDrawerOpen.value = false;
  }
);

</script>

<template>
  <a-layout class="app-layout">
    <a-layout-header class="app-header">
      <div class="header-inner">
        <div class="header-brand" @click="router.push('/')">
          <div class="brand-mark">🍌</div>
          <div class="brand-copy">
            <span class="brand-name">80AI</span>
            <span class="brand-sub">AI Creative Studio</span>
          </div>
        </div>

        <div class="mobile-nav-entry">
          <div v-if="auth.isLoggedIn" class="mobile-nav-credits" @click="openCreditsContact">
            <ThunderboltOutlined />
            <span>{{ auth.user?.credits ?? 0 }}</span>
          </div>
          <a-button class="mobile-nav-fab" type="primary" shape="circle" @click="toggleMobileDrawer">
            <template #icon><MenuOutlined /></template>
          </a-button>
        </div>

        <a-menu
          mode="horizontal"
          :selected-keys="selectedKeys"
          class="header-menu"
          @click="handleMenuClick"
        >
          <a-menu-item v-for="item in primaryMenuItems" :key="item.key">
            <img :src="getPrimaryMenuIconSrc(item)" :alt="item.label" class="nav-menu-icon" />
            <span>{{ item.label }}</span>
          </a-menu-item>
        </a-menu>

        <div class="header-actions">
          <template v-if="auth.isLoggedIn">
            <a-dropdown v-if="isAdmin" :trigger="['hover']" overlay-class-name="warm-dropdown">
              <a-button class="admin-btn" type="text">
                <SettingOutlined />
                管理后台
                <DownOutlined style="font-size: 10px; margin-left: 4px" />
              </a-button>
              <template #overlay>
                <a-menu :selected-keys="adminSelectedKeys" @click="handleAdminMenu">
                  <a-menu-item v-for="item in adminMenuItems" :key="item.key">
                    <component :is="item.icon" />
                    <span style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>

            <div class="credits-badge" @click="openCreditsContact">
              <ThunderboltOutlined />
              <span>{{ auth.user?.credits ?? 0 }}</span>
            </div>

            <a-dropdown :trigger="['hover']" overlay-class-name="warm-dropdown">
              <div class="user-trigger">
                <a-avatar :size="34" class="user-avatar" :src="avatarUrl || undefined">
                  {{ avatarFallback }}
                </a-avatar>
                <span class="user-name">{{ auth.user?.username }}</span>
              </div>
              <template #overlay>
                <a-menu @click="handleUserMenu">
                  <a-menu-item
                    v-for="item in userMenuItems.filter((entry) => !entry.danger)"
                    :key="item.key"
                  >
                    <component :is="item.icon" />
                    <span style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item
                    v-for="item in userMenuItems.filter((entry) => entry.danger)"
                    :key="item.key"
                    danger
                  >
                    <component :is="item.icon" />
                    <span style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </template>

          <template v-else>
            <a-button type="primary" class="login-header-btn" @click="openAuthModal('login')">
              <template #icon><UserOutlined /></template>
              登录
            </a-button>
            <a-button class="register-header-btn" @click="openAuthModal('register')">
              <template #icon><UserAddOutlined /></template>
              注册
            </a-button>
          </template>
        </div>
      </div>
    </a-layout-header>

    <a-layout-content class="app-content">
      <div class="content-inner">
        <router-view v-slot="{ Component, route: currentRoute }">
          <transition :name="routeTransitionName" mode="out-in">
            <div :key="currentRoute.path" class="route-page-shell">
              <component :is="Component" />
            </div>
          </transition>
        </router-view>
      </div>
    </a-layout-content>

    <a-drawer
      v-model:open="mobileDrawerOpen"
      placement="right"
      :width="320"
      class="mobile-nav-drawer"
      title="导航菜单"
    >
      <div class="mobile-drawer-content">
        <div class="mobile-drawer-brand">
          <div class="brand-mark">🍌</div>
          <div class="brand-copy">
            <span class="brand-name">80AI</span>
            <span class="brand-sub">AI Creative Studio</span>
          </div>
        </div>

        <div v-if="auth.isLoggedIn" class="mobile-user-card">
          <a-avatar :size="48" class="user-avatar" :src="avatarUrl || undefined">
            {{ avatarFallback }}
          </a-avatar>
          <div class="mobile-user-meta">
            <span class="mobile-user-name">{{ auth.user?.username }}</span>
            <span class="mobile-user-role">
              {{ isSuperAdmin ? "超级管理员" : isAdmin ? "管理员" : "普通用户" }}
            </span>
          </div>
          <div class="mobile-user-credits" @click="openCreditsContact">
            <ThunderboltOutlined />
            <span>{{ auth.user?.credits ?? 0 }}</span>
          </div>
        </div>

        <div class="mobile-drawer-section">
          <div class="mobile-drawer-section-title">功能导航</div>
          <a-menu
            mode="inline"
            :selected-keys="selectedKeys"
            class="mobile-drawer-menu"
            @click="handleMenuClick"
          >
            <a-menu-item v-for="item in primaryMenuItems" :key="item.key">
              <img :src="getPrimaryMenuIconSrc(item)" :alt="item.label" class="nav-menu-icon" />
              <span>{{ item.label }}</span>
            </a-menu-item>
          </a-menu>
        </div>

        <div v-if="auth.isLoggedIn && isAdmin" class="mobile-drawer-section">
          <div class="mobile-drawer-section-title">管理后台</div>
          <a-menu
            mode="inline"
            :selected-keys="adminSelectedKeys"
            class="mobile-drawer-menu"
            @click="handleAdminMenu"
          >
            <a-menu-item v-for="item in adminMenuItems" :key="item.key">
              <component :is="item.icon" />
              <span>{{ item.label }}</span>
            </a-menu-item>
          </a-menu>
        </div>

        <div class="mobile-drawer-section">
          <div class="mobile-drawer-section-title">
            {{ auth.isLoggedIn ? "账户操作" : "账户入口" }}
          </div>

          <div v-if="auth.isLoggedIn">
            <a-menu mode="inline" class="mobile-drawer-menu" @click="handleUserMenu">
              <a-menu-item
                v-for="item in userMenuItems"
                :key="item.key"
                :danger="item.danger"
              >
                <component :is="item.icon" />
                <span>{{ item.label }}</span>
              </a-menu-item>
            </a-menu>
          </div>
          <div v-else class="mobile-auth-actions">
            <a-button type="primary" class="login-header-btn" block @click="openAuthModal('login')">
              <template #icon><UserOutlined /></template>
              登录
            </a-button>
            <a-button class="register-header-btn" block @click="openAuthModal('register')">
              <template #icon><UserAddOutlined /></template>
              注册
            </a-button>
          </div>
        </div>
      </div>
    </a-drawer>

    <a-modal
      v-model:open="creditsContactVisible"
      title="联系我们"
      :footer="null"
      :width="420"
      centered
    >
      <div class="credits-contact-modal">
        <div v-if="contactQrImage" class="credits-contact-qr">
          <img :src="contactQrImage" alt="contact qr code" />
        </div>
        <div v-else class="credits-contact-empty">
          暂未配置联系二维码，请联系管理员
        </div>
        <ul class="credits-contact-list">
          <li>积分获取</li>
          <li>API调用</li>
          <li>技术支持</li>
          <li>需求定制</li>
        </ul>
      </div>
    </a-modal>

    <a-modal
      v-model:open="announcementVisible"
      title="系统公告"
      :footer="null"
      :width="520"
      centered
      @cancel="handleAnnouncementClose"
    >
      <div class="announcement-modal">
        <div class="announcement-content">
          {{ announcementConfig.announcement_content }}
        </div>
        <a-checkbox v-model:checked="announcementDismissToday">
          今日不再弹出
        </a-checkbox>
        <div class="announcement-actions">
          <a-button type="primary" class="warm-primary-btn" @click="handleAnnouncementClose">
            知道了
          </a-button>
        </div>
      </div>
    </a-modal>

    <a-modal
      v-model:open="loginModalVisible"
      :title="null"
      :footer="null"
      :width="420"
      centered
      @after-close="resetAuthForms"
    >
      <a-tabs v-model:activeKey="authTab" centered class="auth-tabs">
        <a-tab-pane key="login" tab="登录">
          <a-form layout="vertical" :model="loginForm" @finish="handleLoginSubmit" style="margin-top: 8px">
            <a-form-item label="邮箱（推荐）/ 用户名">
              <a-input
                v-model:value="loginForm.account"
                size="large"
                placeholder="优先使用邮箱登录"
                :prefix="h(UserOutlined, { style: authInputPrefixStyle })"
              />
            </a-form-item>
            <a-form-item label="密码">
              <a-input-password
                v-model:value="loginForm.password"
                size="large"
                placeholder="请输入密码"
                :prefix="h(LockOutlined, { style: authInputPrefixStyle })"
                @press-enter="handleLoginSubmit"
              />
            </a-form-item>
            <a-form-item style="margin-bottom: 8px">
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                :loading="loginLoading"
                block
                class="warm-primary-btn"
              >
                <template #icon><ThunderboltOutlined /></template>
                {{ loginLoading ? "登录中..." : "登录" }}
              </a-button>
            </a-form-item>
            <div class="auth-switch-hint">
              用户名重复时，请改用邮箱登录
            </div>
            <div class="auth-switch-hint" style="margin-top: 6px">
              还没有账号？<a @click="authTab = 'register'">立即注册</a>
            </div>
          </a-form>
        </a-tab-pane>

        <a-tab-pane key="register" tab="注册">
          <a-form layout="vertical" :model="registerForm" @finish="handleRegisterSubmit" style="margin-top: 8px">
            <a-form-item label="邮箱">
              <a-input
                v-model:value="registerForm.email"
                size="large"
                placeholder="请输入常用邮箱"
                :prefix="h(MailOutlined, { style: authInputPrefixStyle })"
                :maxlength="255"
              />
            </a-form-item>
            <a-form-item label="验证码">
              <div class="auth-code-row">
                <a-input
                  v-model:value="registerForm.verificationCode"
                  size="large"
                  placeholder="请输入 6 位验证码"
                  :maxlength="6"
                  @press-enter="handleRegisterSubmit"
                />
                <a-button
                  size="large"
                  class="auth-code-btn"
                  :loading="registerCodeLoading"
                  @click="handleSendRegisterCode"
                >
                  {{ registerCodeLoading ? "发送中..." : "发送验证码" }}
                </a-button>
              </div>
            </a-form-item>
            <a-form-item label="用户名">
              <a-input
                v-model:value="registerForm.username"
                size="large"
                placeholder="2-20 个字符"
                :prefix="h(UserOutlined, { style: authInputPrefixStyle })"
                :maxlength="20"
              />
            </a-form-item>
            <a-form-item label="密码">
              <a-input-password
                v-model:value="registerForm.password"
                size="large"
                placeholder="至少 6 位"
                :prefix="h(LockOutlined, { style: authInputPrefixStyle })"
              />
            </a-form-item>
            <a-form-item label="确认密码">
              <a-input-password
                v-model:value="registerForm.confirmPassword"
                size="large"
                placeholder="请再次输入密码"
                :prefix="h(LockOutlined, { style: authInputPrefixStyle })"
                @press-enter="handleRegisterSubmit"
              />
            </a-form-item>
            <a-form-item style="margin-bottom: 8px">
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                :loading="registerLoading"
                block
                class="warm-primary-btn"
              >
                <template #icon><UserAddOutlined /></template>
                {{ registerLoading ? "注册中..." : "注册" }}
              </a-button>
            </a-form-item>
            <div class="auth-switch-hint">
              已有账号？<a @click="authTab = 'login'">去登录</a>
            </div>
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </a-modal>
  </a-layout>
</template>

<style scoped lang="scss">
.app-layout {
  min-height: 100vh;
  background:
    radial-gradient(circle at top, var(--theme-page-glow), transparent 28%),
    var(--theme-page-gradient);
}

.app-header {
  background: var(--theme-header-bg) !important;
  box-shadow: 0 16px 32px var(--theme-header-shadow);
  padding: 0 24px !important;
  height: 74px;
  line-height: normal;
  position: sticky;
  top: 0;
  z-index: 1000;
  border-bottom: 1px solid var(--theme-header-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0;
  height: 100%;
  background: transparent;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  margin-right: 34px;
  flex-shrink: 0;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, var(--theme-brand-bg-start), var(--theme-brand-bg-end));
  box-shadow: 0 12px 22px var(--theme-brand-shadow);
  font-size: 24px;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--theme-title);
  letter-spacing: -0.2px;
}

.brand-sub {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--theme-subtitle);
}

.header-menu {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: max-content;
  border-bottom: none !important;
  background: transparent;
  line-height: 54px;

  :deep(.ant-menu-item) {
    height: 46px;
    line-height: 46px;
    margin-inline: 4px !important;
    padding-inline: 16px !important;
    border-radius: 16px;
    font-weight: 700;
    color: var(--theme-nav-text);

    &::after {
      display: none;
    }
  }

  :deep(.ant-menu-item-selected) {
    background: linear-gradient(
      180deg,
      var(--theme-nav-active-bg-start),
      var(--theme-nav-active-bg-end)
    ) !important;
    color: var(--theme-nav-active-text) !important;
    box-shadow: 0 10px 18px var(--theme-nav-active-shadow);
  }

  :deep(.ant-menu-item-selected .nav-menu-icon) {
    filter: var(--theme-nav-icon-active-filter);
  }

  :deep(.ant-menu-item:not(.ant-menu-item-selected):hover) {
    color: var(--theme-nav-hover-text) !important;
    background: var(--theme-nav-hover-bg) !important;
  }

  :deep(.ant-menu-title-content) {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
}

.nav-menu-icon {
  width: 20px;
  height: 20px;
  display: block;
  flex-shrink: 0;
  filter: var(--theme-nav-icon-filter);
  transition: filter var(--motion-duration-fast) var(--motion-ease-soft);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.mobile-nav-fab {
  width: 54px;
  height: 54px;
  display: none;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: none !important;
  background: var(--theme-accent) !important;
  box-shadow: 0 16px 30px var(--theme-fab-shadow);
}

.mobile-nav-entry {
  display: none;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.mobile-nav-credits {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 42px;
  padding: 0 14px;
  border-radius: 999px;
  background: var(--theme-pill-bg);
  border: 1px solid var(--theme-pill-border);
  color: var(--theme-pill-text);
  font-weight: 700;
  box-shadow: 0 10px 22px var(--theme-pill-shadow);
  cursor: pointer;
}

.mobile-drawer-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.mobile-drawer-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mobile-user-card {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 22px;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong));
  border: 1px solid var(--theme-panel-border-strong);
  box-shadow: 0 12px 24px var(--theme-card-shadow);
}

.mobile-user-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.mobile-user-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--theme-title);
  word-break: break-all;
}

.mobile-user-role {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.mobile-user-credits {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--theme-pill-bg-strong);
  color: var(--theme-pill-text);
  font-weight: 700;
  cursor: pointer;
}

.mobile-drawer-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-drawer-section-title {
  padding-left: 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--theme-subtitle);
}

.mobile-drawer-menu {
  border-inline-end: none !important;
  background: transparent !important;

  :deep(.ant-menu-item) {
    display: flex;
    align-items: center;
    height: 48px;
    line-height: 48px;
    margin: 4px 0 !important;
    border-radius: 16px;
    font-weight: 700;
    color: var(--theme-nav-text);
  }

  :deep(.ant-menu-title-content) {
    display: inline-flex;
    align-items: center;
    min-width: 0;
  }

  :deep(.ant-menu-item-selected) {
    background: linear-gradient(
      180deg,
      var(--theme-nav-active-bg-start),
      var(--theme-nav-active-bg-end)
    ) !important;
    color: var(--theme-nav-active-text) !important;
    box-shadow: 0 10px 18px var(--theme-nav-active-shadow);
  }

  :deep(.ant-menu-item-selected .nav-menu-icon) {
    filter: var(--theme-nav-icon-active-filter);
  }

  :deep(.ant-menu-item-danger) {
    color: #c85a49 !important;
  }

  :deep(.ant-menu-item-danger:hover) {
    background: #fff1ee !important;
    color: #b84b3b !important;
  }
}

.mobile-auth-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.admin-btn {
  height: 40px;
  padding-inline: 14px;
  border-radius: 999px;
  border: 1px solid var(--theme-panel-border-strong) !important;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong)) !important;
  color: var(--theme-accent-text) !important;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  box-shadow: 0 10px 22px var(--theme-card-shadow);

  &:hover {
    color: var(--theme-accent-text-hover) !important;
    border-color: var(--theme-border-strong) !important;
    background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong)) !important;
    box-shadow: 0 12px 24px var(--theme-card-shadow-strong);
  }
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 6px 6px;
  border-radius: 18px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  border: 1px solid transparent;

  &:hover {
    background: var(--theme-panel-bg-muted);
    border-color: var(--theme-panel-border);
  }
}

.user-avatar {
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  font-weight: 700;
  box-shadow: 0 10px 16px var(--theme-nav-active-shadow);
}

.user-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--theme-title);
}

.credits-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--theme-accent-text);
  cursor: pointer;
  transition: color 0.2s, transform 0.2s;

  &:hover {
    color: var(--theme-accent-text-hover);
    transform: translateY(-1px);
  }
}

.credits-contact-modal {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  padding: 8px 0 4px;
  text-align: center;
}

.credits-contact-list {
  display: grid;
  grid-template-columns: repeat(2, auto);
  justify-content: center;
  justify-items: start;
  column-gap: 28px;
  row-gap: 8px;
  margin: 0 auto;
  width: max-content;
  max-width: 100%;
  padding: 0 0 0 1.15em;
  box-sizing: border-box;
  list-style: disc;
  list-style-position: outside;
  text-align: left;
  color: var(--theme-text-secondary);
  font-size: 14px;
  line-height: 1.6;

  li {
    display: list-item;

    &::marker {
      font-size: 0.75em;
      color: var(--theme-subtitle);
    }
  }
}

.credits-contact-qr {
  width: 240px;
  height: 240px;
  padding: 10px;
  border-radius: 24px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
  box-shadow: inset 0 0 0 1px var(--theme-panel-inset);

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    border-radius: 18px;
    background: var(--theme-empty-bg);
  }
}

.credits-contact-empty {
  width: 100%;
  padding: 26px 18px;
  border-radius: 20px;
  background: var(--theme-panel-bg-soft);
  border: 1px dashed var(--theme-empty-border);
  color: var(--theme-text-secondary);
  line-height: 1.8;
}

.announcement-modal {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 6px 0 2px;
}

.announcement-content {
  white-space: pre-wrap;
  line-height: 1.85;
  color: var(--theme-text);
  font-size: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
}

.announcement-actions {
  display: flex;
  justify-content: flex-end;
}

.app-content {
  padding: 22px 24px 28px;
}

.content-inner {
  max-width: 1400px;
  margin: 0 auto;
  position: relative;
}

.route-page-shell {
  min-width: 0;
}

.route-page-forward-enter-active,
.route-page-forward-leave-active,
.route-page-back-enter-active,
.route-page-back-leave-active {
  transition:
    opacity var(--motion-duration-reveal-fast) var(--motion-ease-soft),
    transform var(--motion-duration-reveal) var(--motion-ease-enter),
    filter var(--motion-duration-reveal-fast) var(--motion-ease-soft);
}

.route-page-forward-enter-from {
  opacity: 0;
  transform: translate3d(18px, 0, 0);
  filter: blur(8px);
}

.route-page-forward-leave-to {
  opacity: 0;
  transform: translate3d(-14px, 0, 0);
  filter: blur(6px);
}

.route-page-back-enter-from {
  opacity: 0;
  transform: translate3d(-18px, 0, 0);
  filter: blur(8px);
}

.route-page-back-leave-to {
  opacity: 0;
  transform: translate3d(14px, 0, 0);
  filter: blur(6px);
}

.route-page-forward-enter-to,
.route-page-forward-leave-from,
.route-page-back-enter-to,
.route-page-back-leave-from {
  opacity: 1;
  transform: translate3d(0, 0, 0);
  filter: blur(0);
}

:deep(.mobile-nav-drawer .ant-drawer-header) {
  padding: 20px 20px 0;
  border-bottom: none;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
}

:deep(.mobile-nav-drawer .ant-drawer-title) {
  color: var(--theme-title);
  font-weight: 700;
}

:deep(.mobile-nav-drawer .ant-drawer-body) {
  padding: 18px 20px 24px;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-muted));
}

:deep(.ant-modal .ant-input-affix-wrapper),
:deep(.ant-modal .ant-input-password),
:deep(.ant-modal .ant-input) {
  border-radius: 14px;
}

:deep(.ant-modal .ant-btn-primary) {
  background: var(--theme-accent) !important;
  border: none !important;
}

.login-header-btn {
  height: 42px;
  padding-inline: 20px;
  border-radius: 999px;
  font-weight: 700;
  background: var(--theme-accent) !important;
  border: none !important;
  box-shadow: 0 10px 22px var(--theme-nav-active-shadow);
}

.register-header-btn {
  height: 42px;
  padding-inline: 20px;
  border-radius: 999px;
  font-weight: 700;
  border: 1px solid var(--theme-panel-border-strong) !important;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong)) !important;
  color: var(--theme-accent-text) !important;
  box-shadow: 0 10px 22px var(--theme-card-shadow);

  &:hover {
    color: var(--theme-accent-text-hover) !important;
    border-color: var(--theme-border-strong) !important;
    background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong)) !important;
  }
}

.auth-tabs {
  :deep(.ant-tabs-nav) {
    margin-bottom: 4px;
  }

  :deep(.ant-tabs-tab) {
    font-weight: 700;
    font-size: 15px;
    color: var(--theme-text-muted);
  }

  :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
    color: var(--theme-accent-text) !important;
  }

  :deep(.ant-tabs-ink-bar) {
    background: var(--theme-accent);
    height: 3px;
    border-radius: 2px;
  }
}

.auth-switch-hint {
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-muted);

  a {
    color: var(--theme-link);
    font-weight: 600;
    cursor: pointer;

    &:hover {
      color: var(--theme-link-hover);
    }
  }
}

.auth-code-row {
  display: flex;
  gap: 10px;

  > :first-child {
    flex: 1;
  }
}

.auth-code-btn {
  flex: 0 0 auto;
}

@media (max-width: 960px) {
  .app-header {
    padding-inline: 16px !important;
    height: auto;
  }

  .header-inner {
    gap: 12px;
    height: 74px;
    min-height: 74px;
  }

  .header-brand {
    margin-right: 0;
  }

  .header-menu {
    display: none;
  }

  .header-actions {
    display: none;
  }

  .mobile-nav-entry {
    display: inline-flex;
  }

  .mobile-nav-fab {
    display: inline-flex;
  }
}

@media (max-width: 640px) {
  .brand-sub,
  .user-name {
    display: none;
  }

  .admin-btn {
    padding-inline: 12px;
  }

  .app-content {
    padding-inline: 14px;
  }

  :deep(.mobile-nav-drawer .ant-drawer-content-wrapper) {
    width: min(88vw, 320px) !important;
  }
}
</style>

<style lang="scss">
.warm-dropdown .ant-dropdown-menu {
  min-width: 176px;
  padding: 12px;
  border-radius: 18px;
  border: 1px solid var(--theme-panel-border);
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
  box-shadow: 0 16px 28px var(--theme-shadow-soft);
}

.warm-dropdown .ant-dropdown-menu-item {
  display: flex;
  align-items: center;
  min-height: 50px;
  padding: 10px 16px;
  border-radius: 14px;
  color: var(--theme-title);
  font-weight: 700;
  gap: 8px;
  transition:
    background var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft);
}

.warm-dropdown .ant-dropdown-menu-item:hover {
  background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong));
  color: var(--theme-accent-text-hover);
  box-shadow: 0 10px 22px var(--theme-card-shadow);
  transform: translateY(-1px);
}

.warm-dropdown .ant-dropdown-menu-item-selected {
  background: var(--theme-accent) !important;
  color: var(--theme-accent-contrast) !important;
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 10px 22px var(--theme-shadow-strong);
}

.warm-dropdown .ant-dropdown-menu-item .anticon {
  font-size: 16px;
  color: currentColor;
}

.warm-dropdown .ant-dropdown-menu-item-danger {
  color: #c85a49 !important;
}

.warm-dropdown .ant-dropdown-menu-item-danger:hover {
  background: linear-gradient(180deg, #fff4f1, #ffede8) !important;
  color: #b84b3b !important;
}

.warm-dropdown .ant-dropdown-menu-item-divider {
  margin: 8px 2px;
  background: var(--theme-border);
}
</style>
