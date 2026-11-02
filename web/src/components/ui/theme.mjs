import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const amber = {
  50: "#fff8e6", 100: "#ffebb0", 200: "#ffe08a", 300: "#ffd457",
  400: "#ffc21a", 500: "#dfa008", 600: "#a16b00", 700: "#795000",
  800: "#563b08", 900: "#382908", 950: "#241b07",
};

export const system = createSystem(defaultConfig, defineConfig({
  theme: {
    tokens: {
      fonts: {
        body: { value: "'Inter', Arial, sans-serif" },
        heading: { value: "'Inter', Arial, sans-serif" },
      },
      colors: {
        brand: Object.fromEntries(Object.entries(amber).map(([key, value]) => [key, { value }])),
        canvas: { value: "#fff8e6" }, ink: { value: "#2b2100" },
        muted: { value: "#6b5a2e" }, rail: { value: "#2b2100" },
        pale: { value: "#fbefc8" },
        blueSurface: { value: "#e3f0fb" }, blueInk: { value: "#12426e" },
      },
    },
    semanticTokens: {
      colors: {
        border: { value: "#e6d6a5" },
        brand: {
          solid: { value: "{colors.brand.400}" }, contrast: { value: "{colors.ink}" },
          fg: { value: "{colors.brand.700}" }, muted: { value: "{colors.brand.100}" },
          subtle: { value: "{colors.brand.50}" }, emphasized: { value: "{colors.brand.200}" },
          focusRing: { value: "{colors.brand.600}" },
        },
      },
    },
    recipes: {
      button: {
        base: { colorPalette: "brand", borderRadius: "14px", fontWeight: "600", cursor: "pointer", transition: "background-color 120ms", whiteSpace: "normal", height: "auto", minH: "40px", py: "2", flexShrink: 0 },
        variants: { variant: { outline: { borderColor: "border" } } },
      },
      input: { base: { bg: "white", borderRadius: "14px", minH: "44px", fontSize: "md" }, variants: { variant: { outline: { bg: "white", borderColor: "border" } } } },
      textarea: { base: { bg: "white", borderRadius: "14px", fontSize: "md", minH: "100px" }, variants: { variant: { outline: { bg: "white", borderColor: "border" } } } },
      heading: { base: { color: "ink", fontWeight: "700", letterSpacing: "-0.025em" } },
    },
    slotRecipes: {
      card: { base: { root: { bg: "white", borderRadius: "20px", boxShadow: "none", borderColor: "border", overflow: "hidden" } } },
      table: { base: { root: { bg: "white" }, columnHeader: { bg: "pale", color: "muted", fontSize: "sm", textTransform: "none", fontWeight: "600", py: "3" }, cell: { py: "4", verticalAlign: "top" } } },
      dialog: { base: { content: { borderRadius: "20px", mx: "4", maxW: "calc(100vw - 32px)" }, title: { fontSize: "xl" }, footer: { flexWrap: "wrap" } } },
      field: { base: { root: { minW: "0" }, label: { fontSize: "sm", color: "ink", fontWeight: "600" }, helperText: { fontSize: "sm" }, errorText: { fontSize: "sm" } } },
      badge: { base: { textTransform: "none", letterSpacing: "normal", borderRadius: "4px", fontWeight: "600", px: "2", py: "1" } },
    },
  },
  globalCss: {
    "@font-face": { fontFamily: "Inter", src: 'url(/fonts/Inter.ttf) format("truetype")', fontWeight: "100 900", fontStyle: "normal", fontDisplay: "swap" },
    "html": { colorScheme: "light", colorPalette: "brand", scrollBehavior: "auto" },
    "body": { bg: "canvas", color: "ink", fontSize: "md", lineHeight: "1.6" },
    "*": { scrollbarWidth: "thin", scrollbarColor: "#aab2bb transparent" },
    "::selection": { bg: "brand.200", color: "ink" },
    ":focus-visible": { outline: "3px solid #a16b00", outlineOffset: "3px" },
    "button, input, select, textarea": { font: "inherit" },
    "button:disabled": { cursor: "not-allowed" },
    "select:not([data-scope])": { bg: "white", border: "1px solid #e6d6a5", borderRadius: "14px", minH: "44px", px: "3", py: "2", width: "100%", maxW: "100%", color: "ink" },
    "label": { fontSize: "sm", color: "ink" },
    "label > input:not([type=checkbox]), label > textarea, label > select": { mt: "2" },
    "fieldset": { minWidth: "0", border: 0 },
    "fieldset:disabled": { opacity: "0.7" },
    "[role=alert]": { bg: "red.50", color: "red.800", borderRadius: "14px", p: "3", overflowWrap: "anywhere" },
    "p[role=status]": { bg: "green.50", color: "green.800", borderRadius: "14px", p: "3" },
    "main > div, main section": { borderColor: "border" },
    "summary": { cursor: "pointer", fontWeight: "600", minH: "40px", py: "2" },
    "main img, main video, main iframe": { maxW: "100%" },
    "main p, main td": { overflowWrap: "anywhere" },
    "@media (prefers-reduced-motion: reduce)": { "*": { animation: "none !important", transition: "none !important" } },
  },
}));
