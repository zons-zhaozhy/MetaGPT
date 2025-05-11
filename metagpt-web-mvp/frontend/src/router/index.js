import { createRouter, createWebHistory } from 'vue-router';

// 路由懒加载
const UserLogin = () => import('../views/Login.vue');
const AppLayout = () => import('../views/Layout.vue');
const ProjectList = () => import('../views/ProjectList.vue');
const NewProject = () => import('../views/NewProject.vue');
const ProjectDetail = () => import('../views/ProjectDetail.vue');

// 路由配置
const routes = [
  {
    path: '/login',
    name: 'UserLogin',
    component: UserLogin,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'ProjectList',
        component: ProjectList,
        meta: { title: '项目列表' }
      },
      {
        path: 'projects/new',
        name: 'NewProject',
        component: NewProject,
        meta: { title: '创建项目' }
      },
      {
        path: 'projects/:id',
        name: 'ProjectDetail',
        component: ProjectDetail,
        meta: { title: '项目详情' }
      }
    ]
  },
  // 404路由
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token');
  
  if (to.meta.requiresAuth && !token) {
    // 需要登录但没有token，重定向到登录页
    next({ name: 'UserLogin', query: { redirect: to.fullPath } });
  } else if (to.path === '/login' && token) {
    // 已登录但访问登录页，重定向到首页
    next({ path: '/' });
  } else {
    next();
  }
});

export default router; 