export default defineAppConfig({
  pages: [
    'pages/entry/index',
    'pages/home/index',
    'pages/search/index',
    'pages/cart/index',
    'pages/checkout/index',
    'pages/profile/index',
  ],
  subPackages: [],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#ffffff',
    navigationBarTextStyle: 'black',
    navigationStyle: 'custom',
  },
})
