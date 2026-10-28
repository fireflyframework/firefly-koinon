// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
const safe=9007199254740991n;
export function exactInteger(value:bigint):number|string {
 if(typeof value!=='bigint')throw new TypeError('Supply bigint; implicit coercion is not supported');
 return value>=-safe&&value<=safe?Number(value):value.toString(10);
}
export function exactDecimal(value:string):string {
 if(typeof value!=='string'||!/^[-+]?\d+(?:\.\d+)?$/.test(value))throw new TypeError('Supply a finite plain decimal string without whitespace or an exponent');
 return value;
}
