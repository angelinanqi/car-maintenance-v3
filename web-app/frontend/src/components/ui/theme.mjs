import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const amber = {
  50: "#fff9e8", 100: "#fff0c2", 200: "#ffe08a", 300: "#ffce51",
  400: "#f5b823", 500: "#dfa008", 600: "#a16b00", 700: "#795000",
  800: "#563b08", 900: "#382908", 950: "#241b07",
};

export const system = createSystem(defaultConfig, defineConfig({
  theme: {
    tokens: {
      fonts: {
        body: { value: "'Segoe UI', Arial, sans-serif" },
        heading: { value: "'Segoe UI', Arial, sans-serif" },
      },
      colors: {
        brand: Object.fromEntries(Object.entries(amber).map(([key, value]) => [key, { value }])),
        canvas: { value: "#f5f6f8" }, ink: { value: "#20252b" },
        muted: { value: "#56616d" }, rail: { value: "#202830" },
      },
    },
    semanticTokens: {
      colors: {
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
        base: { colorPalette: "brand", borderRadius: "6px", fontWeight: "600", cursor: "pointer", transition: "background-color 120ms", whiteSpace: "normal", height: "auto", minH: "40px", py: "2", flexShrink: 0 },
        variants: { variant: { outline: { borderColor: "#7b8794" } } },
      },
      input: { base: { bg: "white", borderRadius: "6px", minH: "44px", fontSize: "md" }, variants: { variant: { outline: { bg: "white", borderColor: "#7b8794" } } } },
      textarea: { base: { bg: "white", borderRadius: "6px", fontSize: "md", minH: "100px" }, variants: { variant: { outline: { bg: "white", borderColor: "#7b8794" } } } },
      heading: { base: { color: "ink", fontWeight: "650", letterSpacing: "-0.025em" } },
    },
    slotRecipes: {
      card: { base: { root: { bg: "white", borderRadius: "12px", boxShadow: "none", borderColor: "gray.200", overflow: "hidden" } } },
      table: { base: { root: { bg: "white" }, columnHeader: { bg: "gray.100", color: "muted", fontSize: "sm", textTransform: "none", fontWeight: "600", py: "3" }, cell: { py: "4", verticalAlign: "top" } } },
      dialog: { base: { content: { borderRadius: "12px", mx: "4", maxW: "calc(100vw - 32px)" }, title: { fontSize: "xl" }, footer: { flexWrap: "wrap" } } },
      field: { base: { root: { minW: "0" }, label: { fontSize: "sm", color: "ink", fontWeight: "600" }, helperText: { fontSize: "sm" }, errorText: { fontSize: "sm" } } },
      badge: { base: { textTransform: "none", letterSpacing: "normal", borderRadius: "4px", fontWeight: "600", px: "2", py: "1" } },
    },
  },
  globalCss: {
    "html": { colorScheme: "light", colorPalette: "brand", scrollBehavior: "auto" },
    "body": { bg: "canvas", color: "ink", fontSize: "md", lineHeight: "1.6" },
    "*": { scrollbarWidth: "thin", scrollbarColor: "#aab2bb transparent" },
    "::selection": { bg: "brand.200", color: "ink" },
    ":focus-visible": { outline: "3px solid #a16b00", outlineOffset: "3px" },
    "button, input, select, textarea": { font: "inherit" },
    "button:disabled": { cursor: "not-allowed" },
    "select:not([data-scope])": { bg: "white", border: "1px solid #c9ced5", borderRadius: "6px", minH: "44px", px: "3", py: "2", width: "100%", maxW: "100%", color: "ink" },
    "label": { fontSize: "sm", color: "ink" },
    "label > input:not([type=checkbox]), label > textarea, label > select": { mt: "2" },
    "fieldset": { minWidth: "0", border: 0 },
    "fieldset:disabled": { opacity: "0.7" },
    "[role=alert]": { bg: "red.50", color: "red.800", borderRadius: "6px", p: "3", overflowWrap: "anywhere" },
    "p[role=status]": { bg: "green.50", color: "green.800", borderRadius: "6px", p: "3" },
    "summary": { cursor: "pointer", fontWeight: "600", minH: "40px", py: "2" },
    "main img, main video, main iframe": { maxW: "100%" },
    "main p, main td": { overflowWrap: "anywhere" },
    "@media (prefers-reduced-motion: reduce)": { "*": { animation: "none !important", transition: "none !important" } },
  },
}));
