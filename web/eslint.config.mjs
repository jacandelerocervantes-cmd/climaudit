import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const config = [
  ...coreWebVitals,
  ...typescript,
  { ignores: [".next/**", "node_modules/**", "src/lib/api-types.ts", "next-env.d.ts", "coverage/**"] },
  {
    // Every text is rendered as plain text: raw HTML injection is never allowed.
    rules: { "react/no-danger": "error" },
  },
];

export default config;
