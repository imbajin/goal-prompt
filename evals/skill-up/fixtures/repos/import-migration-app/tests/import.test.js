import assert from "node:assert/strict";
import { importBatch } from "../src/import.js";

assert.equal(importBatch([{ id: 1 }]), 1);
