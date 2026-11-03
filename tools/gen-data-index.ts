import path from "node:path";
import { writeDataIndex } from "../server/dataIndex";

/** `npm run gen:episodes` : régénère src/episodes/data-index.ts à partir des episodes/<id>/scenes.json. */
const root = path.resolve(import.meta.dirname, "..");
console.log(writeDataIndex(root) ? "data-index.ts mis à jour" : "data-index.ts déjà à jour");
