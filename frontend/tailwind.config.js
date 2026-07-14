module.exports = {
  content: ["./src/**/*.{js,jsx}", "./public/index.html"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        border: "var(--border)",
        txt: "var(--txt)",
        muted: "var(--muted)",
        primary: "#4338CA",
        "primary-hover": "#3730A3",
        glow: "#00E5FF",
        danger: "#EF4444",
        success: "#10B981",
      },
      fontFamily: {
        display: ['"Cabinet Grotesk"', '"IBM Plex Sans"', "sans-serif"],
        body: ['"IBM Plex Sans"', "sans-serif"],
      },
      borderRadius: {
        sm: "3px",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "trace": {
          "0%": { backgroundPosition: "0% 50%" },
          "100%": { backgroundPosition: "200% 50%" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease forwards",
        "trace": "trace 3s linear infinite",
      },
    },
  },
  plugins: [],
};
