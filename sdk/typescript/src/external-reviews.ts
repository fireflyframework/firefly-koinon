// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {KoinonTransport,RequestOptions} from "./transport.js";
import type {ExternalFileCleanupInput,ExternalFileCleanupResult,ExternalFileReviewInput,ExternalFileChunkInput,ExternalFileReviewView,ExternalReviewInput,ExternalReviewDecision,ExternalReviewView,CommittedKnowledge,PendingKnowledgeCommit} from "./generated.js";
const id=encodeURIComponent;
const tenant=(tenantId:string)=>`/tenants/${id(tenantId)}`;
type KnowledgeCommitOutcome=CommittedKnowledge|PendingKnowledgeCommit;
export function createExternalReviewsApi(transport:KoinonTransport){
  const externalFileReviews={
   cleanup:(tenantId:string,input:ExternalFileCleanupInput,options:RequestOptions={})=>transport.request<ExternalFileCleanupResult>('POST',`${tenant(tenantId)}/external-file-reviews/cleanup`,{...options,body:input}),
   stage:(tenantId:string,input:ExternalFileReviewInput,idempotencyKey:string,options:RequestOptions={})=>transport.request<ExternalFileReviewView>('POST',`${tenant(tenantId)}/external-file-reviews`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
   get:(tenantId:string,reviewId:string,options:RequestOptions={})=>transport.request<ExternalFileReviewView>('GET',`${tenant(tenantId)}/external-file-reviews/${id(reviewId)}`,options),
   chunk:(tenantId:string,reviewId:string,input:ExternalFileChunkInput,options:RequestOptions={})=>transport.request<ExternalFileReviewView>('POST',`${tenant(tenantId)}/external-file-reviews/${id(reviewId)}/chunks`,{...options,body:input}),
   seal:(tenantId:string,reviewId:string,options:RequestOptions={})=>transport.request<ExternalFileReviewView>('POST',`${tenant(tenantId)}/external-file-reviews/${id(reviewId)}/seal`,options),
   approve:(tenantId:string,reviewId:string,input:ExternalReviewDecision,idempotencyKey:string,options:RequestOptions={})=>transport.request<ExternalFileReviewView>('POST',`${tenant(tenantId)}/external-file-reviews/${id(reviewId)}/approve`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
   cancel:(tenantId:string,reviewId:string,input:ExternalReviewDecision,options:RequestOptions={})=>transport.request<ExternalFileReviewView>('POST',`${tenant(tenantId)}/external-file-reviews/${id(reviewId)}/cancel`,{...options,body:input}),
  };
  const externalReviews={
   stage:(tenantId:string,input:ExternalReviewInput,idempotencyKey:string,options:RequestOptions={})=>transport.request<ExternalReviewView>('POST',`${tenant(tenantId)}/external-knowledge-reviews`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
   get:(tenantId:string,reviewId:string,options:RequestOptions={})=>transport.request<ExternalReviewView>('GET',`${tenant(tenantId)}/external-knowledge-reviews/${id(reviewId)}`,options),
   approve:(tenantId:string,reviewId:string,input:ExternalReviewDecision,idempotencyKey:string,options:RequestOptions={})=>transport.request<KnowledgeCommitOutcome>('POST',`${tenant(tenantId)}/external-knowledge-reviews/${id(reviewId)}/approve`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
   cancel:(tenantId:string,reviewId:string,input:ExternalReviewDecision,options:RequestOptions={})=>transport.request<ExternalReviewView>('POST',`${tenant(tenantId)}/external-knowledge-reviews/${id(reviewId)}/cancel`,{...options,body:input}),
  };
  return {externalFileReviews,externalReviews};
}
export type ExternalReviewsApi=ReturnType<typeof createExternalReviewsApi>;
