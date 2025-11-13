/**
 * Eleventy data loader: reads all window_*.parquet files from ../../data/
 *
 * This runs once at build time and makes all documents available as
 * {{ documents }} in templates.
 */

const fs = require("fs");
const path = require("path");
const parquet = require("parquetjs");

module.exports = async function () {
  const dataDir = path.resolve(__dirname, "../../../data");

  // Find all window_*.parquet files
  const files = fs
    .readdirSync(dataDir)
    .filter((f) => f.startsWith("window_") && f.endsWith(".parquet"))
    .sort(); // Sort by window number

  if (files.length === 0) {
    console.warn(`No Parquet files found in ${dataDir}`);
    return [];
  }

  const documents = [];

  // Read each Parquet file
  for (const file of files) {
    const filePath = path.join(dataDir, file);
    console.log(`Loading ${file}...`);

    const reader = await parquet.ParquetReader.openFile(filePath);
    const cursor = reader.getCursor();

    let record = null;
    while ((record = await cursor.next())) {
      // Parse metadata JSON
      const metadata = record.metadata ? JSON.parse(record.metadata) : {};

      documents.push({
        id: record.id,
        slug: record.slug,
        kind: record.kind,
        title: record.title,
        body_md: record.body_md,
        created_at: record.created_at,
        parent_id: record.parent_id || null,
        metadata: metadata,
      });
    }

    await reader.close();
  }

  console.log(`Loaded ${documents.length} documents from ${files.length} window(s)`);
  return documents;
};
