import { createApp } from 'vue';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import axios from 'axios';
import App from './App.vue';
import router from './router';

// 移除baseURL，全部用相对路径，走devServer代理
// axios.defaults.baseURL = process.env.VUE_APP_API_URL || 'http://localhost:5000';
axios.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const app = createApp(App);

// 添加全局属性
app.config.globalProperties.$axios = axios;

// 使用插件
app.use(ElementPlus);
app.use(router);

app.mount('#app'); 