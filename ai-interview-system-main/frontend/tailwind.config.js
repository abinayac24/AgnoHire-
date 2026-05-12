/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#08101d",
        mist: "#11172c",
        surge: "#1fd8f6",
        ember: "#d81e2b",
        tide: "#18b8db",
        night: "#090b18"
      },
      fontFamily: {
        sans: ['"Space Grotesk"', '"Segoe UI"', "sans-serif"]
      },
      boxShadow: {
        panel: "0 28px 90px rgba(0,0,0,0.45)"
      }
    }
  },
  plugins: []
};
