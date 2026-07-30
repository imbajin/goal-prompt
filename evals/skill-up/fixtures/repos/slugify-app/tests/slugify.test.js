import assert from "node:assert/strict";
import { slugify } from "../src/slugify.js";

assert.equal(slugify("  Hello   World  "), "hello-world");
