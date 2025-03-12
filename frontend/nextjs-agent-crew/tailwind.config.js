/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#fef7f1',
          100: '#feeee4',
          200: '#fcd9c4',
          300: '#fabb93',
          400: '#f79362',
          500: '#f17439',
          600: '#e45a1a',
          700: '#bd4614',
          800: '#983a15',
          900: '#7c3114',
          brandGray: "#F2F4F7",
          brandDarkGray: "#F2F4F7",
          brandAvatarGray: "#98A2B3",
          bodyText: "#101828",
          brandTextSecondary: "#667085",
          brandTextPrimary: "#101828",
          brandBorder: "#EE762480",
          brandColor: "#EE7624",
          brandPrimaryColor: "#EE7624",
          bodyBg: "#f9fafb",
          brandPlaceholder: "#98A2B3",
          brandFrame: "#EAECF0",
          timeLine: "#D0D5DD",
        }
      }
    },
  },
  plugins: [
    require('tailwind-scrollbar')({ nocompatible: true }),
    require('@tailwindcss/typography'),
  ],
}