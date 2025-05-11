<template>
  <div class="layout-container">
    <el-container>
      <el-header class="main-header">
        <div class="logo">
          <h1>MetaGPT Web</h1>
        </div>
        <div class="user-info">
          <el-dropdown @command="handleCommand">
            <span class="el-dropdown-link">
              {{ username }}
              <el-icon class="el-icon--right">
                <i class="el-icon-arrow-down"></i>
              </el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-container>
        <el-aside width="200px" class="main-aside">
          <el-menu
            :default-active="activeMenu"
            router
            class="el-menu-vertical"
            background-color="#304156"
            text-color="#bfcbd9"
            active-text-color="#409EFF"
          >
            <el-menu-item index="/">
              <i class="el-icon-s-home"></i>
              <span>项目列表</span>
            </el-menu-item>
            <el-menu-item index="/projects/new">
              <i class="el-icon-plus"></i>
              <span>创建项目</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        
        <el-main class="main-content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script>
export default {
  name: 'AppLayout',
  data() {
    return {
      username: 'Admin'
    };
  },
  computed: {
    activeMenu() {
      // 根据当前路由确定激活的菜单项
      const { path } = this.$route;
      
      if (path.includes('/projects/') && !path.includes('/projects/new')) {
        return '/';
      }
      
      return path;
    }
  },
  created() {
    this.getUserInfo();
  },
  methods: {
    getUserInfo() {
      try {
        const userStr = localStorage.getItem('user');
        if (userStr) {
          const user = JSON.parse(userStr);
          this.username = user.name || user.username;
        }
      } catch (error) {
        console.error('获取用户信息失败', error);
      }
    },
    handleCommand(command) {
      if (command === 'logout') {
        this.logout();
      }
    },
    logout() {
      // 清除本地存储中的用户信息和token
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      
      // 重定向到登录页
      this.$router.push('/login');
    }
  }
};
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.main-header {
  background-color: #fff;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.logo h1 {
  font-size: 18px;
  margin: 0;
  color: #409EFF;
}

.user-info {
  display: flex;
  align-items: center;
}

.el-dropdown-link {
  cursor: pointer;
  display: flex;
  align-items: center;
}

.main-aside {
  background-color: #304156;
  border-right: 1px solid #1f2d3d;
}

.el-menu-vertical {
  border-right: none;
}

.main-content {
  padding: 20px;
  background-color: #f0f2f5;
  height: calc(100vh - 60px);
  overflow-y: auto;
}
</style> 