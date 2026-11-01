// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {AnswerAudit,AnswerRelease,ResultPin,SourceReference} from '../dist/index.js';
export function recordedOutput(audit:AnswerAudit):AnswerRelease|null|undefined {
 return audit.output_release;
}
export function pins(release:AnswerRelease):Array<ResultPin>|undefined {
 return release.result_pins;
}
export function sources(release:AnswerRelease):Array<SourceReference>|undefined {
 return release.source_refs;
}
export const policy:AnswerRelease['policy_version']='knowledge-only-v1';
// @ts-expect-error Public output release identifies the server's actual policy, not a client invention.
export const invented:AnswerRelease['policy_version']='invented-policy';
// @ts-expect-error A result pin requires its recorded payload digest.
export const incomplete:ResultPin={id:'result'};
