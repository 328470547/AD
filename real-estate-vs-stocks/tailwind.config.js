/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef4ff', 100: '#dbe6fe', 200: '#bccffd', 300: '#8fa9fb',
          400: '#6480f6', 500: '#3f57ee', 600: '#2c39e0', 700: '#252dc0',
          800: '#232a99', 900: '#212879'
        }
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif']
      }
    }
  },
  plugins: []
};
