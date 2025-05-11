module.exports = {
  outputDir: 'dist',
  assetsDir: 'static',
  productionSourceMap: false,
  devServer: {
    proxy: {
      '/api': {
        target: process.env.VUE_APP_API_URL || 'http://localhost:5001',
        changeOrigin: true
      },
      '/socket.io': {
        target: process.env.VUE_APP_API_URL || 'http://localhost:5001',
        changeOrigin: true,
        ws: true,
        logLevel: 'debug'
      }
    }
  }
} 