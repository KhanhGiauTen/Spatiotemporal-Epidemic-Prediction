import assert from "node:assert/strict";
import { predictDemo, validInput } from "../app/api/prediction.ts";

const zero = { contacts: 0, duration: 0, household_size: 0, hcir: 0, location_risk_score: 0 };
assert.equal(validInput(zero), true);
assert.equal(predictDemo(zero).probability, 0);
assert.equal(predictDemo({ contacts: 60, duration: 120, household_size: 8, hcir: 100, location_risk_score: 1 }).probability, 1);
assert.equal(predictDemo({ contacts: 30, duration: 45, household_size: 4, hcir: 50, location_risk_score: 0.6 }).probability, 0.494);
assert.equal(validInput({ ...zero, hcir: 101 }), false);
assert.equal(validInput({ ...zero, contacts: -1 }), false);
assert.equal(validInput({ ...zero, duration: NaN }), false);
assert.equal(validInput({ ...zero, contacts: "30" }), false);
assert.equal(validInput({ ...zero, extra: 1 }), false);
assert.equal(validInput(null), false);
console.log("PASS demo scoring boundaries and invalid input checks");
