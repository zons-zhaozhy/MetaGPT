<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="text-center">
          <h2>MetaGPT Web</h2>
        </div>
      </template>
      <el-form :model="loginForm" :rules="rules" ref="loginFormRef" label-width="0" class="login-form">
        <el-form-item prop="username">
          <el-input v-model="loginForm.username" placeholder="用户名" prefix-icon="el-icon-user" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="loginForm.password" placeholder="密码" prefix-icon="el-icon-lock" show-password type="password" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleLogin" class="login-button">登录</el-button>
        </el-form-item>
      </el-form>
      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: 'UserLogin',
  data() {
    return {
      loginForm: {
        username: 'admin',
        password: 'admin123'
      },
      rules: {
        username: [
          { required: true, message: '请输入用户名', trigger: 'blur' }
        ],
        password: [
          { required: true, message: '请输入密码', trigger: 'blur' }
        ]
      },
      loading: false,
      errorMessage: ''
    };
  },
  methods: {
    handleLogin() {
      this.$refs.loginFormRef.validate(async (valid) => {
        if (valid) {
          this.loading = true;
          this.errorMessage = '';
          
          try {
            const response = await this.$axios.post('/api/auth/login', this.loginForm);
            const { token, user } = response.data;
            
            // 保存token和用户信息
            localStorage.setItem('token', token);
            localStorage.setItem('user', JSON.stringify(user));
            
            // 跳转到首页或重定向URL
            const redirectPath = this.$route.query.redirect || '/';
            this.$router.push(redirectPath);
          } catch (error) {
            if (error.response && error.response.data && error.response.data.error) {
              this.errorMessage = error.response.data.error;
            } else {
              this.errorMessage = '登录失败，请稍后再试';
            }
          } finally {
            this.loading = false;
          }
        }
      });
    }
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f5f7fa;
}

.login-card {
  width: 400px;
  max-width: 90%;
}

.login-form {
  margin-top: 20px;
}

.login-button {
  width: 100%;
}

.error-message {
  color: #f56c6c;
  text-align: center;
  margin-top: 10px;
}
</style> 