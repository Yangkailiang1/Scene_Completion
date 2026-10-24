export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(214 24% 90%)",
        input: "hsl(214 24% 90%)",
        ring: "#496ad5",
        background: "#f6f8fb",
        foreground: "#23334c",
        primary: { DEFAULT: "#3e63dd", foreground: "#fff" },
        secondary: { DEFAULT: "#eef2f8", foreground: "#46566e" },
        muted: { DEFAULT: "#f4f6fa", foreground: "#7d8ba0" },
        accent: { DEFAULT: "#eef2ff", foreground: "#3459c7" },
        destructive: { DEFAULT: "#c84961", foreground: "#fff" },
      },
      borderRadius: { lg: "0.75rem", md: "0.5rem", sm: "0.375rem" },
    },
  },
  plugins: [],
};
