/**
 * Eleventy configuration for Egregora Arrow output.
 *
 * Reads Parquet files from ../data/ and generates static site.
 */

const markdownIt = require("markdown-it");

module.exports = function (eleventyConfig) {
  // Markdown configuration
  const md = markdownIt({
    html: true,
    linkify: true,
    typographer: true,
  });

  eleventyConfig.setLibrary("md", md);
  eleventyConfig.addFilter("markdown", (content) => md.render(content));

  // Collections from Arrow data
  eleventyConfig.addCollection("posts", (collectionApi) => {
    const docs = collectionApi.globalData.documents || [];
    return docs
      .filter((d) => d.kind === "post")
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  });

  eleventyConfig.addCollection("profiles", (collectionApi) => {
    const docs = collectionApi.globalData.documents || [];
    return docs.filter((d) => d.kind === "profile");
  });

  eleventyConfig.addCollection("journals", (collectionApi) => {
    const docs = collectionApi.globalData.documents || [];
    return docs
      .filter((d) => d.kind === "journal")
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  });

  // Copy static assets
  eleventyConfig.addPassthroughCopy("src/assets");
  eleventyConfig.addPassthroughCopy("src/media");

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes",
      data: "_data",
    },
    templateFormats: ["njk", "md", "html"],
    htmlTemplateEngine: "njk",
    markdownTemplateEngine: "njk",
  };
};
