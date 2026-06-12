/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Claude-style light palette
        surface: {
          0: "#f7f5f2",   // warm off-white background
          1: "#ffffff",   // sidebar / card white
          2: "#f0ede8",   // subtle hover
          3: "#e8e3db",   // border / divider
        },
        accent: {
          DEFAULT: "#d97757",   // Claude orange
          hover: "#c46645",
          muted: "#d9775718",
          light: "#fdf3ef",
        },
        ink: {
          DEFAULT: "#1a1a19",   // near black
          muted: "#6b6860",
          faint: "#a09e99",
        },
        success: "#2d7a4f",
        warning: "#b45309",
        danger: "#c0392b",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      animation: {
        "fade-in": "fadeIn 0.15s ease-out",
        "slide-up": "slideUp 0.2s ease-out",
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: "translateY(6px)" }, to: { opacity: 1, transform: "translateY(0)" } },
      },
    },
  },
  plugins: [],
};