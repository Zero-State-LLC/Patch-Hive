// Apply the remembered theme before first paint, so a light-theme reload never flashes dark.
// App.tsx owns the theme once React mounts; the key, values and colours must match it.
try {
  if (window.localStorage.getItem("patchhive-theme") === "light") {
    document.documentElement.dataset.theme = "light";
    document.documentElement.style.colorScheme = "light";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#e9ebef");
  }
} catch {
  // Storage blocked: dark, the default.
}
