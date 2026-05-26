import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = new URL(".", import.meta.url);
const styleLibraryPath = resolve(root.pathname, "data/style-library.json");
const casesPath = resolve(root.pathname, "data/cases.json");
const outputPath = resolve(root.pathname, "site-data.js");

const styleLibrary = JSON.parse(await readFile(styleLibraryPath, "utf8"));
const casesData = JSON.parse(await readFile(casesPath, "utf8"));

const compactCases = casesData.cases.map((item) => ({
  id: item.id,
  title: item.title,
  image: item.image,
  imageAlt: item.imageAlt,
  sourceLabel: item.sourceLabel,
  sourceUrl: item.sourceUrl,
  prompt: item.prompt,
  promptPreview: item.promptPreview,
  category: item.category,
  styles: item.styles || [],
  scenes: item.scenes || [],
  featured: Boolean(item.featured),
  requiresReferenceImage: Boolean(item.requiresReferenceImage),
  githubUrl: item.githubUrl,
}));

const payload = {
  styleLibrary: {
    version: styleLibrary.version,
    repository: styleLibrary.repository,
    categories: styleLibrary.categories,
    styles: styleLibrary.styles,
    scenes: styleLibrary.scenes,
    tagLabels: styleLibrary.tagLabels,
  },
  casesData: {
    repository: casesData.repository,
    totalCases: casesData.totalCases,
    categories: casesData.categories,
    styles: casesData.styles,
    scenes: casesData.scenes,
    cases: compactCases,
  },
};

await writeFile(
  outputPath,
  `window.GPT_IMAGE2_PROMPT_SITE_DATA = ${JSON.stringify(payload)};\n`,
  "utf8"
);

console.log(`Generated ${outputPath}`);
