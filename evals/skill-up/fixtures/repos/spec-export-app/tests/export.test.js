import assert from "node:assert/strict";
import { exportProject } from "../src/export.js";

assert.deepEqual(exportProject({ files: ["b", "a"] }), { files: ["b", "a"] });
