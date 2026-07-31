<template>
  <!-- 根组件：只负责渲染当前路由对应的页面 -->
  <router-view />
</template>

<script setup>
// 全局样式不需要额外引入，Element Plus 已在 main.js 注册
</script>

<style>
/* 全局基础样式 */
html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
  background-color: #f5f7fa;
}

#app {
  height: 100%;
}
</style>
