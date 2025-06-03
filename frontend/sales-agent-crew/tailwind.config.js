/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#F8EEFF',
          100: '#E8D8F3', 
          200: '#D4B6E8',
          300: '#C094DD',
          400: '#AC71D2',
          500: '#974FC7',
          600: '#8138b0',
          700: '#622B86',
          800: '#4E226B',
          900: '#351749',
          950: '#250e36',
          brandGray: '#F2F4F7',
          brandDarkGray: '#F2F4F7',
          brandAvatarGray: '#98A2B3',
          bodyText: '#101828',
          brandTextSecondary: '#667085',
          brandTextPrimary: '#101828',
          brandBorder: '#4E226B80',
          brandColor: '#4E226B',
          brandPrimaryColor: '#4E226B',
          bodyBg: '#f9fafb',
          brandPlaceholder: '#98A2B3',
          brandFrame: '#EAECF0',
          timeLine: '#D0D5DD',
          link: '#1890FF',
        },
      },
    },
  },
  plugins: [
    require('tailwind-scrollbar')({ nocompatible: true }),
    require('@tailwindcss/typography'),
  ],
};
