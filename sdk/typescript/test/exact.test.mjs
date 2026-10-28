// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {exactDecimal,exactInteger} from '../dist/index.js';
test('exact values preserve decimal scale and integer safe boundaries without floating coercion',()=>{
 for(const [input,output] of [[0n,0],[9007199254740991n,9007199254740991],[-9007199254740991n,-9007199254740991],[9007199254740992n,'9007199254740992'],[-9007199254740992n,'-9007199254740992'],[18446744073709551615n,'18446744073709551615']])assert.equal(exactInteger(input),output);
 for(const value of ['1.2300','-0.1234567890123456789','0.00'])assert.equal(exactDecimal(value),value);
 for(const value of [true,false,42,'42'])assert.throws(()=>exactInteger(value),TypeError);
 for(const value of ['NaN','Infinity','1e3',' 1.2','1.2 ',true,1.2])assert.throws(()=>exactDecimal(value));
});
