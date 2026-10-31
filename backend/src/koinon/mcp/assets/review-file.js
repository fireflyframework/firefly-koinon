// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// @ts-check
/**
 * @param {{request:(method:string,params:Record<string,unknown>)=>Promise<Record<string,unknown>>,presentation:(value:unknown)=>void,set:(id:string,value:unknown)=>void,error:(message:string)=>void,activate:()=>void}} bridge
 */
function createKoinonFileReview(bridge) {
  /** @typedef {import('../../../../../sdk/typescript/src/generated.js').ExternalFileReviewView} FileView */
  /** @typedef {{tenant_id:string,destination_id:string,destination_name:string,mode:'document'|'dataset',max_file_bytes:number,chunk_bytes:number}} UploadSetup */
  const el = (/** @type {string} */ id) => {
    const node = document.getElementById(id);
    if (!node) throw new Error("File review is incomplete");
    return node;
  };
  const picker = /** @type {HTMLInputElement} */ (el("file-input"));
  const confirm = /** @type {HTMLInputElement} */ (el("file-confirm"));
  const start = /** @type {HTMLButtonElement} */ (el("file-start"));
  const approve = /** @type {HTMLButtonElement} */ (el("file-approve"));
  const cancel = /** @type {HTMLButtonElement} */ (el("file-cancel"));
  const status = /** @type {HTMLButtonElement} */ (el("file-status"));
  const meter = /** @type {HTMLProgressElement} */ (el("file-meter"));
  /** @type {UploadSetup|null} */ let setup = null;
  /** @type {FileView|null} */ let review = null;
  /** @type {File|null} */ let selected = null;
  /** @type {ArrayBuffer|null} */ let bytes = null;
  let nonce = "",
    busy = false,
    paused = false,
    uncertain = false,
    stageKey = "",
    decisionKey = "",
    activated = false,
    cancelRequested = false;
  /** @type {'upload'|'decision'|'status'|null} */ let operation = null;
  /** @type {Set<number>} */ const ack = new Set();
  const object = (/** @type {unknown} */ v) =>
    v !== null && typeof v === "object" && !Array.isArray(v)
      ? /** @type {Record<string,unknown>} */ (v)
      : null;
  const set = bridge.set;
  const digest = async (/** @type {ArrayBuffer} */ data) =>
    Array.from(
      new Uint8Array(await crypto.subtle.digest("SHA-256", data)),
      (byte) => byte.toString(16).padStart(2, "0"),
    ).join("");
  function controls() {
    const active =
      review?.status === "preview" &&
      new Date(review.expires_at).getTime() > Date.now() &&
      !!nonce &&
      !busy &&
      !uncertain;
    picker.disabled =
      busy || review?.status === "preview" || review?.status === "committed";
    start.disabled =
      busy || !selected || (!!review && review.status !== "uploading");
    start.hidden = !!review && review.status !== "uploading";
    approve.hidden = review?.status !== "preview";
    approve.disabled = !active || !confirm.checked;
    confirm.disabled = !active;
    el("file-confirmation").hidden = review?.status !== "preview";
    cancel.disabled =
      (busy && operation !== "upload") ||
      !review ||
      review.status === "committed" ||
      review.status === "cancelled" ||
      review.status === "unresolved" ||
      review.status === "ingesting";
    status.hidden =
      !review ||
      (!uncertain &&
        review.status !== "unresolved" &&
        review.status !== "ingesting");
    status.disabled = busy;
  }
  function valid(/** @type {unknown} */ candidate) {
    const value = object(candidate);
    if (
      !value ||
      typeof value["id"] !== "string" ||
      typeof value["tenant_id"] !== "string" ||
      typeof value["status"] !== "string" ||
      typeof value["sha256"] !== "string" ||
      !/^[a-f0-9]{64}$/.test(value["sha256"]) ||
      !Number.isInteger(value["revision"]) ||
      !object(value["destination"]) ||
      typeof value["size_bytes"] !== "number"
    )
      throw new Error("Invalid file review");
    return /** @type {FileView} */ (/** @type {unknown} */ (value));
  }
  function render() {
    if (!setup && !review) return;
    if (!activated) {
      bridge.activate();
      activated = true;
    }
    el("file-content").hidden = false;
    set("review-title", review?.filename ?? "Upload knowledge");
    set(
      "description",
      "Choose a file, review its exact bytes and destination, then approve importing it.",
    );
    set(
      "file-destination",
      review?.destination.name ?? setup?.destination_name,
    );
    set(
      "file-mode",
      (review?.mode ?? setup?.mode) === "dataset"
        ? "Structured dataset"
        : "Document",
    );
    if (review) {
      el("file-manifest").hidden = false;
      set("file-name", review.filename);
      set("file-size", review.size_bytes.toLocaleString() + " bytes");
      set("file-type", review.content_type);
      set("file-hash", review.sha256);
      meter.hidden = false;
      meter.max = review.total_chunks;
      meter.value = review.received_chunks;
      if (review.status === "preview") {
        set("file-progress", "Ready for your approval");
        set("state-label", "Awaiting approval");
      } else if (review.status === "committed") {
        set(
          "file-progress",
          "File imported. Source: " +
            (review.source_id ?? review.receipt?.source.id ?? "not recorded"),
        );
        set("state-label", "Imported");
        bytes = null;
        selected = null;
        nonce = "";
        uncertain = false;
      } else if (review.status === "cancelled") {
        set("file-progress", "Upload cancelled. No knowledge was imported.");
        set("state-label", "Cancelled");
        bytes = null;
        selected = null;
        nonce = "";
        uncertain = false;
      } else if (
        review.status === "unresolved" ||
        review.status === "ingesting"
      ) {
        set(
          "file-progress",
          "The import outcome is not confirmed. Check status; do not submit the file again.",
        );
        set("state-label", "Check outcome");
        uncertain = true;
      } else {
        set(
          "file-progress",
          "Uploaded " +
            review.received_chunks +
            " of " +
            review.total_chunks +
            " verified chunks.",
        );
        set("state-label", busy ? "Uploading" : "Upload paused");
      }
    } else {
      set("state-label", "Choose file");
      set(
        "file-help",
        "Maximum " +
          Math.floor((setup?.max_file_bytes ?? 0) / 1048576) +
          " MiB. Nothing enters the repository before your approval.",
      );
    }
    controls();
  }
  function receive(/** @type {Record<string,unknown>} */ response) {
    const meta = object(response["_meta"]),
      privateData = object(meta?.["koinon/knowledgeReview"]),
      structured = object(response["structuredContent"]);
    const kind = privateData?.["kind"] ?? structured?.["kind"];
    if (kind !== "file" && kind !== "file_upload") return false;
    if (response["isError"] === true)
      throw new Error("File operation was denied");
    if (kind === "file_upload") {
      const value = object(privateData?.["setup"] ?? structured?.["setup"]);
      if (
        !value ||
        typeof value["tenant_id"] !== "string" ||
        typeof value["destination_id"] !== "string" ||
        typeof value["destination_name"] !== "string" ||
        !["document", "dataset"].includes(String(value["mode"])) ||
        !Number.isInteger(value["chunk_bytes"]) ||
        Number(value["chunk_bytes"]) < 1 ||
        Number(value["chunk_bytes"]) > 65536 ||
        !Number.isInteger(value["max_file_bytes"]) ||
        Number(value["max_file_bytes"]) < 1 ||
        Number(value["max_file_bytes"]) > 33554432
      )
        throw new Error("Invalid file destination");
      if (busy) return true;
      activated = false;
      setup = /** @type {UploadSetup} */ (/** @type {unknown} */ (value));
      review = null;
      selected = null;
      bytes = null;
      nonce = "";
      stageKey = "";
      decisionKey = "";
      confirm.checked = false;
      picker.value = "";
      uncertain = false;
      ack.clear();
      el("file-manifest").hidden = true;
      meter.hidden = true;
      bridge.presentation(privateData?.["presentation"]);
      render();
      return true;
    }
    const value = valid(privateData?.["review"] ?? structured?.["review"]);
    if (review && review.id !== value.id)
      throw new Error("A different file review was returned");
    const changed =
      !review ||
      review.revision !== value.revision ||
      review.authorization_digest !== value.authorization_digest;
    review = value;
    if (!setup)
      setup = {
        tenant_id: value.tenant_id,
        destination_id: value.destination.id,
        destination_name: value.destination.name,
        mode: value.mode,
        max_file_bytes: 33554432,
        chunk_bytes: 65536,
      };
    if (changed) {
      confirm.checked = false;
      nonce = "";
    }
    if (typeof privateData?.["nonce"] === "string")
      nonce = privateData["nonce"];
    bridge.presentation(privateData?.["presentation"]);
    render();
    return true;
  }
  async function call(
    /** @type {string} */ name,
    /** @type {Record<string,unknown>} */ args,
  ) {
    const response = await bridge.request("tools/call", {
      name,
      arguments: args,
    });
    if (response["isError"] === true)
      throw new Error("File operation was denied");
    receive(response);
    return response;
  }
  function encode(/** @type {ArrayBuffer} */ data) {
    const value = new Uint8Array(data);
    let binary = "";
    for (let i = 0; i < value.length; i += 8192)
      binary += String.fromCharCode(...value.subarray(i, i + 8192));
    return btoa(binary);
  }
  async function upload() {
    if (!setup || !selected || busy) return;
    const target = setup,
      file = selected;
    busy = true;
    operation = "upload";
    paused = false;
    uncertain = false;
    el("error").hidden = true;
    controls();
    try {
      bytes = await file.arrayBuffer();
      const fullHash = await digest(bytes);
      if (paused) return;
      if (
        review &&
        (review.sha256 !== fullHash ||
          review.filename !== file.name ||
          review.size_bytes !== file.size)
      )
        throw new Error("Choose the exact original file to resume");
      if (!review) {
        stageKey ||= crypto.randomUUID();
        await call("koinon_stage_file", {
          tenant_id: target.tenant_id,
          file: {
            filename: file.name,
            content_type: file.type || null,
            mode: target.mode,
            destination_id: target.destination_id,
            size_bytes: file.size,
            sha256: fullHash,
          },
          idempotency_key: stageKey,
        });
      }
      if (!review) throw new Error("No file review was returned");
      const current = review,
        data = bytes,
        total = current.total_chunks;
      let index = 0;
      const worker = async () => {
        while (!paused && index < total) {
          const part = index++;
          if (ack.has(part)) continue;
          const slice = data.slice(
            part * target.chunk_bytes,
            Math.min(data.byteLength, (part + 1) * target.chunk_bytes),
          );
          try {
            await call("koinon_upload_file_chunk", {
              tenant_id: current.tenant_id,
              review_id: current.id,
              chunk: {
                index: part,
                data_base64: encode(slice),
                sha256: await digest(slice),
              },
            });
            ack.add(part);
          } catch (error) {
            paused = true;
            throw error;
          }
        }
      };
      const completed = await Promise.allSettled(
        Array.from({ length: Math.min(4, total) }, () => worker()),
      );
      if (completed.some((value) => value.status === "rejected"))
        throw new Error("A file chunk was not confirmed");
      if (!paused)
        await call("koinon_seal_file", {
          tenant_id: current.tenant_id,
          review_id: current.id,
        });
    } catch {
      uncertain = true;
      bridge.error(
        "The upload could not be confirmed. Check status before resuming the exact same file.",
      );
    } finally {
      busy = false;
      operation = null;
      render();
      if (cancelRequested) {
        cancelRequested = false;
        await decide("cancel");
      }
    }
  }
  async function refresh() {
    if (!review || busy) return;
    busy = true;
    operation = "status";
    controls();
    try {
      await call("koinon_file_review_status", {
        tenant_id: review.tenant_id,
        review_id: review.id,
      });
      uncertain = false;
    } catch {
      bridge.error(
        "File status is unavailable. Check your connection and permissions.",
      );
    } finally {
      busy = false;
      operation = null;
      render();
    }
  }
  async function decide(/** @type {'approve'|'cancel'} */ action) {
    if (!review) return;
    if (busy) {
      if (action === "cancel" && operation === "upload") {
        cancelRequested = true;
        paused = true;
        set(
          "file-progress",
          "Pausing after the current chunks finish. Check status before cancelling.",
        );
      }
      return;
    }
    if (
      action === "approve" &&
      (!nonce || review.status !== "preview" || !confirm.checked || uncertain)
    )
      return;
    busy = true;
    operation = "decision";
    controls();
    el("error").hidden = true;
    try {
      if (action === "cancel")
        await call("koinon_file_review_status", {
          tenant_id: review.tenant_id,
          review_id: review.id,
        });
      if (!review || !nonce)
        throw new Error("Private file review is unavailable");
      /** @type {Record<string,unknown>} */ const args = {
        tenant_id: review.tenant_id,
        review_id: review.id,
        expected_revision: review.revision,
        authorization_digest: review.authorization_digest,
        nonce,
      };
      if (action === "approve") {
        decisionKey ||= crypto.randomUUID();
        args["idempotency_key"] = decisionKey;
      }
      await call(
        action === "approve" ? "koinon_approve_file" : "koinon_cancel_file",
        args,
      );
    } catch {
      uncertain = true;
      bridge.error(
        "The import outcome could not be confirmed. Check status before requesting another import.",
      );
    } finally {
      busy = false;
      operation = null;
      render();
    }
  }
  picker.addEventListener("change", () => {
    const file = picker.files?.[0];
    if (!file || !setup) return;
    if (file.size < 1 || file.size > setup.max_file_bytes) {
      selected = null;
      bridge.error(
        "Choose a nonempty file within this installation’s size limit.",
      );
      controls();
      return;
    }
    selected = file;
    el("error").hidden = true;
    set("file-help", file.name + " (" + file.size.toLocaleString() + " bytes)");
    controls();
  });
  start.addEventListener("click", () => void upload());
  confirm.addEventListener("change", controls);
  approve.addEventListener("click", () => void decide("approve"));
  cancel.addEventListener("click", () => void decide("cancel"));
  status.addEventListener("click", () => void refresh());
  setInterval(controls, 5000);
  return { receive };
}
