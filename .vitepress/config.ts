import { defineConfig } from "vitepress";

export default defineConfig({
  markdown: {
    languageAlias: {
      gitignore: "ignore",
      dockerignore: "ignore",
      ".gitignore": "ignore",
      ".dockerignore": "ignore",

      jinja2: "jinja",
      j2: "jinja",

      gotemplate: "go-template",
      gohtml: "go-template",
      tmpl: "go-template",

      promql: "sql",
    },
  },
  srcExclude: [
    "**/node_modules/**",
    "**/dist/**",
    "**/.vitepress/cache/**",
    "**/.vitepress/dist/**",
    "**/backup/**",
    "**/logs/**",
  ],
});
